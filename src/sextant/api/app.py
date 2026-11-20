"""The HTTP API (contract: docs/api.md; design: docs/generation.md).

`create_app` takes everything it depends on as optional arguments, so tests run it on a fake
retriever and a fake provider with scripted clocks. With no retriever given, the production
one (corpus + e5-large + PostgreSQL) loads in a background thread: until it is ready,
`/v1/health` answers 503 "loading" and `/v1/ask` and `/v1/search` answer 503 `unavailable`.
"""

from __future__ import annotations

import logging
import math
import re
import threading
import time
import uuid
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime
from typing import Any, cast

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from sextant.api.schemas import (
    AskRequest,
    AskResponse,
    ErrorBody,
    ErrorEnvelope,
    HealthResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from sextant.api.settings import Settings
from sextant.generation.answer import AnswerService, AnswerTimeoutError, MalformedAnswerError
from sextant.generation.budget import DailyBudget, Deadline, RateLimiter, utc_now
from sextant.generation.lang import detect_lang
from sextant.generation.prompt import chunk_title
from sextant.generation.providers import (
    LlmProvider,
    ProviderError,
    ProviderTimeout,
    provider_from_env,
)
from sextant.models import Chunk
from sextant.retrieval.base import Retriever, load_chunks

PRODUCTION_STRATEGY = "dense:e5-large"
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,64}")

logger = logging.getLogger("sextant.api")

Loader = Callable[[], tuple[Retriever, Sequence[Chunk]]]


