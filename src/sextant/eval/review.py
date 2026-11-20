r"""Human review of the candidates: `python -m sextant.eval.review <command>`.

    page         candidates.jsonl → eval/review/candidates.json, what the review page shows
    import FILE  decisions exported from the review page → eval/dataset/reviews.jsonl
    build        candidates + reviews → eval/dataset/questions.jsonl and eval/dataset/stats.json

The reviewer, who knows the game, keeps, corrects or rejects each candidate
on the review page (`eval/review/index.html`). Only kept or corrected
candidates become evaluation items, all marked `validated`. Their split is the
one frozen on the candidate before the review started: the review can drop a
question, never move it.

A non-French question corrected only in its French gloss cannot be used as
is: `build` refuses it and names it, and the question text in its own
language is fixed in the review (or re-translated, then reviewed again).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sextant.eval.dataset import EvalItem, SectionRef
from sextant.eval.generation.models import Candidate, read_jsonl, write_jsonl
from sextant.eval.generation.pipeline import Wiki

ROOT = Path(__file__).resolve().parents[3]
DATASET = ROOT / "eval" / "dataset"
CANDIDATES = DATASET / "candidates.jsonl"
REVIEWS = DATASET / "reviews.jsonl"
QUESTIONS = DATASET / "questions.jsonl"
STATS = DATASET / "stats.json"
PAGE_DATA = ROOT / "eval" / "review" / "candidates.json"
MIN_VALIDATED = 150

Decision = Literal["keep", "edit", "reject"]


def section_key(ref: SectionRef) -> str:
    """`slug#index`, the compact form the review page stores."""
    return f"{ref.slug}#{ref.section_index}"


def parse_section_key(key: str) -> SectionRef:
    """Inverse of `section_key`."""
    slug, _, index = key.partition("#")
    if not slug or not index.isdigit():
        raise ValueError(f"bad section key {key!r}")
    return SectionRef(slug=slug, section_index=int(index))


class Review(BaseModel):
    """The reviewer's decision on one candidate."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str
    decision: Decision
    relevant: tuple[SectionRef, ...] | None = None
    question: str | None = None
    reference_answer: str | None = None
    question_fr: str | None = None
    reference_answer_fr: str | None = None
    reject_reason: str = ""
    note: str = ""
    reviewed_at: str = Field(min_length=1)

    @field_validator("relevant", mode="before")
    @classmethod
    def _keys(cls, value: Any) -> Any:
        if isinstance(value, list) and all(isinstance(v, str) for v in value):
            return tuple(parse_section_key(v) for v in value)
        return value


class ReviewError(ValueError):
    """Reviews that cannot be turned into evaluation items."""


def page_record(candidate: Candidate, wiki: Wiki) -> dict[str, Any]:
    """Describe one candidate for the review page (sections shown in French)."""

    def section(ref: SectionRef, role: str) -> dict[str, Any]:
        article = wiki.article("fr", ref.slug)
        sec = article.sections[ref.section_index]
        return {
            "key": section_key(ref),
            "role": role,
            "article": article.title,
            "title": sec.title or "Introduction",
            "text": sec.text,
            "url": f"{article.url}#{sec.anchor}" if sec.anchor else article.url,
        }

    # Sources first, then the judge's additions: the reviewer checks the drafting first.
    shown = [section(r, "source") for r in candidate.relevant if r in candidate.sources]
    shown += [section(r, "judge") for r in candidate.relevant if r not in candidate.sources]
    shown += [section(r, "found") for r in candidate.judge_found]
    return {
        "id": candidate.id,
        "order": candidate.review_order,
        "lang": candidate.lang,
        "corpus_lang": candidate.corpus_lang,
        "kind": candidate.kind,
        "origin": candidate.origin,
        "question": candidate.question,
        "question_fr": candidate.question_fr,
        "answer": candidate.reference_answer,
        "answer_fr": candidate.reference_answer_fr,
        "sections": shown,
        "flags": list(candidate.flags),
        "judge_note": candidate.judge_note,
    }


def import_reviews(records: Iterable[Mapping[str, Any]], known: set[str]) -> list[Review]:
    """Validate decisions exported from the page; unknown ids are an error."""
    reviews = sorted((Review.model_validate(r) for r in records), key=lambda r: r.id)
    unknown = sorted({r.id for r in reviews} - known)
    if unknown:
        raise ReviewError(f"reviews for unknown candidates: {unknown[:5]}")
    if len({r.id for r in reviews}) != len(reviews):
        raise ReviewError("two reviews for the same candidate")
    return reviews


