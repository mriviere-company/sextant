"""Request and response models: exactly the contract of docs/api.md."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from sextant.generation.answer import Citation, Usage
from sextant.models import Lang

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]
TopK = Annotated[int, Field(ge=1, le=20)]
DEFAULT_TOP_K = 5


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class AskRequest(BaseModel):
    """`POST /v1/ask` body."""

    question: Text
    lang: Lang | None = None
    top_k: TopK = DEFAULT_TOP_K


class AskResponse(_Frozen):
    """`POST /v1/ask` 200 body."""

    answer: str
    refused: bool
    citations: list[Citation]
    latency_ms: int
    usage: Usage


class SearchRequest(BaseModel):
    """`POST /v1/search` body."""

    query: Text
    lang: Lang | None = None
    top_k: TopK = DEFAULT_TOP_K


class SearchResult(_Frozen):
    """One retrieved chunk."""

    chunk_id: str
    score: float
    title: str
    url: str
    lang: Lang
    text: str


class SearchResponse(_Frozen):
    """`POST /v1/search` 200 body."""

    results: list[SearchResult]
    latency_ms: int


class HealthResponse(_Frozen):
    """`GET /v1/health` body (200, or 503 while the index is not ready)."""

    status: str
    corpus_chunks: int
    index: str


class ErrorBody(_Frozen):
    """The inside of the error envelope."""

    code: str
    message: str
    request_id: str


class ErrorEnvelope(_Frozen):
    """Every error response."""

    error: ErrorBody
