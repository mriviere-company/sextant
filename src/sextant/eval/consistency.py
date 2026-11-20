r"""Check the system's answers against the current wiki: `python -m sextant.eval.consistency`.

Not a quality benchmark (phase 4 builds that): a check that, after the wiki was rewritten,
the served answers no longer repeat facts the wiki dropped or corrected. Each question goes
through the real answer pipeline (`dense:e5-large`, the configured provider); an LLM judge
then compares the answer with current wiki sections (those the answer cites, plus those BM25
and e5-large retrieve for the question) and reports every claim the wiki contradicts, and
refusals where the wiki does hold the answer.

Questions: the probes of `eval/probes/wiki_v2_facts.jsonl` (one per fact the rewrite
changed) and the **dev** split of the candidates. The test split is never used here.

Usage:
    DEEPSEEK_API_KEY=… SEXTANT_LLM_PROVIDER=deepseek uv run python -m sextant.eval.consistency
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from sextant.eval.dataset import SectionRef
from sextant.eval.generation.models import Candidate, read_jsonl
from sextant.eval.generation.pipeline import Wiki, _parallel, pool_sections
from sextant.generation.answer import AnswerResult, AnswerService
from sextant.generation.budget import Deadline
from sextant.llm import DeepSeekJsonLlm, DiskCache, JsonLlm, LlmError, Request, model_for
from sextant.models import Chunk, Lang

ROOT = Path(__file__).resolve().parents[3]
PROBES = ROOT / "eval" / "probes" / "wiki_v2_facts.jsonl"
CANDIDATES = ROOT / "eval" / "dataset" / "candidates.jsonl"
OUT = ROOT / "eval" / "results" / "v2_answer_consistency.json"
CACHE = ROOT / "eval" / ".llm-cache"

Verdict = Literal["consistent", "contradicted", "unsupported", "correct_refusal", "missed_answer"]

JUDGE_SYSTEM = """You check an answer given by a question-answering system about the game Area \
Universe against the CURRENT wiki sections below (S1, S2…). The sections are the only truth.

Return one JSON object:
{"verdict": "consistent"|"contradicted"|"unsupported"|"correct_refusal"|"missed_answer",
 "contradictions": [{"claim": "<the answer's words>", "wiki": "<short quote of the sections>"}],
 "note": "<one short sentence in French, or empty>"}

- "contradicted": at least one claim of the answer disagrees with the sections (a number, \
time, name, cost, condition, outcome or rule differs). List every such claim.
- "unsupported": nothing contradicts the sections, but some claim is not in them.
- "consistent": every claim of the answer is supported by the sections.
- "correct_refusal": the answer says the wiki does not cover it, and the sections indeed do \
not answer the question.
- "missed_answer": the answer refuses, but the sections do answer the question."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Probe(_Frozen):
    """A question about a fact the rewrite changed, with that fact for the report."""

    id: str
    lang: Lang
    question: str
    expected: str


class Check(_Frozen):
    """One answer and the judge's verdict on it."""

    id: str
    source: Literal["probe", "dev"]
    lang: Lang
    question: str
    answer: str
    refused: bool
    cited: tuple[str, ...]
    verdict: Verdict
    contradictions: tuple[dict[str, str], ...] = ()
    note: str = ""
    expected: str = ""


def parse_verdict(payload: Mapping[str, Any]) -> tuple[Verdict, tuple[dict[str, str], ...], str]:
    """Validate the judge's answer; an unknown verdict counts as a contradiction to look at."""
    allowed = ("consistent", "contradicted", "unsupported", "correct_refusal", "missed_answer")
    raw = payload.get("verdict")
    verdict: Verdict = raw if raw in allowed else "contradicted"
    items = payload.get("contradictions")
    contradictions = tuple(
        {"claim": str(c.get("claim", "")), "wiki": str(c.get("wiki", ""))}
        for c in (items if isinstance(items, list) else [])
        if isinstance(c, dict)
    )
    note = payload.get("note")
    return verdict, contradictions, note if isinstance(note, str) else ""


