"""Build retrieval strategies from short specs, so benchmarks are one command line.

Specs:
- `bm25` — in-memory BM25
- `pg_fts` — PostgreSQL full text
- `dense:<model>` — pgvector search with an embedding model (`minilm`, `mpnet`, `e5-large`)
- `hybrid:<model>` — RRF of `bm25` and `dense:<model>`
- `rerank:<reranker>:<spec>` — cross-encoder reranking of another strategy
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from functools import cached_property

from sextant.models import Chunk
from sextant.retrieval.base import Retriever
from sextant.retrieval.embeddings import Embedder, FastEmbedEmbedder
from sextant.retrieval.hybrid import HybridRetriever
from sextant.retrieval.lexical import BM25Retriever
from sextant.retrieval.rerank import FastEmbedReranker, Reranker, RerankRetriever
from sextant.retrieval.store import DenseRetriever, PgFtsRetriever, PgStore

DEFAULT_DSN = "postgresql://sextant:sextant@127.0.0.1:5432/sextant"


def database_url() -> str:
    """`DATABASE_URL` from the environment, else the local docker-compose default."""
    return os.environ.get("DATABASE_URL", DEFAULT_DSN)


class RetrievalContext:
    """Shares the expensive objects (BM25 index, models, store) between strategies."""

    def __init__(self, chunks: Sequence[Chunk], dsn: str | None = None) -> None:
        self.chunks = list(chunks)
        self.by_id = {chunk.id: chunk for chunk in self.chunks}
        self._dsn = dsn or database_url()
        self._embedders: dict[str, Embedder] = {}
        self._rerankers: dict[str, Reranker] = {}

    @cached_property
    def store(self) -> PgStore:
        """The PostgreSQL store."""
        return PgStore(self._dsn)

    @cached_property
    def bm25(self) -> BM25Retriever:
        """The BM25 index (built once)."""
        return BM25Retriever(self.chunks)

    def embedder(self, key: str) -> Embedder:
        """Return an embedding model, loaded once."""
        if key not in self._embedders:
            self._embedders[key] = FastEmbedEmbedder(key)
        return self._embedders[key]

    def reranker(self, key: str) -> Reranker:
        """Return a reranker, loaded once."""
        if key not in self._rerankers:
            self._rerankers[key] = FastEmbedReranker(key)
        return self._rerankers[key]

    def build(self, spec: str) -> Retriever:
        """Build one strategy from its spec."""
        head, _, rest = spec.partition(":")
        if head == "bm25" and not rest:
            return self.bm25
        if head == "pg_fts" and not rest:
            return PgFtsRetriever(self.store)
        if head == "dense" and rest:
            return DenseRetriever(self.embedder(rest), self.store)
        if head == "hybrid" and rest:
            return HybridRetriever([self.bm25, DenseRetriever(self.embedder(rest), self.store)])
        if head == "rerank" and ":" in rest:
            key, _, inner = rest.partition(":")
            return RerankRetriever(self.build(inner), self.reranker(key), self.by_id)
        raise ValueError(f"unknown retrieval spec: {spec!r}")