class ApiError(Exception):
    """An error with its HTTP status, envelope code and optional headers."""

    def __init__(
        self, status: int, code: str, message: str, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers or {}


def load_production_retriever() -> tuple[Retriever, list[Chunk]]:
    """Load the corpus and build `dense:e5-large` (the slow part: model and database)."""
    from sextant.retrieval.factory import RetrievalContext  # noqa: PLC0415 — heavy imports

    chunks = load_chunks()
    retriever = RetrievalContext(chunks).build(PRODUCTION_STRATEGY)
    retriever.search("warm-up", "fr", 1)
    return retriever, chunks


class _Index:
    """The retriever and corpus, once loaded (assigned atomically by the loader thread)."""

    def __init__(self) -> None:
        self.retriever: Retriever | None = None
        self.chunks: dict[str, Chunk] = {}
        self.failed = False

    @property
    def ready(self) -> bool:
        return self.retriever is not None

    def set(self, retriever: Retriever, chunks: Sequence[Chunk]) -> None:
        self.chunks = {chunk.id: chunk for chunk in chunks}
        self.retriever = retriever


def _load_in_background(index: _Index, loader: Loader) -> None:
    def run() -> None:
        try:
            retriever, chunks = loader()
            index.set(retriever, chunks)
        except Exception:
            index.failed = True
            logger.exception("index loading failed")

    threading.Thread(target=run, name="index-loader", daemon=True).start()


def resolve_request_id(header: str | None) -> str:
    """Keep a well-formed incoming id, else generate one."""
    if header and REQUEST_ID_PATTERN.fullmatch(header):
        return header
    return uuid.uuid4().hex


def client_key(request: Request, trust_proxy: bool) -> str:
    """Return the address rate limits are counted per."""
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "unknown"


_VALIDATION_REASONS = {
    "string_too_short": "too short",
    "string_too_long": "too long",
    "missing": "required",
    "literal_error": "unsupported value",
    "greater_than_equal": "too small",
    "less_than_equal": "too large",
    "json_invalid": "invalid JSON",
    "int_parsing": "must be an integer",
    "string_type": "must be a string",
    "int_type": "must be an integer",
}


def validation_message(error: RequestValidationError) -> str:
    """`field: reason` for the first validation failure (never echoes the input)."""
    first = error.errors()[0]
    field = ".".join(str(part) for part in first["loc"] if part != "body") or "body"
    return f"{field}: {_VALIDATION_REASONS.get(str(first['type']), 'invalid value')}"


def error_response(
    status: int, code: str, message: str, request_id: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    """Build the single error envelope."""
    envelope = ErrorEnvelope(error=ErrorBody(code=code, message=message, request_id=request_id))
    return JSONResponse(
        envelope.model_dump(),
        status_code=status,
        headers={**(headers or {}), "X-Request-Id": request_id},
    )


def create_app(  # noqa: PLR0913, PLR0915 — wiring: every dependency is injectable
    *,
    retriever: Retriever | None = None,
    chunks: Sequence[Chunk] | None = None,
    provider: LlmProvider | None = None,
    settings: Settings | None = None,
    loader: Loader | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    now: Callable[[], datetime] = utc_now,
) -> FastAPI:
    """Build the application.

    With a retriever and chunks the app is ready at once; otherwise `loader` runs in the
    background (default: the production retriever).
    """
    cfg = settings or Settings.from_env()
    llm = provider or provider_from_env()
    index = _Index()
    if retriever is not None:
        index.set(retriever, chunks or [])
    else:
        _load_in_background(index, loader or load_production_retriever)

    budget = DailyBudget(cfg.daily_budget_usd, now)
    ask_limiter = RateLimiter(cfg.ask_per_minute, monotonic)
    search_limiter = RateLimiter(cfg.search_per_minute, monotonic)

    app = FastAPI(title="Sextant", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def observe(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = resolve_request_id(request.headers.get("x-request-id"))
        request.state.request_id = request_id
        request.state.log_fields = {}
        started = monotonic()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled error", extra={"fields": {"request_id": request_id}})
            response = error_response(500, "internal_error", "internal error", request_id)
        response.headers["X-Request-Id"] = request_id
        fields: dict[str, Any] = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": int((monotonic() - started) * 1000),
            **request.state.log_fields,
        }
        logger.info("request", extra={"fields": fields})
        return response

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: Exception) -> Response:
        error = cast(ApiError, exc)
        request.state.log_fields["error_code"] = error.code
        return error_response(
            error.status, error.code, error.message, request.state.request_id, error.headers
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: Exception) -> Response:
        message = validation_message(cast(RequestValidationError, exc))
        request.state.log_fields["error_code"] = "invalid_request"
        return error_response(422, "invalid_request", message, request.state.request_id)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(request: Request, exc: Exception) -> Response:
        http_error = cast(StarletteHTTPException, exc)
        request.state.log_fields["error_code"] = "invalid_request"
        return error_response(
            http_error.status_code,
            "invalid_request",
            str(http_error.detail),
            request.state.request_id,
        )

    def check_rate(limiter: RateLimiter, request: Request) -> None:
        wait = limiter.acquire(client_key(request, cfg.trust_proxy))
        if wait > 0:
            retry_after = max(1, math.ceil(wait))
            raise ApiError(
                429, "rate_limited", "too many requests", {"Retry-After": str(retry_after)}
            )

    def require_ready() -> Retriever:
        if index.retriever is None:
            raise ApiError(503, "unavailable", "index is loading")
        return index.retriever

    @app.get("/v1/health")
    def health() -> JSONResponse:
        if not index.ready:
            body = HealthResponse(
                status="unavailable", corpus_chunks=0, index="failed" if index.failed else "loading"
            )
            return JSONResponse(body.model_dump(), status_code=503)
        return JSONResponse(
            HealthResponse(status="ok", corpus_chunks=len(index.chunks), index="ready").model_dump()
        )

    @app.post("/v1/search")
    def search(body: SearchRequest, request: Request) -> SearchResponse:
        started = monotonic()
        check_rate(search_limiter, request)
        active = require_ready()
        lang = body.lang or detect_lang(body.query)
        hits = active.search(body.query, lang, body.top_k)
        results = [
            SearchResult(
                chunk_id=hit.chunk_id,
                score=hit.score,
                title=chunk_title(index.chunks[hit.chunk_id]),
                url=index.chunks[hit.chunk_id].url,
                lang=index.chunks[hit.chunk_id].lang,
                text=index.chunks[hit.chunk_id].text,
            )
            for hit in hits
            if hit.chunk_id in index.chunks
        ]
        request.state.log_fields.update(
            {
                "lang": lang,
                "top_k": body.top_k,
                "results": len(results),
                "query_chars": len(body.query),
            }
        )
        return SearchResponse(results=results, latency_ms=int((monotonic() - started) * 1000))

    @app.post("/v1/ask")
    def ask(body: AskRequest, request: Request) -> AskResponse:
        deadline = Deadline(cfg.request_timeout_s, monotonic)
        started = monotonic()
        check_rate(ask_limiter, request)
        active = require_ready()
        if budget.exhausted():
            raise ApiError(503, "unavailable", "daily budget exhausted")
        lang = body.lang or detect_lang(body.question)
        service = AnswerService(
            active,
            index.chunks,
            llm,
            max_output_tokens=cfg.max_output_tokens,
            now=now,
            on_cost=budget.add,
        )
        try:
            result = service.answer(body.question, lang, body.top_k, deadline)
        except (ProviderTimeout, AnswerTimeoutError) as error:
            raise ApiError(504, "timeout", "time budget exceeded") from error
        except MalformedAnswerError as error:
            raise ApiError(
                502, "upstream_error", "the model returned an unusable answer"
            ) from error
        except ProviderError as error:
            raise ApiError(502, "upstream_error", "the language model failed") from error
        request.state.log_fields.update(
            {
                "provider": result.provider,
                "model": result.model,
                "lang": result.lang,
                "top_k": result.top_k,
                "refused": result.refused,
                "refusal_reason": result.refusal_reason,
                "citations": [c.chunk_id for c in result.citations],
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
                "cost_usd": result.usage.cost_usd,
                "question_chars": len(body.question),
            }
        )
        return AskResponse(
            answer=result.answer,
            refused=result.refused,
            citations=list(result.citations),
            latency_ms=int((monotonic() - started) * 1000),
            usage=result.usage,
        )

    return app
