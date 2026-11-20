import json
from pathlib import Path
from typing import Any

import pytest

from sextant.eval.retrieval_decision import decide, main, merge, render

IDS = [f"q{i:03d}" for i in range(40)]


def _strategy(
    base: float, gain: float = 0.0, p95: float = 50.0, langs: dict[str, Any] | None = None
) -> dict[str, Any]:
    # Alternating scores give the bootstrap some variance around the mean gain.
    per_question = {
        q: {"ndcg@10": min(1.0, base + gain + (0.05 if i % 2 else -0.05))}
        for i, q in enumerate(IDS)
    }
    mean = sum(r["ndcg@10"] for r in per_question.values()) / len(IDS)
    return {
        "overall": {"ndcg@10": mean},
        "per_question": per_question,
        "latency_ms": {"p50": p95 / 2, "p95": p95},
        "by_lang": langs or {"fr": {"n": 20, "ndcg@10": mean}, "de": {"n": 10, "ndcg@10": mean}},
    }


def _first_stage() -> dict[str, Any]:
    return {
        "bm25": _strategy(0.5),
        "pg_fts": _strategy(0.5, -0.1),
        "dense:minilm": _strategy(0.5, 0.05),
        "dense:mpnet": _strategy(0.5, 0.06),  # +0.01 over minilm: not enough
        "dense:e5-large": _strategy(0.5, 0.10),  # +0.05 over minilm: replaces it
    }


def test_stops_and_names_the_next_strategies_to_run() -> None:
    decision = decide(_first_stage())
    assert decision["dense"] == "dense:e5-large"
    assert decision["lexical"] == "bm25"
    assert decision["pending"] == ["hybrid:e5-large"]
    rule1 = [s for s in decision["steps"] if s["rule"] == 1]
    assert [s["adopted"] for s in rule1] == [False, True]  # mpnet kept out, e5 adopted


def test_rerank_needs_the_gain_and_the_latency_budget() -> None:
    results = _first_stage()
    results["hybrid:e5-large"] = _strategy(0.5, 0.12)  # +0.02 over dense: adopted
    results["rerank:bge-m3:hybrid:e5-large"] = _strategy(0.5, 0.20, p95=4000)  # too slow
    results["rerank:bge-m3@10:hybrid:e5-large"] = _strategy(0.5, 0.16, p95=400)
    decision = decide(results)
    assert decision["first_stage"] == "hybrid:e5-large"
    assert decision["final"] == "rerank:bge-m3@10:hybrid:e5-large"
    assert "rerank:bge-m3@10" in render(decision, ["x.json"])


def test_without_gains_the_simpler_strategy_stays_and_rule_5_needs_15_questions() -> None:
    langs = {"fr": {"n": 20, "ndcg@10": 0.4}, "de": {"n": 10, "ndcg@10": 0.1}}
    results = {
        "bm25": _strategy(
            0.5, langs={"fr": {"n": 20, "ndcg@10": 0.5}, "de": {"n": 10, "ndcg@10": 0.5}}
        ),
        "pg_fts": _strategy(0.5),
        "dense:minilm": _strategy(0.5, 0.01, langs=langs),
        "dense:mpnet": _strategy(0.5, 0.01),
        "dense:e5-large": _strategy(0.5, 0.01),
        "hybrid:minilm": _strategy(0.5, 0.012),
        "rerank:bge-m3:dense:minilm": _strategy(0.5, 0.012),
        "rerank:bge-m3@10:dense:minilm": _strategy(0.5, 0.012),
    }
    decision = decide(results)
    assert decision["final"] == "dense:minilm"  # best single; hybrid gain under 0.01
    findings = {row["lang"]: row for row in decision["languages"]}
    assert findings["fr"]["finding"]  # 0.1 loss with 20 questions
    assert not findings["de"]["rule_applies"]  # 0.4 loss, but only 10 questions


def test_main_refuses_test_split_and_merge_refuses_mixed_splits(tmp_path: Path) -> None:
    report = {"meta": {"split": "test"}, "results": _first_stage()}
    path = tmp_path / "r.json"
    path.write_text(json.dumps(report))
    with pytest.raises(SystemExit, match="dev split only"):
        main([str(path), "--out", str(tmp_path / "d.json")])
    with pytest.raises(ValueError, match="several splits"):
        merge([report, {"meta": {"split": "dev"}, "results": {}}])
