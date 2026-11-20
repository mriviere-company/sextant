"""Cross-encoder reranking of a first-stage retriever's candidates.

A bi-encoder embeds query and passage separately; a cross-encoder reads them
together and scores relevance far more precisely, at a cost per pair. The
usual compromise, measured here: retrieve `depth` candidates cheaply, rerank
them, keep the best `k`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from sextant.models import Chunk, Lang
from sextant.retrieval.base import Hit, Retriever

RERANK_MODELS: dict[str, str] = {
    "bge-m3": "BAAI/bge-reranker-v2-m3-int8",
}


class Reranker(Protocol):
    """Scores (query, passage) pairs; higher is more relevant."""

    @property
    def key(self) -> str:
        """Short name."""
        ...

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        """One score per passage."""
        ...


class FastEmbedReranker:
    """A multilingual ONNX cross-encoder from `fastembed`."""

    def __init__(self, key: str, batch_size: int = 16) -> None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder  # noqa: PLC0415

        if key not in RERANK_MODELS:
            raise ValueError(f"unknown reranker {key!r}; known: {sorted(RERANK_MODELS)}")
        self._key = key
        self._model = TextCrossEncoder(RERANK_MODELS[key])
        self._batch_size = batch_size

    @property
    def key(self) -> str:
        """Short name."""
        return self._key

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        """Relevance scores."""
        return [
            float(s) for s in self._model.rerank(query, list(passages), batch_size=self._batch_size)
        ]


class RerankRetriever:
    """Rerank the top `depth` hits of `base` with a cross-encoder."""

    def __init__(
        self,
        base: Retriever,
        reranker: Reranker,
        chunks: Mapping[str, Chunk],
        depth: int = 30,
    ) -> None:
        self._base = base
        self._reranker = reranker
        self._chunks = chunks
        self._depth = depth

    @property
    def name(self) -> str:
        """Identifier in reports, e.g. `rerank:bge-m3(hybrid(...))`."""
        return f"rerank:{self._reranker.key}({self._base.name})"

    def search(self, query: str, lang: Lang, k: int) -> list[Hit]:
        """Top-k after reranking; ties keep the first-stage order."""
        candidates = self._base.search(query, lang, self._depth)
        if not candidates:
            return []
        scores = self._reranker.score(
            query, [self._chunks[h.chunk_id].embed_text for h in candidates]
        )
        order = sorted(range(len(candidates)), key=lambda i: (-scores[i], i))
        return [Hit(chunk_id=candidates[i].chunk_id, score=scores[i]) for i in order[:k]]
