"""The stages of question generation, each a function of the previous stage's output.

The LLM sits behind `JsonLlm`, so every stage runs with a scripted fake in
the tests. Calls of one stage run in parallel; a call that fails (bad JSON
twice, truncated answer) drops its item and is counted, never retried
silently with different parameters.
"""

from __future__ import annotations

import logging
import random
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast, get_args

from sextant.eval.dataset import Kind, SectionRef
from sextant.eval.generation.models import (
    Assignment,
    Candidate,
    Idea,
    Judgement,
    Realized,
)
from sextant.eval.generation.prompts import (
    CROSS_SYSTEM,
    IDEAS_SYSTEM,
    JUDGE_SYSTEM,
    LANG_NAMES,
    OUT_OF_SCOPE_SYSTEM,
    PROMPT_VERSION,
    REALIZE_SYSTEM,
    STYLES,
)
from sextant.eval.generation.select import review_order
from sextant.eval.generation.split import assign_splits
from sextant.ingest.wiki import load_corpus
from sextant.llm import STRONG_MODEL, JsonLlm, LlmError, Request
from sextant.models import Article, Lang
from sextant.retrieval.base import Retriever

log = logging.getLogger(__name__)

KINDS: tuple[Kind, ...] = get_args(Kind)
CROSS_PAIRS = 45
OUT_OF_SCOPE_IDEAS = 20
POOL_STRATEGIES = ("bm25", "pg_fts", "dense:minilm", "dense:mpnet", "dense:e5-large")
POOL_SECTION_DEPTH = 10
POOL_CHUNK_DEPTH = 30


class Wiki:
    """The six languages of the wiki, addressable by language, slug and section index."""

    def __init__(self, articles: Mapping[Lang, Sequence[Article]]) -> None:
        self.articles: dict[Lang, dict[str, Article]] = {
            lang: {a.slug: a for a in items} for lang, items in articles.items()
        }
        self.order = [a.slug for a in articles["fr"]]

    @classmethod
    def load(cls, directory: Path) -> Wiki:
        """Load the YAML snapshot."""
        return cls(load_corpus(directory))

    def article(self, lang: Lang, slug: str) -> Article:
        """One article in one language."""
        return self.articles[lang][slug]

    def render_article(self, lang: Lang, slug: str) -> str:
        """Render an article with numbered sections, as the drafting prompts show it."""
        article = self.article(lang, slug)
        lines = [f"# {article.title}", f"Catégorie : {article.category_label}"]
        lines += [f"Résumé : {article.summary}", ""]
        for index, section in enumerate(article.sections):
            lines.append(f"## [{index}] {section.title or '(introduction)'}\n{section.text}\n")
        return "\n".join(lines)

    def render_section(self, lang: Lang, ref: SectionRef, label: str) -> str:
        """One section with its article title, labelled for a prompt."""
        article = self.article(lang, ref.slug)
        section = article.sections[ref.section_index]
        title = section.title or "(introduction)"
        return f"[{label}] {article.title} — {title}\n{section.text}"

    def valid(self, ref: SectionRef) -> bool:
        """Whether a section reference exists."""
        article = self.articles["fr"].get(ref.slug)
        return article is not None and 0 <= ref.section_index < len(article.sections)


