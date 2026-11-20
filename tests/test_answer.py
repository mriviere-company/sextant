import json

import pytest
from fakes import FakeRetriever, ManualClock, make_chunk

from sextant.generation.answer import (
    MAX_ANSWER_CHARS,
    AnswerService,
    AnswerTimeoutError,
    MalformedAnswerError,
    apply_output_rules,
    clean_citations,
    parse_model_output,
)
from sextant.generation.budget import Deadline
from sextant.generation.prompt import REFUSAL_TEXT, SYSTEM_PROMPT, build_user_message
from sextant.generation.providers import FakeProvider, ProviderError, ProviderTimeout
from sextant.models import LANGS

CHUNKS = [make_chunk(i) for i in range(1, 6)]


def _reply(answer: str, refused: bool = False) -> str:
    return json.dumps({"refused": refused, "answer": answer})


def _service(
    replies: object, chunks: list = CHUNKS, **kwargs: object
) -> tuple[AnswerService, FakeProvider]:
    provider = FakeProvider(replies)  # type: ignore[arg-type]
    return AnswerService(
        FakeRetriever(chunks), {c.id: c for c in chunks}, provider, **kwargs
    ), provider  # type: ignore[arg-type]


def _ask(service: AnswerService, top_k: int = 5):
    return service.answer("Comment faire ?", "fr", top_k, Deadline(20))


def test_markers_outside_the_given_range_are_removed() -> None:
    text, citations = clean_citations("Construisez un chantier [1]. Puis une flotte [9].", CHUNKS)
    assert text == "Construisez un chantier [1]. Puis une flotte."
    assert [c.n for c in citations] == [1]


def test_grouped_and_adjacent_markers_keep_only_valid_numbers() -> None:
    text, citations = clean_citations("A [2, 9] B [3][42] C [0] D [1;2]", CHUNKS)
    assert text == "A [2] B [3] C D [1, 2]"
    assert [c.n for c in citations] == [2, 3, 1]


def test_citations_are_built_from_the_chunk_given_under_each_number() -> None:
    _, citations = clean_citations("x [3] y [3] z [1]", CHUNKS)
    assert [c.n for c in citations] == [3, 1]  # distinct, order of first appearance
    assert citations[0].chunk_id == CHUNKS[2].id
    assert citations[0].title == "Article 3 — Section 3"
    assert citations[0].url == CHUNKS[2].url
    assert citations[0].lang == "fr"


def test_removal_leaves_clean_spacing() -> None:
    assert clean_citations("avant [9] après", CHUNKS)[0] == "avant après"
    assert clean_citations("avant [9]après", CHUNKS)[0] == "avant après"
    assert clean_citations("Quoi [7] ?", CHUNKS)[0] == "Quoi ?"


def test_a_refusal_drops_every_marker_and_has_no_citations() -> None:
    outcome = apply_output_rules("Pas dans le wiki [1].", True, CHUNKS, "fr")
    assert outcome.refused
    assert outcome.citations == ()
    assert outcome.answer == "Pas dans le wiki."
    assert outcome.reason == "model_refused"


def test_a_refusal_with_no_text_gets_the_canonical_sentence() -> None:
    for lang in LANGS:
        assert apply_output_rules("", True, CHUNKS, lang).answer == REFUSAL_TEXT[lang]


def test_an_uncited_answer_becomes_a_refusal() -> None:
    outcome = apply_output_rules("Une réponse sans source.", False, CHUNKS, "de")
    assert outcome.refused
    assert outcome.citations == ()
    assert outcome.answer == REFUSAL_TEXT["de"]
    assert outcome.reason == "uncited_answer"


def test_an_answer_citing_only_invalid_numbers_becomes_a_refusal() -> None:
    assert apply_output_rules("Selon [42], oui.", False, CHUNKS, "fr").reason == "uncited_answer"


