import math

import pytest

from sextant.eval.metrics import (
    dedupe,
    hit_at_k,
    mean,
    ndcg_at_k,
    paired_bootstrap,
    percentile,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

RANKED = ["a", "b", "c", "d"]


def test_dedupe_keeps_first_occurrence() -> None:
    assert dedupe(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_hit_recall_precision() -> None:
    relevant = {"b", "z"}
    assert hit_at_k(RANKED, relevant, 1) == 0.0
    assert hit_at_k(RANKED, relevant, 2) == 1.0
    assert recall_at_k(RANKED, relevant, 4) == 0.5
    assert precision_at_k(RANKED, relevant, 2) == 0.5
    assert precision_at_k(["b"], relevant, 5) == 0.2  # short lists are not rewarded


def test_reciprocal_rank() -> None:
    assert reciprocal_rank(RANKED, {"c"}) == pytest.approx(1 / 3)
    assert reciprocal_rank(RANKED, {"z"}) == 0.0


def test_ndcg_matches_hand_computation() -> None:
    # relevant at ranks 1 and 3; ideal puts both at ranks 1 and 2
    dcg = 1 + 1 / math.log2(4)
    ideal = 1 + 1 / math.log2(3)
    assert ndcg_at_k(RANKED, {"a", "c"}, 10) == pytest.approx(dcg / ideal)
    assert ndcg_at_k(RANKED, {"a"}, 10) == 1.0


def test_metrics_reject_empty_relevance() -> None:
    with pytest.raises(ValueError, match="undefined"):
        recall_at_k(RANKED, set(), 5)
    with pytest.raises(ValueError, match="undefined"):
        ndcg_at_k(RANKED, set(), 5)


def test_mean_and_percentile() -> None:
    assert mean([]) == 0.0
    assert percentile([10.0, 20.0, 30.0, 40.0], 50) == 20.0
    assert percentile([10.0, 20.0, 30.0, 40.0], 95) == 40.0


def test_paired_bootstrap_detects_a_clear_gain_and_not_noise() -> None:
    a = [0.0] * 50
    better = [1.0] * 50
    delta, low, high = paired_bootstrap(a, better, resamples=2000)
    assert delta == 1.0
    assert low == high == 1.0

    noisy = [1.0, 0.0] * 25
    delta, low, high = paired_bootstrap([0.5] * 50, noisy, resamples=2000)
    assert delta == 0.0
    assert low < 0 < high


def test_paired_bootstrap_requires_paired_samples() -> None:
    with pytest.raises(ValueError, match="paired"):
        paired_bootstrap([1.0], [1.0, 2.0])