def _parallel[T, R](fn: Callable[[T], R | None], items: Sequence[T], workers: int) -> list[R]:
    """Run `fn` over `items` in threads, keep the non-None results in input order."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(fn, items))
    return [r for r in results if r is not None]


def _ints(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, int) and not isinstance(v, bool)]


def _text(value: Any) -> str:
    return " ".join(str(value).split()) if isinstance(value, str) else ""


def parse_article_ideas(slug: str, payload: Mapping[str, Any], wiki: Wiki) -> list[Idea]:
    """Validate the ideas drafted from one article; drop the malformed ones."""
    ideas: list[Idea] = []
    raw = payload.get("ideas")
    for number, entry in enumerate(raw if isinstance(raw, list) else []):
        if not isinstance(entry, dict) or entry.get("kind") not in KINDS:
            continue
        kind = cast(Kind, entry["kind"])
        question, answer = _text(entry.get("question")), _text(entry.get("answer"))
        refs = tuple(
            dict.fromkeys(
                SectionRef(slug=slug, section_index=i)
                for i in _ints(entry.get("sections"))
                if wiki.valid(SectionRef(slug=slug, section_index=i))
            )
        )
        if kind == "unanswerable":
            refs = ()
        elif not refs or (kind == "multi_section" and len(refs) < 2):
            continue
        if len(question) < 8 or not answer:
            continue
        ideas.append(
            Idea(
                id=f"{slug}.{number}",
                origin="article",
                slug=slug,
                kind=kind,
                question=question,
                answer=answer,
                sections=tuple(sorted(refs, key=lambda r: r.section_index)),
            )
        )
    return ideas


def parse_cross_ideas(a: str, b: str, payload: Mapping[str, Any], wiki: Wiki) -> list[Idea]:
    """Validate cross-article ideas: at least one section of each article."""
    ideas: list[Idea] = []
    raw = payload.get("ideas")
    for number, entry in enumerate(raw if isinstance(raw, list) else []):
        if not isinstance(entry, dict):
            continue
        refs: list[SectionRef] = []
        for label in entry.get("sections") or []:
            side, _, index = str(label).partition(":")
            if side.strip() in ("A", "B") and index.strip().isdigit():
                ref = SectionRef(slug=a if side.strip() == "A" else b, section_index=int(index))
                if wiki.valid(ref) and ref not in refs:
                    refs.append(ref)
        question, answer = _text(entry.get("question")), _text(entry.get("answer"))
        if {r.slug for r in refs} != {a, b} or len(question) < 8 or not answer:
            continue
        ideas.append(
            Idea(
                id=f"x.{a}.{b}.{number}",
                origin="cross_article",
                slug=a,
                kind="multi_section",
                question=question,
                answer=answer,
                sections=tuple(refs),
            )
        )
    return ideas


def parse_out_of_scope(payload: Mapping[str, Any]) -> list[Idea]:
    """Validate out-of-scope unanswerable ideas."""
    raw = payload.get("ideas")
    ideas = []
    for number, entry in enumerate(raw if isinstance(raw, list) else []):
        if isinstance(entry, dict) and len(_text(entry.get("question"))) >= 8:
            ideas.append(
                Idea(
                    id=f"oos.{number}",
                    origin="out_of_scope",
                    kind="unanswerable",
                    question=_text(entry["question"]),
                    answer=_text(entry.get("answer")),
                )
            )
    return ideas


def related_pairs(wiki: Wiki, n: int, seed: int = 42) -> list[tuple[str, str]]:
    """Unordered pairs of articles that link to each other, a seeded sample of `n`."""
    pairs = sorted(
        {
            (min(a.slug, other), max(a.slug, other))
            for a in wiki.articles["fr"].values()
            for other in a.related
            if other in wiki.articles["fr"] and other != a.slug
        }
    )
    rng = random.Random(seed)
    return sorted(rng.sample(pairs, min(n, len(pairs))))


def _call(llm: JsonLlm, request: Request, what: str) -> dict[str, Any] | None:
    try:
        return llm.complete_json(request)
    except LlmError as error:
        log.warning("%s: %s", what, error)
        return None


def draft_ideas(llm: JsonLlm, wiki: Wiki, workers: int = 8) -> list[Idea]:
    """Stage 1: ideas per article, per pair of linked articles, and out of scope."""

    def per_article(slug: str) -> list[Idea] | None:
        request = Request(
            model=STRONG_MODEL,
            system=IDEAS_SYSTEM,
            user=wiki.render_article("fr", slug),
            max_tokens=3500,
            temperature=0.7,
        )
        payload = _call(llm, request, f"ideas {slug}")
        return None if payload is None else parse_article_ideas(slug, payload, wiki)

    def per_pair(pair: tuple[str, str]) -> list[Idea] | None:
        a, b = pair
        user = (
            "=== Article A ===\n" + wiki.render_article("fr", a) + "\n\n"
            "=== Article B ===\n" + wiki.render_article("fr", b)
        )
        request = Request(
            model=STRONG_MODEL, system=CROSS_SYSTEM, user=user, max_tokens=1500, temperature=0.7
        )
        payload = _call(llm, request, f"cross {a}/{b}")
        return None if payload is None else parse_cross_ideas(a, b, payload, wiki)

    ideas = [i for group in _parallel(per_article, wiki.order, workers) for i in group]
    pairs = related_pairs(wiki, CROSS_PAIRS)
    ideas += [i for group in _parallel(per_pair, pairs, workers) for i in group]

    catalogue = "\n".join(
        f"- {a.title} : {a.summary}" for a in (wiki.article("fr", s) for s in wiki.order)
    )
    request = Request(
        model=STRONG_MODEL,
        system=OUT_OF_SCOPE_SYSTEM,
        user=f"{catalogue}\n\nNombre de questions : {OUT_OF_SCOPE_IDEAS}",
        max_tokens=2500,
        temperature=0.7,
    )
    payload = _call(llm, request, "out of scope")
    ideas += parse_out_of_scope(payload or {})
    return ideas


def realize(
    llm: JsonLlm,
    wiki: Wiki,
    ideas: Mapping[str, Idea],
    assignments: Sequence[Assignment],
    workers: int = 8,
) -> list[Realized]:
    """Stage 3: write each assigned idea as a player of the target language would."""

    def one(assignment: Assignment) -> Realized | None:
        idea = ideas[assignment.idea_id]
        search_lang = assignment.corpus_lang or assignment.lang
        if idea.sections:
            sections = "\n\n".join(
                wiki.render_section(search_lang, ref, f"{n}")
                for n, ref in enumerate(idea.sections, start=1)
            )
        else:
            sections = "(aucune : le wiki ne répond pas à cette question)"
        system = REALIZE_SYSTEM.format(
            lang_name=LANG_NAMES[assignment.lang],
            lang=assignment.lang,
            style=STYLES[assignment.style],
        )
        user = (
            f"Idée de question : {idea.question}\nRéponse de référence : {idea.answer}\n\n"
            f"Sections du wiki ({LANG_NAMES[search_lang]}) :\n{sections}"
        )
        request = Request(
            model=STRONG_MODEL, system=system, user=user, max_tokens=1200, temperature=0.7
        )
        payload = _call(llm, request, f"realize {idea.id}")
        if payload is None:
            return None
        question, answer = _text(payload.get("question")), _text(payload.get("answer"))
        question_fr, answer_fr = _text(payload.get("question_fr")), _text(payload.get("answer_fr"))
        if assignment.lang == "fr":
            question_fr, answer_fr = question, answer
        if len(question) < 3 or not answer or not question_fr:
            log.warning("realize %s: incomplete answer", idea.id)
            return None
        return Realized(
            idea_id=idea.id,
            lang=assignment.lang,
            corpus_lang=assignment.corpus_lang,
            style=assignment.style,
            question=question,
            answer=answer,
            question_fr=question_fr,
            answer_fr=answer_fr,
        )

    return _parallel(one, assignments, workers)


def pool_sections(
    query: str,
    lang: Lang,
    retrievers: Iterable[Retriever],
    section_of: Mapping[str, SectionRef],
    depth: int = POOL_SECTION_DEPTH,
) -> list[SectionRef]:
    """Union of the top `depth` sections of every strategy (TREC-style pooling)."""
    pooled: dict[SectionRef, None] = {}
    for retriever in retrievers:
        ranked: dict[SectionRef, None] = {}
        for hit in retriever.search(query, lang, POOL_CHUNK_DEPTH):
            ranked.setdefault(section_of[hit.chunk_id])
            if len(ranked) == depth:
                break
        pooled.update(ranked)
    return list(pooled)


def judge(
    llm: JsonLlm,
    wiki: Wiki,
    items: Sequence[tuple[Realized, Idea, Sequence[SectionRef]]],
    workers: int = 8,
) -> list[Judgement]:
    """Stage 4: an LLM judge marks which pooled (and source) sections answer each question.

    `items` pairs each realized question with its idea and its pooled sections.
    Sections are shown in wiki order, sources mixed with pooled ones, so the
    judge cannot tell which section the question was drafted from.
    """

    def one(entry: tuple[Realized, Idea, Sequence[SectionRef]]) -> Judgement | None:
        item, idea, pool = entry
        shown = sorted(
            set(pool) | set(idea.sections),
            key=lambda r: (wiki.order.index(r.slug), r.section_index),
        )
        search_lang = item.corpus_lang or item.lang
        labels = {f"S{n}": ref for n, ref in enumerate(shown, start=1)}
        sections = "\n\n".join(wiki.render_section(search_lang, r, k) for k, r in labels.items())
        reference = (
            "(none: the question is believed NOT to be answered by the wiki)"
            if idea.kind == "unanswerable"
            else item.answer
        )
        user = (
            f"Question ({item.lang}): {item.question}\nReference answer: {reference}\n\n"
            f"Sections ({search_lang}):\n\n{sections}"
        )
        request = Request(
            model=STRONG_MODEL, system=JUDGE_SYSTEM, user=user, max_tokens=500, temperature=0.0
        )
        payload = _call(llm, request, f"judge {idea.id}")
        if payload is None:
            return None
        raw = payload.get("relevant")
        relevant = tuple(labels[k] for k in (raw if isinstance(raw, list) else []) if k in labels)
        return Judgement(
            idea_id=idea.id,
            pooled=tuple(shown),
            relevant=tuple(dict.fromkeys(relevant)),
            answerable=payload.get("answerable") is True,
            note=_text(payload.get("note")),
        )

    return _parallel(one, items, workers)


def assemble(
    ideas: Mapping[str, Idea],
    realized: Sequence[Realized],
    judgements: Mapping[str, Judgement],
    seed: int = 42,
) -> list[Candidate]:
    """Stage 5: proposed relevance, review flags, frozen split, review order and ids."""
    drafts: list[dict[str, Any]] = []
    for item in realized:
        idea, verdict = ideas[item.idea_id], judgements.get(item.idea_id)
        if verdict is None:
            continue
        judged = set(verdict.relevant)
        flags: list[str] = []
        if idea.kind == "unanswerable":
            relevant: tuple[SectionRef, ...] = ()
            added: tuple[SectionRef, ...] = ()
            found = verdict.relevant
            if found or verdict.answerable:
                flags.append("judge_found_answer")
        else:
            added = tuple(r for r in verdict.pooled if r in judged and r not in idea.sections)
            relevant = tuple(sorted(set(idea.sections) | judged, key=verdict.pooled.index))
            found = ()
            if any(source not in judged for source in idea.sections):
                flags.append("source_not_confirmed")
            if not verdict.answerable:
                flags.append("judge_not_answerable")
        drafts.append(
            {
                "lang": item.lang,
                "corpus_lang": item.corpus_lang,
                "kind": idea.kind,
                "origin": idea.origin,
                "slug": idea.slug,
                "style": item.style,
                "question": item.question,
                "reference_answer": item.answer,
                "question_fr": item.question_fr,
                "reference_answer_fr": item.answer_fr,
                "relevant": relevant,
                "sources": idea.sections,
                "judge_added": added,
                "judge_found": found,
                "flags": tuple(flags),
                "judge_note": verdict.note,
                "idea_id": idea.id,
                "prompt_version": PROMPT_VERSION,
            }
        )

    def cell(d: Mapping[str, Any]) -> str:
        return f"{d['lang']}/{d['kind']}/{'x' if d['corpus_lang'] else 'm'}"

    splits = assign_splits(
        groups={d["idea_id"]: d["slug"] or d["idea_id"] for d in drafts},
        cells={d["idea_id"]: cell(d) for d in drafts},
        seed=seed,
    )
    ordered = review_order(drafts, {n: cell(d) for n, d in enumerate(drafts)}, seed=seed)
    return [
        Candidate(id=f"q{n:03d}", review_order=n, split=splits[d["idea_id"]], **d)
        for n, d in enumerate(ordered, start=1)
    ]
