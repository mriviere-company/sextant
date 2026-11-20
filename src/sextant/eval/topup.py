r"""Top up unanswerable questions on a new wiki: `python -m sextant.eval.topup`.

Step 4 of `eval/dataset/MIGRATION_V2.md`. When the rewritten wiki answers former
unanswerable questions, the set loses its measure of refusal; this drafts new ones against
the current wiki (the FAQ included), keeps only those that the pooled sections do not answer,
both as drafted in French and as written in their target language, and appends them to the
candidates with new ids. Their split is frozen now: the split their article already has, or
the side that keeps the language balanced for questions outside any article.

Usage: `uv run python -m sextant.eval.topup --per-lang 7` (needs DEEPSEEK_API_KEY and the index).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import random
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sextant.eval.dataset import SectionRef, Split
from sextant.eval.generation.models import Assignment, Candidate, Idea, read_jsonl, write_jsonl
from sextant.eval.generation.pipeline import (
    POOL_STRATEGIES,
    Wiki,
    _parallel,
    judge,
    pool_sections,
    realize,
)
from sextant.eval.generation.prompts import PROMPT_VERSION
from sextant.eval.generation.select import review_order
from sextant.llm import DeepSeekJsonLlm, DiskCache, JsonLlm, LlmError, Request, model_for
from sextant.models import LANGS, Lang
from sextant.retrieval.base import Retriever

ROOT = Path(__file__).resolve().parents[3]
CANDIDATES = ROOT / "eval" / "dataset" / "candidates.jsonl"
WORK = ROOT / "eval" / "dataset" / "work" / "v2"
CACHE = ROOT / "eval" / ".llm-cache"
TRIED = WORK / "topup_tried.json"
OUT_OF_SCOPE_SHARE = 0.25

ARTICLE_SYSTEM = """Tu aides à construire le jeu d'évaluation d'un assistant qui répond aux \
questions des joueurs d'Area Universe à partir du wiki du jeu. On te donne un article du wiki \
ACTUEL. Propose 3 questions, en français, qu'un joueur poserait naturellement sur ce sujet, \
mais auxquelles l'article ne répond pas, même partiellement : un détail, un chiffre, un \
mécanisme qu'il ne donne pas. Pas de piège, pas de hors-sujet, rien qui se déduise de \
l'article. Formulation simple, comme un joueur, autonome (jamais « selon le wiki »).
Format JSON : {"ideas": [{"question": "…", "answer": "ce que l'article dit de proche et ce \
qui manque, en une phrase"}]}"""

SCOPE_SYSTEM = """Tu aides à construire le jeu d'évaluation d'un assistant qui répond aux \
questions des joueurs d'Area Universe à partir du wiki du jeu. Voici la liste des articles du \
wiki actuel (titre et résumé), dont une FAQ. Propose le nombre de questions demandé, en \
français, qu'un joueur pourrait réellement poser à l'aide du jeu mais auxquelles AUCUN article \
ne répond. La FAQ couvre désormais : jouer sur plusieurs serveurs, hors ligne, appareils, \
langues, pseudo, contact, bugs, achats et remboursements, compte supprimé, suppression des \
rapports ; évite ces sujets. Pas de question hors du jeu.
Format JSON : {"ideas": [{"question": "…", "answer": "pourquoi le wiki ne répond pas"}]}"""


def _ideas(payload: Mapping[str, Any], prefix: str, slug: str) -> list[Idea]:
    raw = payload.get("ideas")
    out = []
    for n, entry in enumerate(raw if isinstance(raw, list) else []):
        if isinstance(entry, dict) and isinstance(entry.get("question"), str):
            question = " ".join(entry["question"].split())
            if len(question) >= 8:
                out.append(
                    Idea(
                        id=f"{prefix}.{n}",
                        origin="article" if slug else "out_of_scope",
                        slug=slug,
                        kind="unanswerable",
                        question=question,
                        answer=" ".join(str(entry.get("answer", "")).split()),
                    )
                )
    return out


def draft(llm: JsonLlm, wiki: Wiki, n_scope: int, workers: int) -> list[Idea]:
    """Unanswerable ideas per article and out of scope, drafted in French."""

    def per_article(slug: str) -> list[Idea] | None:
        request = Request(
            model=model_for("draft"),
            system=ARTICLE_SYSTEM,
            user=wiki.render_article("fr", slug),
            max_tokens=1200,
            temperature=0.7,
        )
        try:
            return _ideas(llm.complete_json(request), f"v2u.{slug}", slug)
        except LlmError:
            return None

    ideas = [i for group in _parallel(per_article, wiki.order, workers) for i in group]
    catalogue = "\n".join(
        f"- {a.title} : {a.summary}" for a in (wiki.article("fr", s) for s in wiki.order)
    )
    request = Request(
        model=model_for("draft"),
        system=SCOPE_SYSTEM,
        user=f"{catalogue}\n\nNombre de questions : {n_scope}",
        max_tokens=2500,
        temperature=0.7,
    )
    with contextlib.suppress(LlmError):
        ideas += _ideas(llm.complete_json(request), "v2u.oos", "")
    return ideas


def unanswered(
    llm: JsonLlm,
    wiki: Wiki,
    asked: Sequence[tuple[str, str, Lang]],
    retrievers: Sequence[Retriever],
    sections: Mapping[str, SectionRef],
) -> set[str]:
    """Ids whose question no pooled section answers, according to the relevance judge."""
    from sextant.eval.generation.models import Realized  # noqa: PLC0415

    entries = []
    for key, question, lang in asked:
        pool = pool_sections(question, lang, retrievers, sections)
        realized = Realized(
            idea_id=key,
            lang=lang,
            style="natural",
            question=question,
            answer="",
            question_fr=question,
            answer_fr="",
        )
        stub = Idea(
            id=key, origin="out_of_scope", kind="unanswerable", question=question, answer=""
        )
        entries.append((realized, stub, pool))
    verdicts = judge(llm, wiki, entries)
    return {v.idea_id for v in verdicts if not v.relevant and not v.answerable}


def assign_split(slug: str, lang: Lang, splits: Mapping[str, Split], counts: Counter[str]) -> Split:
    """Return the article's split if it has one, else the side with fewer questions in `lang`."""
    if slug in splits:
        return splits[slug]
    return "dev" if counts[f"{lang}/dev"] <= counts[f"{lang}/test"] else "test"


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0915 — a linear pipeline
    """Entry point."""
    from sextant.eval.retrieval_bench import section_map  # noqa: PLC0415 — DB stack
    from sextant.retrieval.base import load_chunks  # noqa: PLC0415
    from sextant.retrieval.factory import RetrievalContext  # noqa: PLC0415

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--per-lang", type=int, default=7, help="unanswerable target per language")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    candidates = read_jsonl(CANDIDATES, Candidate)
    # ideas already written into a language (kept or rejected by the second judge) are not
    # drawn again, so the stage can be re-run to fill the slots a first run left empty
    tried: set[str] = set()
    if TRIED.exists():
        tried = set(json.loads(TRIED.read_text(encoding="utf-8")))
    live = [c for c in candidates if c.status != "rejected"]
    have = Counter(c.lang for c in live if c.kind == "unanswerable")
    need = {lang: max(0, args.per_lang - have[lang]) for lang in LANGS}
    total = sum(need.values())
    print(f"unanswerable per language now: {dict(have)}; drafting {total}: {need}")
    if not total:
        return 0

    wiki = Wiki.load(ROOT / "corpus" / "wiki")
    chunks = load_chunks()
    context = RetrievalContext(chunks)
    retrievers = [context.build(spec) for spec in POOL_STRATEGIES]
    sections = section_map(chunks)
    llm = DeepSeekJsonLlm(DiskCache(CACHE))
    rng = random.Random(args.seed)

    ideas = draft(
        llm, wiki, n_scope=max(8, round(total * OUT_OF_SCOPE_SHARE * 2)), workers=args.workers
    )
    kept_ids = unanswered(
        llm, wiki, [(i.id, i.question, "fr") for i in ideas], retrievers, sections
    )
    pool = [i for i in ideas if i.id in kept_ids and i.id not in tried]
    rng.shuffle(pool)
    n_scope = round(total * OUT_OF_SCOPE_SHARE)
    used_articles = Counter(c.slug for c in live if c.kind == "unanswerable")
    scope = [i for i in pool if not i.slug][:n_scope]
    in_article = sorted((i for i in pool if i.slug), key=lambda i: used_articles[i.slug])
    chosen: list[Idea] = []
    seen: set[str] = set()
    for idea in in_article:  # one idea per article first, the least-used articles first
        if len(chosen) + len(scope) >= total:
            break
        if idea.slug not in seen:
            chosen.append(idea)
            seen.add(idea.slug)
    chosen += scope

    slots = [lang for lang in LANGS for _ in range(need[lang])]
    rng.shuffle(slots)
    plan = [
        Assignment(idea_id=i.id, lang=lang, style=rng.choice(["short", "natural", "situated"]))
        for i, lang in zip(chosen, slots, strict=False)
    ]
    by_id = {i.id: i for i in chosen}
    realized = realize(llm, wiki, by_id, plan, args.workers)
    TRIED.write_text(json.dumps(sorted(tried | set(by_id)), indent=1) + "\n", encoding="utf-8")
    still = unanswered(
        llm, wiki, [(r.idea_id, r.question, r.lang) for r in realized], retrievers, sections
    )
    realized = [r for r in realized if r.idea_id in still]

    splits = {c.slug: c.split for c in candidates if c.slug}
    counts: Counter[str] = Counter(f"{c.lang}/{c.split}" for c in live)
    revision = next(c.wiki_revision for c in candidates if c.wiki_revision)
    first = max(c.review_order for c in candidates) + 1
    ordered = review_order(realized, {n: r.lang for n, r in enumerate(realized)}, seed=args.seed)
    new: list[Candidate] = []
    for offset, r in enumerate(ordered):
        idea = by_id[r.idea_id]
        split = assign_split(idea.slug, r.lang, splits, counts)
        counts[f"{r.lang}/{split}"] += 1
        new.append(
            Candidate(
                id=f"q{first + offset:03d}",
                review_order=first + offset,
                split=split,
                lang=r.lang,
                kind="unanswerable",
                origin=idea.origin,
                slug=idea.slug,
                style=r.style,
                question=r.question,
                reference_answer=r.answer,
                question_fr=r.question_fr,
                reference_answer_fr=r.answer_fr,
                relevant=(),
                sources=(),
                idea_id=idea.id,
                prompt_version=PROMPT_VERSION,
                wiki_revision=revision,
                status="to_review",
                reasons=("new_unanswerable",),
            )
        )
    write_jsonl(CANDIDATES, [*candidates, *new])
    write_jsonl(WORK / "topup_ideas.jsonl", ideas)
    print(
        f"added {len(new)}: {dict(Counter(c.lang for c in new))}, "
        f"splits {dict(Counter(c.split for c in new))}"
    )
    print(f"usage {llm.usage.model_dump()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
