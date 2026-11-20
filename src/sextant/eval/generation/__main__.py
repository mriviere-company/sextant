r"""Generate evaluation candidates: `python -m sextant.eval.generation <stage>`.

Stages, each reading the previous one's file in `eval/dataset/work/`:

    ideas     draft ideas per article, per linked pair, out of scope  → ideas.jsonl
    plan      select ideas, assign languages and styles                → plan.jsonl
    realize   write each question in its language                      → realized.jsonl
    judge     pool sections over every strategy, LLM relevance judge   → judgements.jsonl
    assemble  flags, frozen split, review order                        → ../candidates.jsonl
    all       every stage in order

LLM answers are cached in `eval/.llm-cache/` (git-ignored): re-running a stage
replays the cache. `DEEPSEEK_API_KEY` must be set; `judge` also needs the
PostgreSQL index (`make index`).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path

from sextant.eval.generation.models import (
    Assignment,
    Candidate,
    Idea,
    Judgement,
    Realized,
    read_jsonl,
    write_jsonl,
)
from sextant.eval.generation.pipeline import (
    POOL_STRATEGIES,
    Wiki,
    assemble,
    draft_ideas,
    judge,
    pool_sections,
    realize,
)
from sextant.eval.generation.select import assign_languages, select_ideas
from sextant.llm import DeepSeekJsonLlm, DiskCache

ROOT = Path(__file__).resolve().parents[4]
DATASET = ROOT / "eval" / "dataset"
WORK = DATASET / "work"
CANDIDATES = DATASET / "candidates.jsonl"
CACHE = ROOT / "eval" / ".llm-cache"
STAGES = ("ideas", "plan", "realize", "judge", "assemble")


def _summary(candidates: list[Candidate]) -> dict[str, object]:
    return {
        "candidates": len(candidates),
        "by_lang": dict(sorted(Counter(c.lang for c in candidates).items())),
        "by_kind": dict(sorted(Counter(c.kind for c in candidates).items())),
        "by_split": dict(sorted(Counter(c.split for c in candidates).items())),
        "cross_lingual": sum(c.corpus_lang is not None for c in candidates),
        "flagged": dict(sorted(Counter(f for c in candidates for f in c.flags).items())),
        "with_judge_additions": sum(bool(c.judge_added) for c in candidates),
    }


def run(stage: str, workers: int) -> None:
    """Run one stage."""
    wiki = Wiki.load(ROOT / "corpus" / "wiki")
    needs_llm = stage in ("ideas", "realize", "judge")
    llm = DeepSeekJsonLlm(DiskCache(CACHE)) if needs_llm else None

    if stage == "ideas":
        assert llm is not None
        ideas = draft_ideas(llm, wiki, workers)
        write_jsonl(WORK / "ideas.jsonl", ideas)
        print(f"ideas: {len(ideas)}", dict(Counter(f"{i.kind}/{i.origin}" for i in ideas)))
    elif stage == "plan":
        ideas = read_jsonl(WORK / "ideas.jsonl", Idea)
        selected, shortfall = select_ideas(ideas)
        plan = assign_languages(selected)
        write_jsonl(WORK / "plan.jsonl", plan)
        print(f"plan: {len(plan)} assignments; shortfall: {shortfall or 'none'}")
    elif stage == "realize":
        assert llm is not None
        ideas_by_id = {i.id: i for i in read_jsonl(WORK / "ideas.jsonl", Idea)}
        plan = read_jsonl(WORK / "plan.jsonl", Assignment)
        realized = realize(llm, wiki, ideas_by_id, plan, workers)
        write_jsonl(WORK / "realized.jsonl", realized)
        print(f"realized: {len(realized)} / {len(plan)}")
    elif stage == "judge":
        assert llm is not None
        from sextant.eval.retrieval_bench import section_map  # noqa: PLC0415 — DB stack
        from sextant.retrieval.base import load_chunks  # noqa: PLC0415
        from sextant.retrieval.factory import RetrievalContext  # noqa: PLC0415

        ideas_by_id = {i.id: i for i in read_jsonl(WORK / "ideas.jsonl", Idea)}
        realized = read_jsonl(WORK / "realized.jsonl", Realized)
        chunks = load_chunks()
        context = RetrievalContext(chunks)
        retrievers = [context.build(spec) for spec in POOL_STRATEGIES]
        sections = section_map(chunks)
        pools = {
            r.idea_id: pool_sections(r.question, r.corpus_lang or r.lang, retrievers, sections)
            for r in realized
        }
        entries = [(r, ideas_by_id[r.idea_id], pools[r.idea_id]) for r in realized]
        judgements = judge(llm, wiki, entries, workers)
        write_jsonl(WORK / "judgements.jsonl", judgements)
        sizes = sorted(len(j.pooled) for j in judgements)
        median = sizes[len(sizes) // 2]
        print(f"judged: {len(judgements)} / {len(realized)}; median pool {median} sections")
    elif stage == "assemble":
        ideas_by_id = {i.id: i for i in read_jsonl(WORK / "ideas.jsonl", Idea)}
        realized = read_jsonl(WORK / "realized.jsonl", Realized)
        verdicts = {j.idea_id: j for j in read_jsonl(WORK / "judgements.jsonl", Judgement)}
        candidates = assemble(ideas_by_id, realized, verdicts)
        write_jsonl(CANDIDATES, candidates)
        print(json.dumps(_summary(candidates), indent=1))
    if llm is not None:
        print(f"usage: {llm.usage.model_dump()}")


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("stage", choices=(*STAGES, "all"))
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    for stage in STAGES if args.stage == "all" else (args.stage,):
        run(stage, args.workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
