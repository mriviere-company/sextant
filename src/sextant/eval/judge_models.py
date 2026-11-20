r"""Compare `deepseek-flash` with `deepseek-v4-pro` as judges on the cached dev requests.

Protocol and rule: `eval/LLM_MODELS.md`, written before the run. The judge requests pro
already answered for **dev-split** candidates are read from the response cache and replayed
with flash, unchanged otherwise; both answers go through the parsers the pipelines use, and
the decisions code consumes are compared with Cohen's kappa. A judge switches to flash only
if every one of its decisions reaches kappa 0.80.

Writes `eval/results/judge_models.{json,md}`. Usage (needs the cache; flash calls are cached
too): `uv run python -m sextant.eval.judge_models`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from sextant.eval.dataset import SectionRef
from sextant.eval.generation.models import Candidate, read_jsonl
from sextant.eval.generation.pipeline import _parallel
from sextant.eval.generation.prompts import JUDGE_SYSTEM
from sextant.eval.migration import (
    REASSESS_SYSTEM,
    STRICT_SYSTEM,
    parse_reassessment,
    parse_strict,
)
from sextant.generation.pricing import cost_usd
from sextant.llm import (
    FAST_MODEL,
    STRONG_MODEL,
    DeepSeekJsonLlm,
    DiskCache,
    JsonLlm,
    LlmError,
    Request,
    Role,
    parse_json_object,
)

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "eval" / ".llm-cache"
CANDIDATES = ROOT / "eval" / "dataset" / "v1" / "candidates.jsonl"  # same ids, questions, splits
OUT = ROOT / "eval" / "results" / "judge_models.json"
THRESHOLD = 0.80
UNUSABLE = "unusable"
BOOTSTRAP = 10_000
SEED = 42

Payload = Mapping[str, Any] | None
Decisions = dict[str, list[str]]  # decision -> one label per unit
_SHOWN = re.compile(r"^\[(S\d+)\] (.*)$", re.MULTILINE)


def shown_sections(user: str) -> list[tuple[str, str]]:
    """Return the (label, title line) of every section a judge prompt shows, in order."""
    return [(m.group(1), m.group(2)) for m in _SHOWN.finditer(user)]


def _yes(flag: bool) -> str:
    return "yes" if flag else "no"


def relevance_decisions(payload: Payload, user: str) -> Decisions:
    """Relevant or not for each shown section, and whether the sections answer the question."""
    labels = [label for label, _ in shown_sections(user)]
    if payload is None:
        return {"section": [UNUSABLE] * len(labels), "answerable": [UNUSABLE]}
    raw = payload.get("relevant")
    chosen = {k for k in (raw if isinstance(raw, list) else []) if k in labels}
    return {
        "section": [_yes(label in chosen) for label in labels],
        "answerable": [_yes(payload.get("answerable") is True)],
    }


def reassessment_decisions(payload: Payload, user: str) -> Decisions:
    """Return the old-answer verdict, answerability and validity, as the migration reads them."""
    if payload is None:
        return {name: [UNUSABLE] for name in ("old_answer", "answerable", "question_valid")}
    labels = {
        label: SectionRef(slug="section", section_index=n)
        for n, (label, _) in enumerate(shown_sections(user))
    }
    parsed = parse_reassessment("item", payload, labels)
    return {
        "old_answer": [parsed.old_answer],
        "answerable": [_yes(parsed.answerable)],
        "question_valid": [_yes(parsed.question_valid)],
    }


def strict_decisions(payload: Payload, user: str) -> Decisions:
    """Whether every claim of the reviewed answer is backed by the wiki."""
    if payload is None:
        return {"consistent": [UNUSABLE]}
    return {"consistent": [_yes(parse_strict("item", payload).consistent)]}


@dataclass(frozen=True)
class Task:
    """One judge: its prompt, how to find the question in a request, how to read its answer."""

    role: Role
    system: str
    question: re.Pattern[str]
    decisions: Callable[[Payload, str], Decisions]


TASKS = (
    Task(
        "relevance_judge",
        JUDGE_SYSTEM,
        re.compile(r"\AQuestion \(\w+\): (.*?)\nReference answer:", re.DOTALL),
        relevance_decisions,
    ),
    Task(
        "reassessment",
        REASSESS_SYSTEM,
        re.compile(r"\AQuestion \(\w+\): (.*?)\nOld kind:", re.DOTALL),
        reassessment_decisions,
    ),
    Task(
        "strict_check",
        STRICT_SYSTEM,
        re.compile(r"\AQuestion: (.*?)\nAnswer to verify:", re.DOTALL),
        strict_decisions,
    ),
)


# --- statistics ----------------------------------------------------------------------------


def kappa(confusion: np.ndarray) -> float:
    """Cohen's kappa of a square confusion matrix; perfect agreement on one class counts as 1."""
    total = float(confusion.sum())
    if total == 0:
        return float("nan")
    observed = float(np.trace(confusion)) / total
    expected = float((confusion.sum(axis=0) * confusion.sum(axis=1)).sum()) / total**2
    if expected >= 1.0:
        return 1.0 if observed >= 1.0 else 0.0
    return (observed - expected) / (1.0 - expected)


