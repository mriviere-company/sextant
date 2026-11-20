"""Small fakes shared by the generation and API tests."""

from __future__ import annotations

from collections.abc import Sequence

from sextant.models import Chunk, Lang
from sextant.retrieval.base import Hit


def make_chunk(index: int, lang: Lang = "fr") -> Chunk:
    """A hand-made chunk: article `art{index}`, section `Section {index}`."""
    return Chunk(
        id=f"{lang}:art{index}#sec{index}:0",
        lang=lang,
        slug=f"art{index}",
        article_title=f"Article {index}",
        category="guide",
        section_index=index,
        section_anchor=f"sec{index}",
        section_title=f"Section {index}",
        part=0,
        text=f"Texte {index} de la section.",
        embed_text=f"Article {index} Section {index} Texte {index}",
        url=f"https://www.areauniverse.com/wiki/art{index}#sec{index}",
        n_words=5,
    )


class FakeRetriever:
    """Returns the first `k` chunks of the requested language, best first."""

    name = "fake"

    def __init__(self, chunks: Sequence[Chunk]) -> None:
        self.chunks = list(chunks)
        self.queries: list[tuple[str, Lang, int]] = []

    def search(self, query: str, lang: Lang, k: int) -> list[Hit]:
        self.queries.append((query, lang, k))
        same = [c for c in self.chunks if c.lang == lang][:k]
        return [Hit(chunk_id=c.id, score=1.0 - i / 10) for i, c in enumerate(same)]


class ManualClock:
    """A clock that only moves when told to."""

    def __init__(self, start: float = 1000.0) -> None:
        self.value = start

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds
