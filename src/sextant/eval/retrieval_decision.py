r"""Apply the decision rules of `eval/PROTOCOL.md` to dev results.

Run with `python -m sextant.eval.retrieval_decision <results files>`.

The rules were written before any run; this module applies them mechanically,
so the chosen configuration follows from committed results files and not from
someone reading the numbers. It reads one or more results files of
`retrieval_bench` (the benchmark runs in stages, because which hybrid and
which reranker to measure depends on earlier decisions), compares strategies
pairwise with the paired bootstrap on nDCG@10 over the monolingual answerable
questions, and either reaches the final configuration or names the strategies
to run next.

Rules as coded (wording of the protocol, made procedural):
1. Dense model: start from the smallest model; each larger one, in size order,
   replaces the current one if it beats it by >= 0.02 nDCG@10, significant.
4. pg_fts replaces bm25 as the lexical strategy if it beats it by >= 0.01,
   significant (rule 2's threshold).
2. The best single strategy is the better of the lexical strategy and the
   chosen dense model; hybrid:<chosen model> (RRF of bm25 and that model)
   replaces it if it beats it by >= 0.01, significant.
3. Each reranking variant over the first stage qualifies if it adds >= 0.03,
   significant, with a p95 latency <= 500 ms; if both qualify, the top-10
   variant wins unless the top-30 one beats it by a further >= 0.02, significant.
5. In every language with at least 15 monolingual questions, the chosen
   configuration is compared with bm25; a loss >= 0.05 nDCG@10 is a finding.

Usage:
    uv run python -m sextant.eval.retrieval_decision eval/results/retrieval_dev_*.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sextant.eval.metrics import paired_bootstrap

METRIC = "ndcg@10"
DENSE_BY_SIZE = ("dense:minilm", "dense:mpnet", "dense:e5-large")
DENSE_GAIN = 0.02
HYBRID_GAIN = 0.01
RERANK_GAIN = 0.03
RERANK_TIE_GAIN = 0.02
RERANK_P95_MS = 500.0
LANGUAGE_LOSS = 0.05
LANGUAGE_MIN_N = 15
RERANKER = "bge-m3"


class Pending(Exception):  # noqa: N818 — a state, not an error
    """The next rule needs strategies that have not been run yet."""

    def __init__(self, specs: Sequence[str]) -> None:
        super().__init__(", ".join(specs))
        self.specs = list(specs)


def merge(reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Union of the strategies of several results files of the same split."""
    splits = {r["meta"]["split"] for r in reports}
    if len(splits) != 1:
        raise ValueError(f"results from several splits: {sorted(splits)}")
    merged: dict[str, Any] = {}
    for report in reports:
        merged.update(report["results"])
    return merged


def _compare(results: Mapping[str, Any], base: str, other: str) -> dict[str, Any]:
    missing = [s for s in (base, other) if s not in results]
    if missing:
        raise Pending(missing)
    a, b = results[base]["per_question"], results[other]["per_question"]
    if set(a) != set(b):
        raise ValueError(f"{base} and {other} were not run on the same questions")
    ids = sorted(a)
    delta, low, high = paired_bootstrap([a[i][METRIC] for i in ids], [b[i][METRIC] for i in ids])
    return {
        "baseline": base,
        "candidate": other,
        "metric": METRIC,
        "n": len(ids),
        "delta": round(delta, 4),
        "ci95": [round(low, 4), round(high, 4)],
        "significant": low > 0 or high < 0,
    }


def _wins(comparison: Mapping[str, Any], gain: float) -> bool:
    return bool(comparison["delta"] >= gain and comparison["ci95"][0] > 0)


