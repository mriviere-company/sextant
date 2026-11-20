import json
from pathlib import Path

import pytest

from sextant.eval.dataset import EvalItem, SectionRef, load_items
from sextant.eval.retrieval_bench import compare, render_markdown, run_strategy
from sextant.retrieval.base import Hit

SECTIONS = {
    "fr:fleet#a:0": SectionRef(slug="fleet", section_index=0),
    "fr:fleet#a:1": SectionRef(slug="fleet", section_index=0),
    "fr:market#b:0": SectionRef(slug="market", section_index=1),
}
ITEMS = [
    EvalItem(
        id="q1",
        question="Comment construire une flotte ?",
        lang="fr",
        kind="procedural",
        split="dev",
        relevant=(SectionRef(slug="fleet", section_index=0),),
    ),
    EvalItem(
        id="q2",
        question="Quel est le meilleur restaurant ?",
        lang="fr",
        kind="unanswerable",
        split="dev",
    ),
]


class _Fixed:
    def __init__(self, name: str, ids: list[str]) -> None:
        self._name, self._ids = name, ids

    @property
    def name(self) -> str:
        return self._name

    def search(self, query: str, lang: str, k: int) -> list[Hit]:
        return [Hit(chunk_id=i, score=1.0) for i in self._ids[:k]]


def _clock() -> float:
    _clock.t += 0.002  # type: ignore[attr-defined]
    return _clock.t  # type: ignore[attr-defined]


_clock.t = 0.0  # type: ignore[attr-defined]


def test_run_strategy_dedupes_sections_and_skips_unanswerable() -> None:
    # two chunks of the same relevant section: counted once, at the best rank
    result = run_strategy(
        _Fixed("s", ["fr:market#b:0", "fr:fleet#a:1", "fr:fleet#a:0"]), ITEMS, SECTIONS, _clock
    )
    assert list(result["per_question"]) == ["q1"]
    assert result["overall"]["mrr"] == 0.5
    assert result["overall"]["hit@1"] == 0.0
    assert result["by_lang"]["fr"]["n"] == 1
    assert result["latency_ms"]["p50"] == pytest.approx(2.0)


class _Recording(_Fixed):
    def __init__(self, name: str, ids: list[str]) -> None:
        super().__init__(name, ids)
        self.langs: list[str] = []

    def search(self, query: str, lang: str, k: int) -> list[Hit]:
        self.langs.append(lang)
        return super().search(query, lang, k)


def test_cross_lingual_questions_are_searched_in_their_corpus_and_reported_apart() -> None:
    cross = EvalItem(
        id="q3",
        question="How do I build a fleet?",
        lang="en",
        corpus_lang="fr",
        kind="procedural",
        split="dev",
        relevant=(SectionRef(slug="fleet", section_index=0),),
    )
    retriever = _Recording("s", ["fr:fleet#a:0"])
    result = run_strategy(retriever, [*ITEMS, cross], SECTIONS, _clock)
    assert retriever.langs == ["fr", "fr"]  # q1 in its language, q3 in the French corpus
    assert list(result["per_question"]) == ["q1"]
    assert list(result["per_question_cross_lingual"]) == ["q3"]
    assert result["cross_lingual"]["n"] == 1
    assert "en" not in result["by_lang"]
    report = {
        "meta": {
            "split": "dev",
            "questions": 3,
            "answerable": 2,
            "monolingual_answerable": 1,
            "baseline": "s",
            "results_file": "x.json",
        },
        "results": {"s": result},
        "comparisons": [],
    }
    assert "Cross-lingual questions" in render_markdown(report)


def test_compare_and_markdown() -> None:
    results = {
        "base": run_strategy(
            _Fixed("base", ["fr:market#b:0", "fr:fleet#a:0"]), ITEMS, SECTIONS, _clock
        ),
        "new": run_strategy(_Fixed("new", ["fr:fleet#a:0"]), ITEMS, SECTIONS, _clock),
    }
    comparisons = compare(results, "base")
    mrr = next(c for c in comparisons if c["metric"] == "mrr")
    assert mrr["delta"] == 0.5
    report = {
        "meta": {
            "split": "dev",
            "questions": 2,
            "answerable": 1,
            "monolingual_answerable": 1,
            "baseline": "base",
            "results_file": "x.json",
        },
        "results": results,
        "comparisons": comparisons,
    }
    markdown = render_markdown(report)
    assert "| `new` | 1.000 |" in markdown
    assert "Against `base`" in markdown


def test_dataset_validation(tmp_path: Path) -> None:
    good = {
        "id": "a",
        "question": "Où ?",
        "lang": "fr",
        "kind": "factual",
        "split": "dev",
        "relevant": [{"slug": "fleet", "section_index": 0}],
    }
    path = tmp_path / "q.jsonl"
    path.write_text(
        json.dumps(good) + "\n" + json.dumps({**good, "id": "b", "split": "test"}) + "\n"
    )
    assert [i.id for i in load_items(path, "dev")] == ["a"]

    path.write_text(json.dumps({**good, "kind": "unanswerable"}) + "\n")
    with pytest.raises(ValueError, match="cannot have relevant"):
        load_items(path)

    path.write_text(json.dumps({**good, "corpus_lang": "fr"}) + "\n")
    with pytest.raises(ValueError, match="cross-lingual"):
        load_items(path)

    path.write_text(json.dumps(good) + "\n" + json.dumps(good) + "\n")
    with pytest.raises(ValueError, match="duplicate"):
        load_items(path)
