"""The flash-versus-pro judge measurement: statistics, parsing, and the coded rule."""

import json
from pathlib import Path

import numpy as np
import pytest

from sextant.eval.judge_models import (
    OUT,
    TASKS,
    UNUSABLE,
    Replay,
    decide,
    kappa,
    measure,
    reassessment_decisions,
    relevance_decisions,
    shown_sections,
    strict_decisions,
)
from sextant.llm import FAST_MODEL, MODELS, STRONG_MODEL, Request, model_for

USER = (
    "Question (fr): q ?\nReference answer: a\n\nSections (fr):\n\n[S1] A — x\ntext\n\n[S2] B — y\nt"
)


def test_kappa_matches_a_hand_computed_value() -> None:
    # observed 0.7, expected 0.5 -> (0.7 - 0.5) / (1 - 0.5)
    assert kappa(np.array([[20, 5], [10, 15]])) == pytest.approx(0.4)


def test_kappa_counts_perfect_agreement_on_one_class_as_one() -> None:
    assert kappa(np.array([[12, 0], [0, 0]])) == 1.0


def test_shown_sections_reads_labels_in_order() -> None:
    assert shown_sections(USER) == [("S1", "A — x"), ("S2", "B — y")]


def test_relevance_decisions_label_each_shown_section() -> None:
    decisions = relevance_decisions({"relevant": ["S2", "S9"], "answerable": True}, USER)
    assert decisions == {"section": ["no", "yes"], "answerable": ["yes"]}
    assert relevance_decisions(None, USER) == {
        "section": [UNUSABLE, UNUSABLE],
        "answerable": [UNUSABLE],
    }


def test_reassessment_decisions_read_unknown_verdicts_as_contradicted() -> None:
    decisions = reassessment_decisions({"old_answer": "maybe", "answerable": True}, USER)
    assert decisions == {
        "old_answer": ["contradicted"],
        "answerable": ["yes"],
        "question_valid": ["yes"],
    }


def test_strict_decisions_need_every_claim_supported() -> None:
    claims = [{"claim": "c", "status": "supported"}, {"claim": "d", "status": "contradicted"}]
    assert strict_decisions({"verdict": "consistent", "claims": claims}, "") == {
        "consistent": ["no"]
    }
    assert strict_decisions({"verdict": "consistent", "claims": claims[:1]}, "") == {
        "consistent": ["yes"]
    }


def test_the_answer_judge_switches_only_with_both_claim_judges() -> None:
    both = decide({"relevance_judge": False, "reassessment": True, "strict_check": True})
    assert both["answer_judge"] == FAST_MODEL
    assert both["relevance_judge"] == STRONG_MODEL
    assert both["draft"] == FAST_MODEL
    one = decide({"relevance_judge": True, "reassessment": True, "strict_check": False})
    assert one["answer_judge"] == STRONG_MODEL


def test_measure_counts_unusable_answers_as_disagreements() -> None:
    task = TASKS[2]  # strict check
    request = Request(model=STRONG_MODEL, system=task.system, user="", max_tokens=1, temperature=0)
    ok = {"verdict": "consistent", "claims": [{"claim": "c", "status": "supported"}]}
    replays = [
        Replay(cid="q1", request=request, pro=ok, flash=ok),
        Replay(cid="q2", request=request, pro={"verdict": "not_consistent"}, flash=None),
    ]
    result = measure(task, replays)
    assert result["unusable"] == {"pro": 0, "flash": 1}
    assert result["decisions"]["consistent"]["agreement"] == 0.5
    assert result["disagreements"] == [
        {"id": "q2", "decision": "consistent", "unit": "", "pro": "no", "flash": UNUSABLE}
    ]
    assert not result["switch"]


def test_a_forced_model_overrides_every_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEXTANT_EVAL_MODEL", STRONG_MODEL)
    assert model_for("draft") == STRONG_MODEL
    monkeypatch.delenv("SEXTANT_EVAL_MODEL")
    assert model_for("draft") == FAST_MODEL


@pytest.mark.skipif(not Path(OUT).exists(), reason="judge measurement not run yet")
def test_the_models_in_code_are_the_measured_decision() -> None:
    decided = json.loads(Path(OUT).read_text(encoding="utf-8"))["models"]
    assert decided == MODELS
