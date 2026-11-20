"""The retrieval contract shared by every strategy, so the benchmark can swap them freely."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from sextant.models import Chunk, Lang

CHUNKS_PATH = Path(__file__).resolve().parents[3] / "corpus" / "processed" / "chunks.jsonl"


class Hit(BaseModel):
    """One retrieved chunk with the score the strategy gave it (higher is better)."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    score: float


class Retriever(Protocol):
    """A retrieval strategy: the `k` best chunks for a query, in the query's language."""

    @property
    def name(self) -> str:
        """Short identifier used in benchmark reports."""
        ...

    def search(self, query: str, lang: Lang, k: int) -> list[Hit]:
        """Return at most `k` hits, best first."""
        ...


def load_chunks(path: Path = CHUNKS_PATH) -> list[Chunk]:
    """Load the processed corpus written by `make ingest`."""
    if not path.exists():
        raise FileNotFoundError(f"{path} not found: run `make ingest` first")
    with path.open(encoding="utf-8") as handle:
        return [Chunk.model_validate(json.loads(line)) for line in handle if line.strip()]
