"""LLM providers behind one protocol: a deterministic fake, DeepSeek and Anthropic.

Keys come from the environment only (`DEEPSEEK_API_KEY`; the Anthropic SDK resolves its own
credentials). Every SDK client is injectable so tests never touch the network. SDK retries
are limited to one, because the request has a time budget that retries would eat.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

import anthropic
import openai
from pydantic import BaseModel, ConfigDict, Field

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODELS = {
    "fake": "fake",
    "deepseek": "deepseek-flash",
    "anthropic": "claude-opus-5-5",
}

# Claude Opus 5.5 always thinks, and thinking tokens count against `max_tokens`: leave room
# for it on top of the answer, with a floor.
ANTHROPIC_THINKING_HEADROOM = 3500
ANTHROPIC_MIN_MAX_TOKENS = 4000
SDK_MAX_RETRIES = 1

ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"refused": {"type": "boolean"}, "answer": {"type": "string"}},
    "required": ["refused", "answer"],
    "additionalProperties": False,
}


class ChatRequest(BaseModel):
    """One completion request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    system: str
    user: str
    max_output_tokens: int = Field(gt=0)
    timeout_s: float = Field(gt=0)


class ChatResult(BaseModel):
    """What a provider returned. `input_tokens` is the whole prompt, cache hits included."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cache_hit_tokens: int = Field(default=0, ge=0)
    provider: str
    model: str


class ProviderError(RuntimeError):
    """The provider failed (HTTP error, unusable response)."""


class ProviderTimeout(ProviderError):  # noqa: N818 — name fixed by the design
    """The provider did not answer within the time given. Catch this before `ProviderError`."""


class LlmProvider(Protocol):
    """A chat model answering one request."""

    name: str
    model: str

    def complete(self, request: ChatRequest) -> ChatResult:
        """Return the model's reply, or raise `ProviderError` / `ProviderTimeout`."""
        ...


Reply = str | Exception
DEFAULT_FAKE_REPLY = json.dumps({"refused": False, "answer": "Réponse de test [1]."})


class FakeProvider:
    """Deterministic provider for tests and offline runs; every call costs nothing.

    `replies` is a callable of the request, or a sequence consumed in order (the last one
    repeats). A reply that is an exception is raised. Calls are recorded in `calls`.
    """

    name = "fake"
    model = "fake"

    def __init__(
        self, replies: Sequence[Reply] | Callable[[ChatRequest], Reply] | None = None
    ) -> None:
        self._replies = replies if replies is not None else [DEFAULT_FAKE_REPLY]
        self.calls: list[ChatRequest] = []
        self._lock = threading.Lock()

    def _next_reply(self, request: ChatRequest) -> Reply:
        with self._lock:
            index = len(self.calls)
            self.calls.append(request)
        if callable(self._replies):
            return self._replies(request)
        return self._replies[min(index, len(self._replies) - 1)]

    def complete(self, request: ChatRequest) -> ChatResult:
        """Return the scripted reply (or raise it)."""
        reply = self._next_reply(request)
        if isinstance(reply, Exception):
            raise reply
        return ChatResult(
            text=reply,
            input_tokens=max(1, len(request.system + request.user) // 4),
            output_tokens=max(1, len(reply) // 4),
            provider=self.name,
            model=self.model,
        )


class DeepSeekProvider:
    """DeepSeek through the OpenAI SDK: JSON mode, thinking disabled."""

    name = "deepseek"

    def __init__(self, model: str = DEFAULT_MODELS["deepseek"], client: Any = None) -> None:
        if client is None:
            api_key = os.environ.get("DEEPSEEK_API_KEY")
            if not api_key:
                raise RuntimeError("DEEPSEEK_API_KEY is not set (see .env.example)")
            client = openai.OpenAI(
                api_key=api_key, base_url=DEEPSEEK_BASE_URL, max_retries=SDK_MAX_RETRIES
            )
        self.model = model
        self._client = client

    def complete(self, request: ChatRequest) -> ChatResult:
        """Call chat completions; the prompt must mention JSON for JSON mode to accept it."""
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": request.system},
                    {"role": "user", "content": request.user},
                ],
                max_tokens=request.max_output_tokens,
                temperature=0.0,
                response_format={"type": "json_object"},
                extra_body={"thinking": {"type": "disabled"}},
                timeout=request.timeout_s,
            )
        except openai.APITimeoutError as error:
            raise ProviderTimeout("DeepSeek timed out") from error
        except openai.OpenAIError as error:
            raise ProviderError(f"DeepSeek call failed: {type(error).__name__}") from error
        if not response.choices:
            raise ProviderError("DeepSeek returned no choice")
        usage = response.usage
        return ChatResult(
            text=response.choices[0].message.content or "",
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            cache_hit_tokens=int(getattr(usage, "prompt_cache_hit_tokens", 0) or 0),
            provider=self.name,
            model=self.model,
        )


class AnthropicProvider:
    """Claude through the Anthropic SDK: structured output, low effort, no sampling params."""

    name = "anthropic"

    def __init__(self, model: str = DEFAULT_MODELS["anthropic"], client: Any = None) -> None:
        if client is None:
            # Credentials are resolved by the SDK from the environment.
            client = anthropic.Anthropic(max_retries=SDK_MAX_RETRIES)
        self.model = model
        self._client = client

    def complete(self, request: ChatRequest) -> ChatResult:
        """Call the Messages API; a safety refusal becomes a refused answer."""
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=max(
                    ANTHROPIC_MIN_MAX_TOKENS,
                    request.max_output_tokens + ANTHROPIC_THINKING_HEADROOM,
                ),
                system=request.system,
                messages=[{"role": "user", "content": request.user}],
                output_config={
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": ANSWER_SCHEMA},
                },
                timeout=request.timeout_s,
            )
        except anthropic.APITimeoutError as error:
            raise ProviderTimeout("Anthropic timed out") from error
        except anthropic.APIError as error:
            raise ProviderError(f"Anthropic call failed: {type(error).__name__}") from error
        usage = response.usage
        cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        cache_write = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
        if response.stop_reason == "max_tokens":
            raise ProviderError("Anthropic answer truncated at max_tokens")
        if response.stop_reason == "refusal":
            text = json.dumps({"refused": True, "answer": ""})
        else:
            text = "".join(b.text for b in response.content if b.type == "text")
        return ChatResult(
            text=text,
            input_tokens=int(usage.input_tokens or 0) + cache_read + cache_write,
            output_tokens=int(usage.output_tokens or 0),
            cache_hit_tokens=cache_read,
            provider=self.name,
            model=self.model,
        )


def make_provider(name: str = "fake", model: str | None = None) -> LlmProvider:
    """Build a provider by name (`fake`, `deepseek`, `anthropic`)."""
    if name not in DEFAULT_MODELS:
        raise ValueError(f"unknown LLM provider: {name!r} (expected {sorted(DEFAULT_MODELS)})")
    chosen = model or DEFAULT_MODELS[name]
    if name == "deepseek":
        return DeepSeekProvider(chosen)
    if name == "anthropic":
        return AnthropicProvider(chosen)
    return FakeProvider()


def provider_from_env(env: Mapping[str, str] | None = None) -> LlmProvider:
    """Build the provider named by `SEXTANT_LLM_PROVIDER` / `SEXTANT_LLM_MODEL` (default: fake)."""
    source = os.environ if env is None else env
    return make_provider(
        source.get("SEXTANT_LLM_PROVIDER", "fake"), source.get("SEXTANT_LLM_MODEL")
    )
