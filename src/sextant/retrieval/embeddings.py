"""Local embedding models (ONNX, CPU) behind a small protocol.

Embeddings run locally through `fastembed` (ONNX Runtime): no API cost, no
data leaving the machine, and the same vectors in CI as on a laptop. Models
that expect instruction prefixes (the E5 family's `query:` / `passage:`) get
them from `fastembed`'s `query_embed` / `passage_embed`, so queries and
passages are never embedded the same way by mistake.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

Vectors = NDArray[np.float32]

# Short names used in reports and table names; the benchmark compares them.
EMBEDDING_MODELS: dict[str, str] = {
    "minilm": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "mpnet": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    "e5-large": "intfloat/multilingual-e5-large",
}


class Embedder(Protocol):
    """Turns texts into L2-normalized vectors."""

    @property
    def key(self) -> str:
        """Short name, safe as a SQL identifier suffix."""
        ...

    @property
    def dim(self) -> int:
        """Vector dimension."""
        ...

    def embed_queries(self, texts: Sequence[str]) -> Vectors:
        """Vectors for search queries."""
        ...

    def embed_passages(self, texts: Sequence[str]) -> Vectors:
        """Vectors for indexed passages."""
        ...


def normalize(vectors: Vectors) -> Vectors:
    """L2-normalize rows (cosine similarity becomes a dot product)."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return (vectors / np.where(norms == 0, 1, norms)).astype(np.float32)


def safe_key(key: str) -> str:
    """Reject anything that is not a plain identifier fragment."""
    if not re.fullmatch(r"[a-z0-9_]+", key.replace("-", "_")):
        raise ValueError(f"invalid embedder key: {key!r}")
    return key.replace("-", "_")


class FastEmbedEmbedder:
    """An ONNX embedding model from `fastembed` (downloaded once, then cached)."""

    def __init__(self, key: str, batch_size: int = 32) -> None:
        from fastembed import TextEmbedding  # noqa: PLC0415 — heavy import, only when used

        if key not in EMBEDDING_MODELS:
            raise ValueError(f"unknown model {key!r}; known: {sorted(EMBEDDING_MODELS)}")
        self._key = key
        self._model = TextEmbedding(EMBEDDING_MODELS[key])
        self._batch_size = batch_size
        self._dim = int(self.embed_queries(["dimension probe"]).shape[1])

    @property
    def key(self) -> str:
        """Short name."""
        return self._key

    @property
    def dim(self) -> int:
        """Vector dimension."""
        return self._dim

    def embed_queries(self, texts: Sequence[str]) -> Vectors:
        """Query vectors (with the model's query prefix if it uses one)."""
        rows = list(self._model.query_embed(list(texts), batch_size=self._batch_size))
        return normalize(np.asarray(rows, dtype=np.float32))

    def embed_passages(self, texts: Sequence[str]) -> Vectors:
        """Passage vectors (with the model's passage prefix if it uses one)."""
        rows = list(self._model.passage_embed(list(texts), batch_size=self._batch_size))
        return normalize(np.asarray(rows, dtype=np.float32))
