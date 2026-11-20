"""Domain models shared by ingestion, retrieval and evaluation.

Every model is frozen: the corpus is data, not state. Identifiers are derived
from the content's own coordinates (language, article slug, section anchor),
never from a counter, so the same wiki snapshot always yields the same ids —
which is what lets an evaluation set reference chunks across rebuilds.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Lang = Literal["fr", "en", "de", "es", "pt", "ru"]
LANGS: tuple[Lang, ...] = ("fr", "en", "de", "es", "pt", "ru")

WIKI_BASE_URL = "https://www.areauniverse.com/wiki"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Section(_Frozen):
    """One `<h2>` section of an article (the intro before the first `<h2>` has an empty anchor)."""

    anchor: str
    title: str
    text: str = Field(min_length=1)


class Article(_Frozen):
    """One wiki article in one language."""

    lang: Lang
    slug: str = Field(pattern=r"^[a-z0-9_]+$")
    title: str
    category: str
    category_label: str
    order: int
    tags: tuple[str, ...]
    summary: str
    related: tuple[str, ...]
    sections: tuple[Section, ...] = Field(min_length=1)

    @property
    def url(self) -> str:
        """Public URL of the article on the game site."""
        return f"{WIKI_BASE_URL}/{self.slug}"


class Chunk(_Frozen):
    """The unit that gets embedded, retrieved and cited.

    `text` is what the LLM reads and what a citation points to. `embed_text`
    prepends the article and section titles: short sections ("Étape 2 — Composer")
    are ambiguous on their own, and a contextual header is a cheap, well-known
    retrieval gain that phase 2 measures rather than assumes.

    `section_index` is the position of the section in its article. Anchors are
    translated, positions are not: `(slug, section_index)` names the same
    passage in all six languages.
    """

    id: str
    lang: Lang
    slug: str
    article_title: str
    category: str
    section_index: int = Field(ge=0)
    section_anchor: str
    section_title: str
    part: int = Field(ge=0)
    text: str = Field(min_length=1)
    embed_text: str
    url: str
    n_words: int = Field(ge=1)