def confusions(pairs: Sequence[Sequence[tuple[str, str]]], classes: Sequence[str]) -> np.ndarray:
    """One confusion matrix per item (rows pro, columns flash), shape (items, K, K)."""
    index = {c: n for n, c in enumerate(classes)}
    out = np.zeros((len(pairs), len(classes), len(classes)), dtype=np.int64)
    for item, units in enumerate(pairs):
        for pro, flash in units:
            out[item, index[pro], index[flash]] += 1
    return out


def bootstrap_kappa(per_item: np.ndarray, seed: int = SEED, n: int = BOOTSTRAP) -> list[float]:
    """95 % interval of kappa, resampling items (all units of an item move together)."""
    rng = np.random.default_rng(seed)
    items = per_item.shape[0]
    values: list[float] = []
    for start in range(0, n, 500):
        draws = rng.integers(0, items, size=(min(500, n - start), items))
        values += [kappa(m) for m in per_item[draws].sum(axis=1)]
    lo, hi = np.nanpercentile(values, [2.5, 97.5])
    return [round(float(lo), 4), round(float(hi), 4)]


def decide(switched: Mapping[str, bool]) -> dict[Role, str]:
    """Apply the rule of `eval/LLM_MODELS.md`: drafts on flash, each judge by its measurement."""
    flash_judges = switched["reassessment"] and switched["strict_check"]
    return {
        "draft": FAST_MODEL,
        "relevance_judge": FAST_MODEL if switched["relevance_judge"] else STRONG_MODEL,
        "reassessment": FAST_MODEL if switched["reassessment"] else STRONG_MODEL,
        "strict_check": FAST_MODEL if switched["strict_check"] else STRONG_MODEL,
        "answer_judge": FAST_MODEL if flash_judges else STRONG_MODEL,
    }


# --- run -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Replay:
    """A pro judge request of a dev candidate, its cached answer, and flash's."""

    cid: str
    request: Request
    pro: Payload
    flash: Payload


def cached_requests(system: str) -> list[tuple[Request, str]]:
    """Every cached pro request with this system prompt, and its raw answer."""
    out = []
    for path in sorted(CACHE.rglob("*")):
        if not path.is_file():
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        request = Request(**record["request"])
        if request.system == system and request.model == STRONG_MODEL:
            out.append((request, record["content"]))
    return out


def _parse(content: str) -> Payload:
    try:
        return parse_json_object(content)
    except LlmError:
        return None


def replay(
    llm: JsonLlm, task: Task, by_question: Mapping[str, Candidate], workers: int
) -> list[Replay]:
    """Replay with flash the pro requests of dev candidates (one per candidate)."""
    chosen: dict[str, tuple[Request, str]] = {}
    for request, content in cached_requests(task.system):
        match = task.question.match(request.user)
        cand = by_question.get(match.group(1)) if match else None
        if cand is None or cand.split != "dev":
            continue
        if cand.id in chosen:
            raise SystemExit(f"{task.role}: two cached pro requests for {cand.id}")
        chosen[cand.id] = (request, content)

    def one(cid: str) -> Replay:
        request, content = chosen[cid]
        flash_request = request.model_copy(update={"model": FAST_MODEL})
        try:
            flash: Payload = llm.complete_json(flash_request)
        except LlmError:
            flash = None
        return Replay(cid=cid, request=request, pro=_parse(content), flash=flash)

    return _parallel(one, sorted(chosen), workers)


def measure(task: Task, replays: Sequence[Replay]) -> dict[str, Any]:
    """Kappa, interval, agreement, confusion and disagreements for each decision of a task."""
    per_decision: dict[str, list[list[tuple[str, str]]]] = {}
    disagreements: list[dict[str, str]] = []
    for r in replays:
        pro = task.decisions(r.pro, r.request.user)
        flash = task.decisions(r.flash, r.request.user)
        sections = shown_sections(r.request.user)
        for name, labels in pro.items():
            pairs = list(zip(labels, flash[name], strict=True))
            per_decision.setdefault(name, []).append(pairs)
            for n, (a, b) in enumerate(pairs):
                if a != b:
                    unit = f"{sections[n][0]} {sections[n][1]}" if name == "section" else ""
                    disagreements.append(
                        {"id": r.cid, "decision": name, "unit": unit, "pro": a, "flash": b}
                    )
    decisions: dict[str, Any] = {}
    for name, by_item in per_decision.items():
        classes = sorted({label for units in by_item for pair in units for label in pair})
        per_item = confusions(by_item, classes)
        total = per_item.sum(axis=0)
        decisions[name] = {
            "units": int(total.sum()),
            "kappa": round(kappa(total), 4),
            "ci95": bootstrap_kappa(per_item),
            "agreement": round(float(np.trace(total)) / float(total.sum()), 4),
            "confusion": {
                f"{pro}->{flash}": int(total[i, j])
                for i, pro in enumerate(classes)
                for j, flash in enumerate(classes)
                if total[i, j]
            },
        }
    switch = all(d["kappa"] >= THRESHOLD for d in decisions.values())
    unusable = {
        "pro": sum(r.pro is None for r in replays),
        "flash": sum(r.flash is None for r in replays),
    }
    return {
        "items": len(replays),
        "unusable": unusable,
        "decisions": decisions,
        "switch": switch,
        "disagreements": disagreements,
    }


