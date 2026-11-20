import json
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import openai
import pytest

from sextant.generation.providers import (
    ANSWER_SCHEMA,
    AnthropicProvider,
    ChatRequest,
    DeepSeekProvider,
    FakeProvider,
    ProviderError,
    ProviderTimeout,
    make_provider,
    provider_from_env,
)

REQUEST = ChatRequest(system="sys JSON", user="usr", max_output_tokens=600, timeout_s=12.5)
HTTP_REQUEST = httpx2.Request("POST", "https://example.invalid/")


def _status_error(cls: Any) -> Any:
    response = httpx2.Response(500, request=HTTP_REQUEST)
    return cls("boom", response=response, body=None)


class _Create:
    """A `create` method returning or raising what it was given, recording its kwargs."""

    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def _deepseek(outcome: Any) -> tuple[DeepSeekProvider, _Create]:
    create = _Create(outcome)
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return DeepSeekProvider(client=client), create


def _completion(content: str | None = '{"refused": false, "answer": "x [1]"}') -> Any:
    usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20, prompt_cache_hit_tokens=40)
    choice = SimpleNamespace(message=SimpleNamespace(content=content), finish_reason="stop")
    return SimpleNamespace(choices=[choice], usage=usage)


def test_deepseek_request_parameters_and_usage_mapping() -> None:
    provider, create = _deepseek(_completion())
    result = provider.complete(REQUEST)
    call = create.calls[0]
    assert call["model"] == "deepseek-flash"
    assert call["response_format"] == {"type": "json_object"}
    assert call["extra_body"] == {"thinking": {"type": "disabled"}}
    assert call["max_tokens"] == 600
    assert call["timeout"] == 12.5
    assert call["messages"] == [
        {"role": "system", "content": "sys JSON"},
        {"role": "user", "content": "usr"},
    ]
    assert (result.input_tokens, result.output_tokens, result.cache_hit_tokens) == (100, 20, 40)
    assert (result.provider, result.model) == ("deepseek", "deepseek-flash")
    assert json.loads(result.text)["refused"] is False


def test_deepseek_missing_cache_field_and_empty_content() -> None:
    usage = SimpleNamespace(prompt_tokens=5, completion_tokens=1)
    choice = SimpleNamespace(message=SimpleNamespace(content=None), finish_reason="stop")
    provider, _ = _deepseek(SimpleNamespace(choices=[choice], usage=usage))
    result = provider.complete(REQUEST)
    assert result.cache_hit_tokens == 0
    assert result.text == ""


def test_deepseek_maps_sdk_errors() -> None:
    provider, _ = _deepseek(openai.APITimeoutError(request=HTTP_REQUEST))
    with pytest.raises(ProviderTimeout):
        provider.complete(REQUEST)
    provider, _ = _deepseek(_status_error(openai.InternalServerError))
    with pytest.raises(ProviderError) as info:
        provider.complete(REQUEST)
    assert not isinstance(info.value, ProviderTimeout)
    provider, _ = _deepseek(SimpleNamespace(choices=[], usage=None))
    with pytest.raises(ProviderError):
        provider.complete(REQUEST)


def test_deepseek_requires_its_key_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        DeepSeekProvider()


def _message(
    stop_reason: str = "end_turn", text: str = '{"refused": false, "answer": "a [1]"}'
) -> Any:
    usage = SimpleNamespace(
        input_tokens=30, output_tokens=50, cache_read_input_tokens=10, cache_creation_input_tokens=5
    )
    content = [
        SimpleNamespace(type="thinking", thinking=""),
        SimpleNamespace(type="text", text=text),
    ]
    return SimpleNamespace(content=content, stop_reason=stop_reason, usage=usage)


def _claude(outcome: Any) -> tuple[AnthropicProvider, _Create]:
    create = _Create(outcome)
    return AnthropicProvider(
        client=SimpleNamespace(messages=SimpleNamespace(create=create))
    ), create


def test_anthropic_request_parameters_and_usage_mapping() -> None:
    provider, create = _claude(_message())
    result = provider.complete(REQUEST)
    call = create.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"] == {
        "effort": "low",
        "format": {"type": "json_schema", "schema": ANSWER_SCHEMA},
    }
    assert call["max_tokens"] >= 4000  # headroom for the always-on thinking
    for forbidden in ("temperature", "top_p", "top_k", "thinking"):
        assert forbidden not in call
    assert call["system"] == "sys JSON"
    assert call["messages"] == [{"role": "user", "content": "usr"}]
    assert call["timeout"] == 12.5
    # input_tokens counts the whole prompt: uncached + cache read + cache write
    assert (result.input_tokens, result.output_tokens, result.cache_hit_tokens) == (45, 50, 10)
    assert json.loads(result.text) == {"refused": False, "answer": "a [1]"}


def test_anthropic_max_tokens_follows_a_large_output_budget() -> None:
    provider, create = _claude(_message())
    provider.complete(REQUEST.model_copy(update={"max_output_tokens": 5000}))
    assert create.calls[0]["max_tokens"] == 8500


def test_anthropic_refusal_becomes_a_refused_answer() -> None:
    provider, _ = _claude(_message(stop_reason="refusal", text=""))
    assert json.loads(provider.complete(REQUEST).text) == {"refused": True, "answer": ""}


def test_anthropic_max_tokens_is_a_provider_error() -> None:
    provider, _ = _claude(_message(stop_reason="max_tokens"))
    with pytest.raises(ProviderError):
        provider.complete(REQUEST)


def test_anthropic_maps_sdk_errors() -> None:
    provider, _ = _claude(anthropic.APITimeoutError(request=HTTP_REQUEST))
    with pytest.raises(ProviderTimeout):
        provider.complete(REQUEST)
    for error in (
        _status_error(anthropic.InternalServerError),
        anthropic.APIConnectionError(request=HTTP_REQUEST),
    ):
        provider, _ = _claude(error)
        with pytest.raises(ProviderError) as info:
            provider.complete(REQUEST)
        assert not isinstance(info.value, ProviderTimeout)


def test_fake_provider_scripts_replies_and_records_calls() -> None:
    provider = FakeProvider(["a", RuntimeError("down"), "c"])
    assert provider.complete(REQUEST).text == "a"
    with pytest.raises(RuntimeError, match="down"):
        provider.complete(REQUEST)
    assert provider.complete(REQUEST).text == "c"
    assert provider.complete(REQUEST).text == "c"  # the last reply repeats
    assert len(provider.calls) == 4
    assert FakeProvider(lambda request: request.user.upper()).complete(REQUEST).text == "USR"


def test_factory_selects_provider_and_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "not-a-real-key")
    assert make_provider().name == "fake"
    assert make_provider("deepseek").model == "deepseek-flash"
    assert make_provider("deepseek", "deepseek-v4-pro").model == "deepseek-v4-pro"
    assert provider_from_env({}).name == "fake"
    env = {"SEXTANT_LLM_PROVIDER": "deepseek", "SEXTANT_LLM_MODEL": "deepseek-v4-pro"}
    chosen = provider_from_env(env)
    assert (chosen.name, chosen.model) == ("deepseek", "deepseek-v4-pro")
    with pytest.raises(ValueError, match="unknown LLM provider"):
        make_provider("gpt")