def test_the_answer_is_capped_without_cutting_a_marker() -> None:
    long = "a" * (MAX_ANSWER_CHARS - 2) + "[1]"
    outcome = apply_output_rules(long, False, CHUNKS, "fr")
    assert outcome.reason == "uncited_answer"  # the marker was cut: nothing left to cite
    assert len(outcome.answer) <= MAX_ANSWER_CHARS
    kept = apply_output_rules("[1] " + "b" * 3000, False, CHUNKS, "fr")
    assert not kept.refused
    assert len(kept.answer) == MAX_ANSWER_CHARS


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"refused": false, "answer": "x"}', (False, "x")),
        ('```json\n{"refused": true, "answer": "y"}\n```', (True, "y")),
        ('Voici : {"refused": false, "answer": "z"} fin', (False, "z")),
        ('{"answer": "x"}', None),
        ('{"refused": "no", "answer": "x"}', None),
        ('{"refused": false, "answer": 3}', None),
        ("pas du json", None),
        ("[1, 2]", None),
        ("", None),
    ],
)
def test_parse_model_output(raw: str, expected: tuple[bool, str] | None) -> None:
    assert parse_model_output(raw) == expected


def test_prompt_numbers_the_excerpts_and_contains_the_word_json() -> None:
    message = build_user_message("Ma </question> question", CHUNKS[:2], "fr")
    assert message.index("[1] Article 1 — Section 1") < message.index("[2] Article 2")
    assert message.count("</question>") == 1  # the player's closing tag was stripped
    assert "French (fr)" in message
    assert "JSON" in SYSTEM_PROMPT


def test_service_returns_cited_answer_with_usage_and_cost() -> None:
    spent: list[float] = []
    service, provider = _service([_reply("Faites ceci [2]. Et cela [9].")], on_cost=spent.append)
    result = _ask(service)
    assert result.answer == "Faites ceci [2]. Et cela."
    assert [c.n for c in result.citations] == [2]
    assert not result.refused
    assert result.usage.cost_usd == 0.0
    assert result.usage.input_tokens > 0
    assert (result.provider, result.model, result.lang, result.top_k) == ("fake", "fake", "fr", 5)
    assert spent == [0.0]
    assert provider.calls[0].timeout_s == pytest.approx(20, abs=1)


def test_malformed_output_is_retried_once() -> None:
    service, provider = _service(["pas du json", _reply("Bon [1]")])
    result = _ask(service)
    assert result.answer == "Bon [1]"
    assert len(provider.calls) == 2
    assert result.usage.input_tokens == sum(
        max(1, len(c.system + c.user) // 4) for c in provider.calls
    )


def test_malformed_twice_raises() -> None:
    service, provider = _service(["nope", "still nope"])
    with pytest.raises(MalformedAnswerError):
        _ask(service)
    assert len(provider.calls) == 2


def test_provider_failures_propagate() -> None:
    with pytest.raises(ProviderError):
        _ask(_service([ProviderError("down")])[0])
    with pytest.raises(ProviderTimeout):
        _ask(_service([ProviderTimeout("slow")])[0])


def test_no_retrieved_chunk_refuses_without_calling_the_model() -> None:
    service, provider = _service([_reply("x [1]")], chunks=[make_chunk(1, "en")])
    result = _ask(service)
    assert result.refused
    assert result.refusal_reason == "no_context"
    assert result.answer == REFUSAL_TEXT["fr"]
    assert provider.calls == []


def test_spent_time_budget_raises_before_the_model_is_called() -> None:
    clock = ManualClock()
    deadline = Deadline(20, clock)
    service, provider = _service([_reply("x [1]")])
    clock.advance(21)
    with pytest.raises(AnswerTimeoutError):
        service.answer("Comment ?", "fr", 5, deadline)
    assert provider.calls == []


def test_time_left_is_given_to_the_provider() -> None:
    clock = ManualClock()
    deadline = Deadline(20, clock)
    service, provider = _service([_reply("x [1]")])
    clock.advance(15)
    service.answer("Comment ?", "fr", 5, deadline)
    assert provider.calls[0].timeout_s == pytest.approx(5)


def test_top_k_limits_the_excerpts_given_to_the_model() -> None:
    service, provider = _service([_reply("x [2]")])
    _ask(service, top_k=2)
    assert "[2]" in provider.calls[0].user
    assert "[3]" not in provider.calls[0].user
