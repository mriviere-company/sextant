r"""Retrieval benchmark: `python -m sextant.eval.retrieval_bench`.

Runs several strategies over one split of the evaluation set and writes a
JSON results file (the source of truth for any published figure) and a
Markdown report next to it. Unanswerable questions are counted but excluded
from retrieval metrics: they have no relevant section, and refusal is a
generation concern (phase 4).

Usage:
    uv run python -m sextant.eval.retrieval_bench --split dev \\
        --strategies bm25,pg_fts,dense:minilm,hybrid:minilm --baseline bm25
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from sextant.eval.dataset import EvalItem, SectionRef, Split, load_items
from sextant.eval.metrics import (
    dedupe,
    hit_at_k,
    mean,
    ndcg_at_k,
    paired_bootstrap,
    percentile,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from sextant.models import Chunk
from sextant.retrieval.base import Retriever, load_chunks

ROOT = Path(__file__).resolve().parents[3]
DATASET = ROOT / "eval" / "dataset" / "questions.jsonl"
RESULTS = ROOT / "eval" / "results"
DEPTH = 10
KS = (1, 3, 5, 10)
COMPARED = ("mrr", "ndcg@10", "recall@5")


def score_item(ranked: Sequence[SectionRef], item: EvalItem) -> dict[str, float]:
    """All retrieval metrics of one answerable question."""
    relevant = set(item.relevant)
    scores: dict[str, float] = {"mrr": reciprocal_rank(ranked, relevant)}
    for k in KS:
        scores[f"hit@{k}"] = hit_at_k(ranked, relevant, k)
        scores[f"recall@{k}"] = recall_at_k(ranked, relevant, k)
        scores[f"precision@{k}"] = precision_at_k(ranked, relevant, k)
    scores["ndcg@10"] = ndcg_at_k(ranked, relevant, 10)
    return scores


def _aggregate(rows: Sequence[Mapping[str, float]]) -> dict[str, float]:
    keys = rows[0].keys() if rows else []
    return {key: round(mean([row[key] for row in rows]), 4) for key in keys}


def run_strategy(
    retriever: Retriever,
    items: Sequence[EvalItem],
    section_of: Mapping[str, SectionRef],
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    """Evaluate one strategy; returns aggregates, breakdowns, latencies and per-question scores."""
    per_question: dict[str, dict[str, float]] = {}
    latencies: list[float] = []
    by_lang: defaultdict[str, list[dict[str, float]]] = defaultdict(list)
    by_kind: defaultdict[str, list[dict[str, float]]] = defaultdict(list)
    for item in items:
        if not item.answerable:
            continue
        started = clock()
        hits = retriever.search(item.question, item.lang, DEPTH)
        latencies.append((clock() - started) * 1000)
        ranked = dedupe([section_of[hit.chunk_id] for hit in hits])
        scores = score_item(ranked, item)
        per_question[item.id] = scores
        by_lang[item.lang].append(scores)
        by_kind[item.kind].append(scores)
    rows = list(per_question.values())
    return {
        "overall": _aggregate(rows),
        "by_lang": {lang: _aggregate(r) | {"n": len(r)} for lang, r in sorted(by_lang.items())},
        "by_kind": {kind: _aggregate(r) | {"n": len(r)} for kind, r in sorted(by_kind.items())},
        "latency_ms": {
            "p50": round(percentile(latencies, 50), 2),
            "p95": round(percentile(latencies, 95), 2),
        },
        "per_question": per_question,
    }


def compare(results: Mapping[str, Mapping[str, Any]], baseline: str) -> list[dict[str, Any]]:
    """Paired bootstrap of each strategy against the baseline on the compared metrics."""
    base = results[baseline]["per_question"]
    ids = sorted(base)
    comparisons = []
    for name, result in results.items():
        if name == baseline:
            continue
        other = result["per_question"]
        for metric in COMPARED:
            delta, low, high = paired_bootstrap(
                [base[i][metric] for i in ids], [other[i][metric] for i in ids]
            )
            comparisons.append(
                {
                    "strategy": name,
                    "baseline": baseline,
                    "metric": metric,
                    "delta": round(delta, 4),
                    "ci95": [round(low, 4), round(high, 4)],
                    "significant": low > 0 or high < 0,
                }
            )
    return comparisons


def render_markdown(report: Mapping[str, Any]) -> str:
    """Human-readable summary of a results file."""
    meta = report["meta"]
    lines = [
        f"# Retrieval benchmark — split `{meta['split']}`",
        "",
        f"{meta['answerable']} answerable questions ({meta['questions']} in total), "
        f"top {DEPTH} sections per query. Source: `{meta['results_file']}`.",
        "",
        "| Strategy | MRR | nDCG@10 | Recall@5 | Hit@1 | Hit@5 | p50 ms | p95 ms |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, result in report["results"].items():
        o, lat = result["overall"], result["latency_ms"]
        lines.append(
            f"| `{name}` | {o['mrr']:.3f} | {o['ndcg@10']:.3f} | {o['recall@5']:.3f} | "
            f"{o['hit@1']:.3f} | {o['hit@5']:.3f} | {lat['p50']:.1f} | {lat['p95']:.1f} |"
        )
    if report["comparisons"]:
        lines += [
            "",
            f"## Against `{meta['baseline']}` (paired bootstrap, 95 % CI)",
            "",
            "| Strategy | Metric | Δ | 95 % CI | Significant |",
            "|---|---|---|---|---|",
        ]
        for c in report["comparisons"]:
            significant = "yes" if c["significant"] else "no"
            lines.append(
                f"| `{c['strategy']}` | {c['metric']} | {c['delta']:+.3f} | "
                f"[{c['ci95'][0]:+.3f}, {c['ci95'][1]:+.3f}] | {significant} |"
            )
    return "\n".join(lines) + "\n"


def section_map(chunks: Sequence[Chunk]) -> dict[str, SectionRef]:
    """Chunk id → language-independent section."""
    return {c.id: SectionRef(slug=c.slug, section_index=c.section_index) for c in chunks}


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    from sextant.retrieval.factory import RetrievalContext  # noqa: PLC0415 — needs the DB stack

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--strategies", default="bm25")
    parser.add_argument("--baseline", default="bm25")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    split: Split = args.split
    items = load_items(args.dataset, split)
    chunks = load_chunks()
    context = RetrievalContext(chunks)
    sections = section_map(chunks)
    specs = [s.strip() for s in args.strategies.split(",") if s.strip()]
    results = {spec: run_strategy(context.build(spec), items, sections) for spec in specs}

    out = args.out or RESULTS / f"retrieval_{split}.json"
    report = {
        "meta": {
            "split": split,
            "questions": len(items),
            "answerable": sum(item.answerable for item in items),
            "depth": DEPTH,
            "baseline": args.baseline,
            "results_file": str(out.relative_to(ROOT)) if out.is_relative_to(ROOT) else str(out),
        },
        "results": results,
        "comparisons": compare(results, args.baseline) if args.baseline in results else [],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
