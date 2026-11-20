"""The answer pipeline: retrieve, prompt, call the provider, enforce the citation guarantee.

The guarantees live here, in code, not in the prompt (docs/generation.md, "Output handling"):
a citation only ever refers to a chunk that was given to the model, a non-refused answer
always carries at least one valid citation, and a refusal carries none.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from sextant.generation.budget import Deadline, utc_now
from sextant.generation.pricing import cost_usd
from sextant.generation.prompt import (
    REFUSAL_TEXT,
    SYSTEM_PROMPT,
    build_user_message,
    chunk_title,
)
from sextant.generation.providers import (
    ChatRequest,
    ChatResult,
    LlmProvider,
    ProviderError,
)
from sextant.llm import LlmError, parse_json_object
from sextant.models import Chunk, Lang
from sextant.retrieval.base import Retriever

logger = logging.getLogger("sextant.generation")

MAX_ANSWER_CHARS = 2000
MAX_ATTEMPTS = 2  # the first call plus one retry on malformed output

REASON_MODEL_REFUSED = "model_refused"
REASON_UNCITED = "uncited_answer"
REASON_NO_CONTEXT = "no_context"

# `[3]`, `[3, 4]`; adjacent markers (`[3][4]`) are two matches. The leading whitespace is
# captured so that removing a marker leaves no double space.
_MARKER = re.compile(r"(\s*)\[\s*(\d{1,6}(?:\s*[,;]\s*\d{1,6})*)\s*\]")
_PARTIAL_MARKER = re.compile(r"\s*\[[\d\s,;]*$")
_NO_SPACE_BEFORE = frozenset(".,;:!?…)")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Citation(_Frozen):
    """A source of the answer, built from the chunk given under number `n`."""

    n: int
    chunk_id: str
    title: str
    url: str
    lang: Lang


class Usage(_Frozen):
    """Tokens and cost of a request (all provider calls, a retry included)."""

    input_tokens: int
    output_tokens: int
    cost_usd: float | None


class AnswerResult(_Frozen):
    """The outcome of the pipeline, before HTTP shaping."""

    answer: str
    refused: bool
    citations: tuple[Citation, ...]
    usage: Usage
    refusal_reason: str | None
    provider: str
    model: str
    lang: Lang
    top_k: int


class AnswerTimeoutError(RuntimeError):
    """The request's time budget was spent before the model could be called."""


class MalformedAnswerError(ProviderError):
    """The provider returned unparseable output twice."""


class _Outcome(_Frozen):
    answer: str
    refused: bool
    citations: tuple[Citation, ...]
    reason: str | None


def _strip_all_markers(text: str) -> str:
    return _MARKER.sub(_removal, text).strip()


def _removal(match: re.Match[str]) -> str:
    """Replace a removed marker by nothing, or one space when text follows directly."""
    following = match.string[match.end() : match.end() + 1]
    if not following or following.isspace() or following in _NO_SPACE_BEFORE:
        return ""
    return match.group(1)[:1]


def clean_citations(text: str, chunks: Sequence[Chunk]) -> tuple[str, tuple[Citation, ...]]:
    """Drop every marker that points outside `1..len(chunks)`; collect the valid ones.

    Returns the cleaned text and one citation per distinct valid number, in order of first
    appearance, built from the chunk that was given under that number.
    """
    count = len(chunks)
    order: list[int] = []

    def rewrite(match: re.Match[str]) -> str:
        numbers = [int(part) for part in re.split(r"[,;]", match.group(2))]
        valid = [n for n in numbers if 1 <= n <= count]
        for n in valid:
            if n not in order:
                order.append(n)
        if not valid:
            return _removal(match)
        kept = ", ".join(str(n) for n in valid)
        return f"{match.group(1)}[{kept}]"

    cleaned = _MARKER.sub(rewrite, text).strip()
    citations = tuple(
        Citation(
            n=n,
            chunk_id=chunks[n - 1].id,
            title=chunk_title(chunks[n - 1]),
            url=chunks[n - 1].url,
            lang=chunks[n - 1].lang,
        )
        for n in order
    )
    return cleaned, citations


def cap_answer(text: str) -> str:
    """Cut the answer at `MAX_ANSWER_CHARS`, never leaving half a citation marker."""
    if len(text) <= MAX_ANSWER_CHARS:
        return text
    return _PARTIAL_MARKER.sub("", text[:MAX_ANSWER_CHARS]).rstrip()