def render(result: Mapping[str, Any]) -> str:
    """Markdown report."""
    lines = [
        "# Judges: deepseek-flash against deepseek-v4-pro (dev split)",
        "",
        f"Protocol and rule: [`eval/LLM_MODELS.md`](../LLM_MODELS.md). Rule: a judge switches "
        f"to flash if kappa ≥ {result['threshold']:.2f} on every decision it feeds to code.",
        "",
        "| Judge | Items | Decision | Units | Kappa | 95 % CI | Agreement | Flash? |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for role, task in result["tasks"].items():
        for name, d in task["decisions"].items():
            lines.append(
                f"| {role} | {task['items']} | {name} | {d['units']} | {d['kappa']:.3f} | "
                f"{d['ci95'][0]:.3f} to {d['ci95'][1]:.3f} | {d['agreement']:.1%} | "
                f"{'yes' if task['switch'] else 'no'} |"
            )
    lines += ["", "## Models chosen", ""]
    lines += [f"- `{role}`: `{model}`" for role, model in result["models"].items()]
    usage = result["usage"]
    lines += [
        "",
        f"Flash replay: {usage['calls']} calls, {usage['prompt_tokens']} input and "
        f"{usage['completion_tokens']} output tokens, about {usage['cost_usd'] or 0:.2f} $ "
        f"(price at run time). Unusable answers (not JSON after a retry): "
        + ", ".join(
            f"{role} pro {t['unusable']['pro']} / flash {t['unusable']['flash']}"
            for role, t in result["tasks"].items()
        )
        + ".",
        "",
        "## Disagreements",
        "",
    ]
    for role, task in result["tasks"].items():
        counts = Counter(
            f"{d['decision']}: {d['pro']}->{d['flash']}" for d in task["disagreements"]
        )
        lines.append(f"### {role} ({len(task['disagreements'])})")
        lines.append("")
        lines += [f"- {k}: {v}" for k, v in sorted(counts.items())]
        lines.append("")
        for d in task["disagreements"]:
            unit = f" — {d['unit']}" if d["unit"] else ""
            lines.append(f"- {d['id']} `{d['decision']}`{unit}: pro {d['pro']}, flash {d['flash']}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--dry-run", action="store_true", help="count the dev requests to replay, call nothing"
    )
    args = parser.parse_args(argv)

    candidates = read_jsonl(CANDIDATES, Candidate)
    by_question = {c.question: c for c in candidates}
    if len(by_question) != len(candidates):
        raise SystemExit("two candidates share a question: cannot match cached requests")
    if args.dry_run:
        for task in TASKS:
            found = Counter(
                by_question[m.group(1)].split
                for r, _ in cached_requests(task.system)
                if (m := task.question.match(r.user)) and m.group(1) in by_question
            )
            print(f"{task.role}: {dict(found)}")
        return 0
    llm = DeepSeekJsonLlm(DiskCache(CACHE))
    tasks: dict[str, Any] = {}
    for task in TASKS:
        replays = replay(llm, task, by_question, args.workers)
        tasks[task.role] = measure(task, replays)
        print(f"{task.role}: {len(replays)} items, switch={tasks[task.role]['switch']}")
    usage: dict[str, Any] = llm.usage.model_dump()
    cost = cost_usd(
        FAST_MODEL,
        input_tokens=usage["prompt_tokens"],
        output_tokens=usage["completion_tokens"],
        cache_hit_tokens=usage["prompt_cache_hit_tokens"],
    )
    usage["cost_usd"] = round(cost, 4) if cost is not None else None
    result = {
        "protocol": "eval/LLM_MODELS.md",
        "split": "dev",
        "pro": STRONG_MODEL,
        "flash": FAST_MODEL,
        "threshold": THRESHOLD,
        "tasks": tasks,
        "models": decide({role: t["switch"] for role, t in tasks.items()}),
        "usage": usage,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT.with_suffix(".md").write_text(render(result) + "\n", encoding="utf-8")
    print(json.dumps(result["models"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
