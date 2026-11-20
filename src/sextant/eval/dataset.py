"""The evaluation set: questions with the wiki sections that answer them.

Relevance is judged at the *section* level, identified by `(slug,
section_index)`: section positions are the same in all six languages, so one
judgement holds whatever the question's language, and a section split into
several chunks counts once.

A *cross-lingual* question sets `corpus_lang`: it is asked in `lang` but
searched in the wiki of another language (a player whose question language
differs from the wiki they read). Those questions are reported apart from the
monolingual ones, which carry the decision metrics (`eval/PROTOCOL.md`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sextant.models import Lang

Kind = Literal["factual", "procedural", "comparative", "multi_section", "unanswerable"]
Split = Literal["dev", "test"]


class SectionRef(BaseModel):
    """A section, language-independent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slug: str
    section_index: int = Field(ge=0)


class EvalItem(BaseModel):
    """One evaluation question."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    question: str = Field(min_length=3)
    lang: Lang
    corpus_lang: Lang | None = None
    kind: Kind
    split: Split
    relevant: tuple[SectionRef, ...] = ()
    reference_answer: str = ""
    validated: bool = False

    @model_validator(mode="after")
    def _relevance_matches_kind(self) -> EvalItem:
        if self.kind == "unanswerable" and self.relevant:
            raise ValueError(f"{self.id}: an unanswerable question cannot have relevant sections")
        if self.kind != "unanswerable" and not self.relevant:
            raise ValueError(f"{self.id}: an answerable question needs relevant sections")
        if self.corpus_lang == self.lang:
            raise ValueError(f"{self.id}: corpus_lang is only set for cross-lingual questions")
        return self

    @property
    def answerable(self) -> bool:
        """Whether the wiki contains the answer."""
        return self.kind != "unanswerable"

    @property
    def cross_lingual(self) -> bool:
        """Whether the question is searched in another language's wiki."""
        return self.corpus_lang is not None

    @property
    def search_lang(self) -> Lang:
        """The language of the wiki the question is searched in."""
        return self.corpus_lang or self.lang


def load_items(path: Path, split: Split | None = None) -> list[EvalItem]:
    """Load a JSONL evaluation file, optionally one split only; ids must be unique."""
    items: list[EvalItem] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if line.strip():
                try:
                    items.append(EvalItem.model_validate(json.loads(line)))
                except ValueError as error:
                    raise ValueError(f"{path}:{number}: {error}") from error
    ids = [item.id for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path}: duplicate question ids")
    return [item for item in items if split is None or item.split == split]