def decide(results: Mapping[str, Any]) -> dict[str, Any]:
    """Apply rules 1, 4, 2, 3 and 5 in order; stop at the first one missing results."""
    steps: list[dict[str, Any]] = []
    state: dict[str, Any] = {"steps": steps}
    try:
        # Rule 1 — dense model
        dense = DENSE_BY_SIZE[0]
        for larger in DENSE_BY_SIZE[1:]:
            comparison = _compare(results, dense, larger)
            adopted = _wins(comparison, DENSE_GAIN)
            steps.append({"rule": 1, **comparison, "threshold": DENSE_GAIN, "adopted": adopted})
            if adopted:
                dense = larger
        state["dense"] = dense

        # Rule 4 — lexical strategy
        comparison = _compare(results, "bm25", "pg_fts")
        adopted = _wins(comparison, HYBRID_GAIN)
        steps.append({"rule": 4, **comparison, "threshold": HYBRID_GAIN, "adopted": adopted})
        lexical = "pg_fts" if adopted else "bm25"
        state["lexical"] = lexical

        # Rule 2 — hybrid over the best single strategy
        best_single = max((lexical, dense), key=lambda s: results[s]["overall"][METRIC])
        hybrid = f"hybrid:{dense.removeprefix('dense:')}"
        comparison = _compare(results, best_single, hybrid)
        adopted = _wins(comparison, HYBRID_GAIN)
        steps.append({"rule": 2, **comparison, "threshold": HYBRID_GAIN, "adopted": adopted})
        first_stage = hybrid if adopted else best_single
        state["first_stage"] = first_stage

        # Rule 3 — reranking variants
        variants = {
            30: f"rerank:{RERANKER}:{first_stage}",
            10: f"rerank:{RERANKER}@10:{first_stage}",
        }
        qualified: dict[int, bool] = {}
        for depth, spec in variants.items():
            comparison = _compare(results, first_stage, spec)
            p95 = float(results[spec]["latency_ms"]["p95"])
            ok = _wins(comparison, RERANK_GAIN) and p95 <= RERANK_P95_MS
            qualified[depth] = ok
            steps.append(
                {
                    "rule": 3,
                    **comparison,
                    "threshold": RERANK_GAIN,
                    "p95_ms": p95,
                    "p95_limit_ms": RERANK_P95_MS,
                    "adopted": ok,
                }
            )
        final = first_stage
        if qualified[30] and qualified[10]:
            tie = _compare(results, variants[10], variants[30])
            deeper = _wins(tie, RERANK_TIE_GAIN)
            steps.append({"rule": 3, **tie, "threshold": RERANK_TIE_GAIN, "adopted": deeper})
            final = variants[30] if deeper else variants[10]
        elif qualified[30] or qualified[10]:
            final = variants[30] if qualified[30] else variants[10]
        state["final"] = final

        # Rule 5 — no language left behind
        chosen, base = results[final]["by_lang"], results["bm25"]["by_lang"]
        languages = []
        for lang in sorted(base):
            n = int(base[lang]["n"])
            loss = round(base[lang][METRIC] - chosen[lang][METRIC], 4)
            applies = n >= LANGUAGE_MIN_N
            languages.append(
                {
                    "lang": lang,
                    "n": n,
                    "loss_vs_bm25": loss,
                    "rule_applies": applies,
                    "finding": applies and loss >= LANGUAGE_LOSS,
                }
            )
        state["languages"] = languages
    except Pending as pending:
        state["pending"] = pending.specs
    return state


def render(decision: Mapping[str, Any], sources: Sequence[str]) -> str:
    """Markdown summary of a decision."""
    lines = [
        "# Retrieval decision — dev split",
        "",
        "Sources: " + ", ".join(f"`{s}`" for s in sources),
        "",
    ]
    lines += [
        "| Rule | Baseline | Candidate | Δ nDCG@10 | 95 % CI | Threshold | p95 ms | Adopted |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in decision["steps"]:
        p95 = f"{s['p95_ms']:.0f}" if "p95_ms" in s else "—"
        lines.append(
            f"| {s['rule']} | `{s['baseline']}` | `{s['candidate']}` | {s['delta']:+.3f} | "
            f"[{s['ci95'][0]:+.3f}, {s['ci95'][1]:+.3f}] | ≥ {s['threshold']:.2f} | {p95} | "
            f"{'yes' if s['adopted'] else 'no'} |"
        )
    if "pending" in decision:
        lines += ["", "**Pending:** run " + ", ".join(f"`{s}`" for s in decision["pending"]) + "."]
        return "\n".join(lines) + "\n"
    lines += ["", f"**Chosen configuration: `{decision['final']}`**", ""]
    lines += ["| Language | n | Loss vs bm25 | Rule 5 applies | Finding |", "|---|---|---|---|---|"]
    for row in decision["languages"]:
        lines.append(
            f"| {row['lang']} | {row['n']} | {row['loss_vs_bm25']:+.3f} | "
            f"{'yes' if row['rule_applies'] else f'no (n < {LANGUAGE_MIN_N})'} | "
            f"{'yes' if row['finding'] else 'no'} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("results", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=Path("eval/results/retrieval_decision.json"))
    args = parser.parse_args(argv)
    reports = [json.loads(p.read_text(encoding="utf-8")) for p in args.results]
    if any(r["meta"]["split"] != "dev" for r in reports):
        raise SystemExit("decisions are taken on the dev split only")
    decision = decide(merge(reports))
    sources = [str(p) for p in args.results]
    out = {"sources": sources, **decision}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown = render(decision, sources)
    args.out.with_suffix(".md").write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
