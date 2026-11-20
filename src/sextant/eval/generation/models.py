"""Data of the question-generation pipeline, stage by stage.

    Idea  ──select / assign──▶  Assignment  ──realize──▶  Realized  ──pool + judge──▶  Candidate

Each stage writes a JSONL file under `eval/dataset/work/` (committed, so the
provenance of every question is inspectable), and `eval/dataset/candidates.jsonl`
is what the reviewer validates. Nothing here is an evaluation item yet: an
`EvalItem` only exists once a human kept or corrected the candidate.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from sextant.eval.dataset import Kind, SectionRef, Split
from sextant.models import Lang

Origin = Literal["article", "cross_article", "out_of_scope"]
Style = Literal["short", "natural", "situated"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Idea(_Frozen):
    """A question drafted in French from one article (or two linked articles)."""

    id: str
    origin: Origin
    slug: str = ""  # primary article; empty for out-of-scope questions
    kind: Kind
    question: str = Field(min_length=3)
    answer: str
    sections: tuple[SectionRef, ...] = ()


class Assignment(_Frozen):
    """A selected idea with its target language, search corpus and style."""

    idea_id: str
    lang: Lang
    corpus_lang: Lang | None = None
    style: Style


class Realized(_Frozen):
    """The question as a player would type it, with its reference answer."""

    idea_id: str
    lang: Lang
    corpus_lang: Lang | None = None
    style: Style
    question: str = Field(min_length=3)
    answer: str
    question_fr: str
    answer_fr: str


class Candidate(_Frozen):
    """A question ready for human review.

    `relevant` is the proposed judgement: the sections the idea was drafted
    from (`sources`) plus those an LLM judge found answering it among the
    sections every retrieval strategy returned (`judge_added`, TREC-style
    pooling). `flags` point the reviewer at what deserves a second look.
    """

    id: str
    review_order: int = Field(ge=1)
    split: Split
    lang: Lang
    corpus_lang: Lang | None = None
    kind: Kind
    origin: Origin
    slug: str
    style: Style
    question: str
    reference_answer: str
    question_fr: str
    reference_answer_fr: str
    relevant: tuple[SectionRef, ...]
    sources: tuple[SectionRef, ...]
    judge_added: tuple[SectionRef, ...] = ()
    judge_found: tuple[SectionRef, ...] = ()  # unanswerable only: sections the judge disputes
    flags: tuple[str, ...] = ()
    judge_note: str = ""
    idea_id: str
    prompt_version: str


def write_jsonl(path: Path, records: Iterable[BaseModel]) -> None:
    """One JSON object per line, UTF-8, stable key order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=False) + "\n")


def read_jsonl[M: BaseModel](path: Path, model: type[M]) -> list[M]:
    """Load a JSONL file into models."""
    with path.open(encoding="utf-8") as handle:
        return [model.model_validate(json.loads(line)) for line in handle if line.strip()]


class Judgement(_Frozen):
    """Which pooled sections an LLM judge found answering a realized question."""

    idea_id: str
    pooled: tuple[SectionRef, ...]
    relevant: tuple[SectionRef, ...]
    answerable: bool
    note: str = ""