def apply_output_rules(
    answer: str, model_refused: bool, chunks: Sequence[Chunk], lang: Lang
) -> _Outcome:
    """Rules 2 to 6 of docs/generation.md on a parsed model output."""
    capped = cap_answer(answer)
    canonical = REFUSAL_TEXT[lang]
    if model_refused:
        text = _strip_all_markers(capped)
        return _Outcome(
            answer=text or canonical, refused=True, citations=(), reason=REASON_MODEL_REFUSED
        )
    cleaned, citations = clean_citations(capped, chunks)
    if not citations:
        return _Outcome(answer=canonical, refused=True, citations=(), reason=REASON_UNCITED)
    return _Outcome(answer=cleaned, refused=False, citations=citations, reason=None)


def parse_model_output(text: str) -> tuple[bool, str] | None:
    """`(refused, answer)` from the model's JSON, or None when it is unusable (rule 1)."""
    try:
        data = parse_json_object(_outermost_object(text))
    except LlmError:
        return None
    refused, answer = data.get("refused"), data.get("answer")
    if not isinstance(refused, bool) or not isinstance(answer, str):
        return None
    return refused, answer


def _outermost_object(text: str) -> str:
    """Take the outermost `{…}` so prose or a fence around the object is tolerated."""
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if 0 <= start < end else text


class AnswerService:
    """Answers a question from the wiki; one instance serves all requests."""

    def __init__(  # noqa: PLR0913 — wiring of a service, all keyword-only
        self,
        retriever: Retriever,
        chunks_by_id: Mapping[str, Chunk],
        provider: LlmProvider,
        *,
        max_output_tokens: int = 600,
        now: Callable[[], datetime] = utc_now,
        on_cost: Callable[[float], None] | None = None,
    ) -> None:
        self._retriever = retriever
        self._chunks = chunks_by_id
        self._provider = provider
        self._max_output_tokens = max_output_tokens
        self._now = now
        self._on_cost = on_cost
        self._warned_models: set[str] = set()

    def answer(self, question: str, lang: Lang, top_k: int, deadline: Deadline) -> AnswerResult:
        """Run the pipeline. Raises `AnswerTimeoutError`, `ProviderTimeout` or `ProviderError`."""
        hits = self._retriever.search(question, lang, top_k)
        chunks = [self._chunks[h.chunk_id] for h in hits if h.chunk_id in self._chunks][:top_k]
        if not chunks:
            return self._result(_no_context(lang), lang, top_k, [])
        user = build_user_message(question, chunks, lang)
        results: list[ChatResult] = []
        parsed: tuple[bool, str] | None = None
        for _ in range(MAX_ATTEMPTS):
            results.append(self._call(user, deadline))
            parsed = parse_model_output(results[-1].text)
            if parsed is not None:
                break
        if parsed is None:
            raise MalformedAnswerError("provider returned malformed output twice")
        outcome = apply_output_rules(parsed[1], parsed[0], chunks, lang)
        return self._result(outcome, lang, top_k, results)

    def _call(self, user: str, deadline: Deadline) -> ChatResult:
        remaining = deadline.remaining()
        if remaining <= 0:
            raise AnswerTimeoutError("time budget exhausted")
        request = ChatRequest(
            system=SYSTEM_PROMPT,
            user=user,
            max_output_tokens=self._max_output_tokens,
            timeout_s=remaining,
        )
        result = self._provider.complete(request)
        cost = self._cost(result)
        if cost is not None and self._on_cost is not None:
            self._on_cost(cost)
        return result

    def _cost(self, result: ChatResult) -> float | None:
        cost = cost_usd(
            result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cache_hit_tokens=result.cache_hit_tokens,
            at=self._now(),
        )
        if cost is None and result.model not in self._warned_models:
            self._warned_models.add(result.model)
            fields: dict[str, Any] = {"event": "unknown_model_price", "model": result.model}
            logger.warning("model missing from the price table", extra={"fields": fields})
        return cost

    def _result(
        self, outcome: _Outcome, lang: Lang, top_k: int, results: list[ChatResult]
    ) -> AnswerResult:
        costs = [self._cost(r) for r in results]
        total: float | None = None
        if all(c is not None for c in costs):
            total = round(sum(c for c in costs if c is not None), 6)
        return AnswerResult(
            answer=outcome.answer,
            refused=outcome.refused,
            citations=outcome.citations,
            usage=Usage(
                input_tokens=sum(r.input_tokens for r in results),
                output_tokens=sum(r.output_tokens for r in results),
                cost_usd=total,
            ),
            refusal_reason=outcome.reason,
            provider=self._provider.name,
            model=self._provider.model,
            lang=lang,
            top_k=top_k,
        )


def _no_context(lang: Lang) -> _Outcome:
    return _Outcome(answer=REFUSAL_TEXT[lang], refused=True, citations=(), reason=REASON_NO_CONTEXT)
