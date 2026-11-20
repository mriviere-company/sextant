"""Retrieval metrics, implemented from their definitions.

All metrics work on a ranked list of *sections* (chunk hits are first mapped
to their section; a section keeps the rank of its best chunk) against the set
of relevant sections, with binary relevance:

- hit@k: 1 if at least one relevant section is in the top k.
- recall@k: share of the relevant sections found in the top k.
- precision@k: share of the top k that is relevant (divided by k, even when
  fewer than k results came back: returning nothing is not rewarded).
- reciprocal rank (MRR when averaged): 1 / rank of the first relevant section.
- nDCG@k: DCG with gain 1 and log2 discount, normalized by the ideal ranking.

`paired_bootstrap` gives a confidence interval on the mean difference between
two strategies over the same questions, which is how the benchmark decides
whether a difference is real or noise.
"""

from __future__ import annotations

import math
import random
from collections.abc import Hashable, Sequence


def dedupe[T: Hashable](ranked: Sequence[T]) -> list[T]:
    """Keep the first occurrence of each item, in order."""
    seen: set[T] = set()
    out: list[T] = []
    for item in ranked:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def hit_at_k[T: Hashable](ranked: Sequence[T], relevant: set[T], k: int) -> float:
    """1.0 if any relevant item is in the top k."""
    return 1.0 if any(item in relevant for item in ranked[:k]) else 0.0


def recall_at_k[T: Hashable](ranked: Sequence[T], relevant: set[T], k: int) -> float:
    """Share of relevant items found in the top k."""
    if not relevant:
        raise ValueError("recall is undefined without relevant items")
    return len(relevant.intersection(ranked[:k])) / len(relevant)


def precision_at_k[T: Hashable](ranked: Sequence[T], relevant: set[T], k: int) -> float:
    """Relevant items in the top k, divided by k."""
    return sum(1 for item in ranked[:k] if item in relevant) / k


def reciprocal_rank[T: Hashable](ranked: Sequence[T], relevant: set[T]) -> float:
    """1 / rank of the first relevant item, 0 if none."""
    for rank, item in enumerate(ranked, start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k[T: Hashable](ranked: Sequence[T], relevant: set[T], k: int) -> float:
    """Compute the normalized discounted cumulative gain, binary relevance."""
    if not relevant:
        raise ValueError("nDCG is undefined without relevant items")
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, item in enumerate(ranked[:k], start=1)
        if item in relevant
    )
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(len(relevant), k) + 1))
    return dcg / ideal


def mean(values: Sequence[float]) -> float:
    """Arithmetic mean (0 for an empty sequence)."""
    return sum(values) / len(values) if values else 0.0


def percentile(values: Sequence[float], q: float) -> float:
    """Nearest-rank percentile, `q` in [0, 100]."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100 * len(ordered)))
    return ordered[rank - 1]


def paired_bootstrap(
    a: Sequence[float],
    b: Sequence[float],
    *,
    resamples: int = 10_000,
    confidence: float = 0.95,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Mean of `b - a` and its bootstrap confidence interval, resampling questions."""
    if len(a) != len(b) or not a:
        raise ValueError("paired samples of equal, non-zero length expected")
    diffs = [y - x for x, y in zip(a, b, strict=True)]
    rng = random.Random(seed)
    n = len(diffs)
    stats = sorted(mean([diffs[rng.randrange(n)] for _ in range(n)]) for _ in range(resamples))
    tail = (1 - confidence) / 2
    low = stats[int(tail * resamples)]
    high = stats[min(resamples - 1, int((1 - tail) * resamples))]
    return mean(diffs), low, high