def _read_export(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if text.startswith("["):
        data = json.loads(text)
        return [dict(r) for r in data]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def build_items(candidates: Sequence[Candidate], reviews: Sequence[Review]) -> list[EvalItem]:
    """Kept and corrected candidates as validated evaluation items, in review order."""
    by_id = {c.id: c for c in candidates}
    problems: list[str] = []
    items: list[EvalItem] = []
    for review in sorted(reviews, key=lambda r: by_id[r.id].review_order):
        if review.decision == "reject":
            continue
        cand = by_id[review.id]
        question = (review.question or cand.question).strip()
        answer = (review.reference_answer or cand.reference_answer).strip()
        gloss_edited = (
            review.question_fr is not None and review.question_fr.strip() != cand.question_fr
        )
        text_edited = review.question is not None and review.question.strip() != cand.question
        if cand.lang != "fr" and gloss_edited and not text_edited:
            problems.append(f"{cand.id}: French gloss corrected but not the {cand.lang} question")
            continue
        relevant = cand.relevant if review.relevant is None else review.relevant
        if cand.kind == "unanswerable":
            relevant = ()
        if cand.kind != "unanswerable" and not relevant:
            problems.append(f"{cand.id}: kept without any relevant section")
            continue
        items.append(
            EvalItem(
                id=cand.id,
                question=question,
                lang=cand.lang,
                corpus_lang=cand.corpus_lang,
                kind=cand.kind,
                split=cand.split,
                relevant=tuple(relevant),
                reference_answer=answer,
                validated=True,
            )
        )
    if problems:
        raise ReviewError("; ".join(problems))
    return items


def dataset_stats(
    candidates: Sequence[Candidate], reviews: Sequence[Review], items: Sequence[EvalItem]
) -> dict[str, Any]:
    """Compute the published figures of the evaluation set (the README links here)."""

    def table(rows: Iterable[EvalItem]) -> dict[str, Any]:
        rows = list(rows)
        return {
            "questions": len(rows),
            "by_lang": dict(sorted(Counter(i.lang for i in rows).items())),
            "by_kind": dict(sorted(Counter(i.kind for i in rows).items())),
            "unanswerable_share": round(sum(not i.answerable for i in rows) / len(rows), 3)
            if rows
            else 0.0,
            "cross_lingual": sum(i.cross_lingual for i in rows),
            "monolingual_answerable_by_lang": dict(
                sorted(
                    Counter(i.lang for i in rows if i.answerable and not i.cross_lingual).items()
                )
            ),
            "relevant_sections_per_answerable": round(
                sum(len(i.relevant) for i in rows if i.answerable)
                / max(1, sum(i.answerable for i in rows)),
                2,
            ),
        }

    decisions = Counter(r.decision for r in reviews)
    reviewed = {r.id for r in reviews}
    per_kind_kept = Counter(i.kind for i in items)
    per_kind_reviewed = Counter(c.kind for c in candidates if c.id in reviewed)
    return {
        "candidates": len(candidates),
        "reviewed": len(reviews),
        "decisions": dict(sorted(decisions.items())),
        "reject_reasons": dict(
            sorted(
                Counter(
                    r.reject_reason or "unspecified" for r in reviews if r.decision == "reject"
                ).items()
            )
        ),
        "acceptance_by_kind": {
            kind: round(per_kind_kept[kind] / n, 3) for kind, n in sorted(per_kind_reviewed.items())
        },
        "relevance_changed_by_reviewer": sum(
            1
            for r in reviews
            if r.decision != "reject"
            and r.relevant is not None
            and set(r.relevant) != set(next(c for c in candidates if c.id == r.id).relevant)
        ),
        "validated": table(items),
        "dev": table(i for i in items if i.split == "dev"),
        "test": table(i for i in items if i.split == "test"),
    }


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("page")
    imp = sub.add_parser("import")
    imp.add_argument("file", type=Path)
    sub.add_parser("build")
    args = parser.parse_args(argv)

    candidates = read_jsonl(CANDIDATES, Candidate)
    if args.command == "page":
        wiki = Wiki.load(ROOT / "corpus" / "wiki")
        records = [page_record(c, wiki) for c in candidates]
        PAGE_DATA.parent.mkdir(parents=True, exist_ok=True)
        lines = ",\n".join(json.dumps(r, ensure_ascii=False) for r in records)
        PAGE_DATA.write_text(f"[\n{lines}\n]\n", encoding="utf-8")
        print(f"{PAGE_DATA.relative_to(ROOT)}: {len(records)} candidates")
    elif args.command == "import":
        reviews = import_reviews(_read_export(args.file), {c.id for c in candidates})
        write_jsonl(REVIEWS, reviews)
        print(
            f"{REVIEWS.relative_to(ROOT)}: {len(reviews)} reviews",
            dict(Counter(r.decision for r in reviews)),
        )
    else:
        reviews = read_jsonl(REVIEWS, Review)
        items = build_items(candidates, reviews)
        write_jsonl(QUESTIONS, items)
        stats = dataset_stats(candidates, reviews, items)
        STATS.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(stats["validated"], indent=1))
        if len(items) < MIN_VALIDATED:
            print(f"warning: {len(items)} validated questions, the plan asks for {MIN_VALIDATED}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
