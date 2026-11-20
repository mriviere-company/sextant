"""Reciprocal rank fusion of several retrievers.

RRF (Cormack et al., 2009) combines rankings by position only: a chunk scores
the sum of `1 / (k + rank)` over the lists it appears in. It needs no score
calibration between BM25 and cosine similarity, which live on unrelated
scales, and `k = 60` is the value from the original paper.
"""

from __future__ import annotations

from collections.abc import Sequence

from sextant.models import Lang
from sextant.retrieval.base import Hit, Retriever

RRF_K = 60


def rrf_fuse(rankings: Sequence[Sequence[Hit]], k: int = RRF_K) -> list[Hit]:
    """Fuse ranked lists; ties keep a deterministic order (by chunk id)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, start=1):
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [Hit(chunk_id=chunk_id, score=score) for chunk_id, score in ordered]


class HybridRetriever:
    """Fuse the top `depth` results of each retriever with RRF, keep the best `k`."""

    def __init__(self, retrievers: Sequence[Retriever], depth: int = 50, k: int = RRF_K) -> None:
        if not retrievers:
            raise ValueError("HybridRetriever needs at least one retriever")
        self._retrievers = list(retrievers)
        self._depth = depth
        self._k = k

    @property
    def name(self) -> str:
        """Identifier in reports, e.g. `hybrid(bm25+dense:minilm)`."""
        return "hybrid(" + "+".join(r.name for r in self._retrievers) + ")"

    def search(self, query: str, lang: Lang, k: int) -> list[Hit]:
        """Fused top-k."""
        rankings = [r.search(query, lang, self._depth) for r in self._retrievers]
        return rrf_fuse(rankings, self._k)[:k]
