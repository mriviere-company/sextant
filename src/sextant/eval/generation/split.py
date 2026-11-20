"""Freeze the dev / test split *before* any human review or benchmark run.

Questions are split by **article**: every question drafted from an article
lands in the same split, so the test set never contains a question about a
passage that also has a (possibly translated) twin in dev. Groups are placed
greedily, largest first, on whichever side keeps the language x kind cells and
the totals most even. Seeded, hence reproducible.

Assigning splits to *candidates* rather than to validated questions means the
review cannot move a question from one split to the other: a rejected
candidate simply leaves its split smaller.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from collections.abc import Hashable, Mapping, Sequence

from sextant.eval.dataset import Split

TOTAL_WEIGHT = 4.0  # balance of the overall sizes matters more than of a single cell


def assign_splits(
    groups: Mapping[str, str],
    cells: Mapping[str, Hashable],
    seed: int = 42,
) -> dict[str, Split]:
    """Map item id → split; `groups` gives each item's group, `cells` its stratum."""
    rng = random.Random(seed)
    members: defaultdict[str, list[str]] = defaultdict(list)
    for item, group in groups.items():
        members[group].append(item)
    order: Sequence[str] = sorted(members, key=lambda g: (-len(members[g]), rng.random()))

    counts: dict[Split, Counter[Hashable]] = {"dev": Counter(), "test": Counter()}
    totals: dict[Split, int] = {"dev": 0, "test": 0}
    result: dict[str, Split] = {}

    def imbalance(side: Split, items: Sequence[str]) -> float:
        added = Counter(cells[i] for i in items)
        other: Split = "test" if side == "dev" else "dev"
        keys = set(counts["dev"]) | set(counts["test"]) | set(added)
        score = sum((counts[side][k] + added[k] - counts[other][k]) ** 2 for k in keys)
        return score + TOTAL_WEIGHT * (totals[side] + len(items) - totals[other]) ** 2

    for group in order:
        items = members[group]
        dev, test = imbalance("dev", items), imbalance("test", items)
        side: Split = (
            ("dev" if rng.random() < 0.5 else "test")
            if dev == test
            else ("dev" if dev < test else "test")
        )
        for item in items:
            result[item] = side
            counts[side][cells[item]] += 1
        totals[side] += len(items)
    return result
