from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from sextant.llm import (
    BudgetExceededError,
    DeepSeekJsonLlm,
    DiskCache,
    LlmError,
    Request,
    parse_json_object,
)

REQUEST = Request(model="m", system="s", user="u", max_tokens=50, temperature=0.0)


class _Completions:
    def __init__(self, answers: list[tuple[str, str]]) -> None:
        self.answers = answers
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        content, finish = self.answers.pop(0)
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, prompt_cache_hit_tokens=3)
        choice = SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish)
        return SimpleNamespace(choices=[choice], usage=usage)


def _llm(tmp_path: Path, answers: list[tuple[str, str]], budget: int = 1000) -> DeepSeekJsonLlm:
    completions = _Completions(answers)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return DeepSeekJsonLlm(DiskCache(tmp_path), budget=budget, client=client)


def test_parse_json_object_accepts_a_fence_and_rejects_non_objects() -> None:
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(LlmError):
        parse_json_object("[1, 2]")
    with pytest.raises(LlmError):
        parse_json_object("pas du json")


def test_answers_are_cached_and_thinking_is_disabled(tmp_path: Path) -> None:
    llm = _llm(tmp_path, [('{"ok": true}', "stop")])
    assert llm.complete_json(REQUEST) == {"ok": True}
    assert llm.complete_json(REQUEST) == {"ok": True}  # replayed from disk
    completions = llm._client.chat.completions
    assert len(completions.calls) == 1
    assert completions.calls[0]["extra_body"] == {"thinking": {"type": "disabled"}}
    assert llm.usage.calls == 1
    assert llm.usage.cached_calls == 1
    assert llm.usage.total_tokens == 15
    # a fresh client on the same cache directory spends nothing
    assert _llm(tmp_path, []).complete_json(REQUEST) == {"ok": True}


def test_invalid_json_is_retried_once_and_never_cached(tmp_path: Path) -> None:
    llm = _llm(tmp_path, [("nope", "stop"), ('{"a": 1}', "stop")])
    assert llm.complete_json(REQUEST) == {"a": 1}
    llm = _llm(tmp_path / "other", [("nope", "stop"), ("still not", "stop")])
    with pytest.raises(LlmError):
        llm.complete_json(REQUEST)
    assert DiskCache(tmp_path / "other").get(REQUEST) is None


def test_truncated_answers_fail(tmp_path: Path) -> None:
    with pytest.raises(LlmError, match="truncated"):
        _llm(tmp_path, [('{"a": ', "length")]).complete_json(REQUEST)


def test_budget_stops_the_run(tmp_path: Path) -> None:
    llm = _llm(tmp_path, [('{"a": 1}', "stop")], budget=10)
    llm.complete_json(REQUEST)
    other = REQUEST.model_copy(update={"user": "v"})
    with pytest.raises(BudgetExceededError):
        llm.complete_json(other)


def test_missing_key_is_a_clear_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        DeepSeekJsonLlm(DiskCache(tmp_path))