def judge_answer(
    llm: JsonLlm,
    wiki: Wiki,
    asked: tuple[str, Lang],
    result: AnswerResult,
    pool: Sequence[SectionRef],
) -> tuple[Verdict, tuple[dict[str, str], ...], str]:
    """Ask the judge whether the answer to `asked` (question, language) agrees with the wiki."""
    question, lang = asked
    shown = sorted(set(pool), key=lambda r: (wiki.order.index(r.slug), r.section_index))
    sections = "\n\n".join(wiki.render_section(lang, r, f"S{n}") for n, r in enumerate(shown, 1))
    user = (
        f"Question ({lang}): {question}\n\nAnswer: {result.answer}\n"
        f"(the system {'refused' if result.refused else 'answered'})\n\n"
        f"Current wiki sections:\n\n{sections}"
    )
    request = Request(
        model=model_for("answer_judge"),
        system=JUDGE_SYSTEM,
        user=user,
        max_tokens=1200,
        temperature=0.0,
    )
    try:
        return parse_verdict(llm.complete_json(request))
    except LlmError as error:
        return "contradicted", (), f"juge illisible : {error}"


def render(checks: Sequence[Check]) -> str:
    """Markdown report: counts, then every contradiction and missed answer."""
    lines = ["# Answers against wiki v2", ""]
    for source in ("probe", "dev"):
        group = [c for c in checks if c.source == source]
        counts = Counter(c.verdict for c in group)
        lines.append(
            f"- **{source}** ({len(group)}): "
            + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
        )
    flagged = [c for c in checks if c.verdict in ("contradicted", "missed_answer")]
    lines += ["", f"## Flagged ({len(flagged)})", ""]
    for c in flagged:
        lines.append(f"### `{c.id}` ({c.source}, {c.lang}) — {c.verdict}")
        lines += ["", f"Question: {c.question}", "", f"Answer: {c.answer}", ""]
        if c.expected:
            lines += [f"Expected (wiki v2): {c.expected}", ""]
        for item in c.contradictions:
            lines.append(f"- « {item['claim']} » — wiki: « {item['wiki']} »")
        if c.note:
            lines += ["", f"Note: {c.note}"]
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    from sextant.eval.retrieval_bench import section_map  # noqa: PLC0415 — DB stack
    from sextant.generation.providers import provider_from_env  # noqa: PLC0415
    from sextant.retrieval.base import load_chunks  # noqa: PLC0415
    from sextant.retrieval.factory import RetrievalContext  # noqa: PLC0415

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    chunks = load_chunks()
    by_id: dict[str, Chunk] = {c.id: c for c in chunks}
    context = RetrievalContext(chunks)
    dense = context.build("dense:e5-large")
    pools = [context.bm25, dense]
    sections = section_map(chunks)
    provider = provider_from_env()
    service = AnswerService(dense, by_id, provider)
    wiki = Wiki.load(ROOT / "corpus" / "wiki")
    llm = DeepSeekJsonLlm(DiskCache(CACHE))

    questions: list[tuple[str, Literal["probe", "dev"], Lang, str, str]] = [
        (p.id, "probe", p.lang, p.question, p.expected) for p in read_jsonl(PROBES, Probe)
    ]
    questions += [
        (c.id, "dev", c.lang, c.question, "")
        for c in read_jsonl(CANDIDATES, Candidate)
        if c.split == "dev" and c.status != "rejected" and c.corpus_lang is None
    ]

    def one(entry: tuple[str, Literal["probe", "dev"], Lang, str, str]) -> Check | None:
        qid, source, lang, question, expected = entry
        try:
            result = service.answer(question, lang, 5, Deadline(60.0))
        except Exception as error:  # one failed question must not stop the run
            print(f"{qid}: {error}", file=sys.stderr)
            return None
        cited = [sections[c.chunk_id] for c in result.citations]
        pool = [*pool_sections(question, lang, pools, sections, depth=5), *cited]
        verdict, contradictions, note = judge_answer(llm, wiki, (question, lang), result, pool)
        return Check(
            id=qid,
            source=source,
            lang=lang,
            question=question,
            answer=result.answer,
            refused=result.refused,
            cited=tuple(c.chunk_id for c in result.citations),
            verdict=verdict,
            contradictions=contradictions,
            note=note,
            expected=expected,
        )

    checks = _parallel(one, questions, args.workers)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "wiki_revision": (ROOT / "corpus" / "wiki" / "SOURCE_REVISION").read_text().split()[0],
        "provider": provider.name,
        "model": provider.model,
        "checks": [c.model_dump(mode="json") for c in checks],
    }
    args.out.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    args.out.with_suffix(".md").write_text(render(checks), encoding="utf-8")
    print(render(checks)[:4000])
    print(f"judge usage: {llm.usage.model_dump()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
