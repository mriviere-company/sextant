"""Invariants of the committed evaluation files: CI fails if the frozen split drifts.

The split is assigned to the candidates before the human review; these tests
make that freeze checkable: every question of an article sits in one split,
the evaluation items keep their candidate's split, and only reviewed,
validated candidates become items.
"""

from collections import Counter, defaultdict
from pathlib import Path

import pytest

from sextant.eval.dataset import load_items
from sextant.eval.generation.models import Candidate, read_jsonl
from sextant.eval.generation.select import CROSS_LINGUAL_PER_LANG, MONOLINGUAL_PER_LANG
from sextant.models import LANGS

DATASET = Path(__file__).resolve().parents[1] / "eval" / "dataset"
CANDIDATES = DATASET / "v1" / "candidates.jsonl"  # the frozen v1 set
QUESTIONS = DATASET / "v1" / "questions.jsonl"
V2_CANDIDATES = DATASET / "candidates.jsonl"

pytestmark = pytest.mark.skipif(not CANDIDATES.exists(), reason="no candidates generated yet")


def _candidates() -> list[Candidate]:
    return read_jsonl(CANDIDATES, Candidate)


def test_candidates_follow_the_planned_mix() -> None:
    candidates = _candidates()
    per_lang = sum(MONOLINGUAL_PER_LANG.values()) + sum(CROSS_LINGUAL_PER_LANG.values())
    assert Counter(c.lang for c in candidates) == dict.fromkeys(LANGS, per_lang)
    assert (
        sum(c.kind == "unanswerable" for c in candidates)
        == 6 * MONOLINGUAL_PER_LANG["unanswerable"]
    )
    crossed = [c for c in candidates if c.corpus_lang]
    assert len(crossed) == 6 * sum(CROSS_LINGUAL_PER_LANG.values())
    assert all(c.corpus_lang != c.lang and c.kind != "unanswerable" for c in crossed)
    assert [c.id for c in candidates] == [f"q{n:03d}" for n in range(1, len(candidates) + 1)]


def test_the_split_is_frozen_by_article_and_balanced() -> None:
    candidates = _candidates()
    by_article: defaultdict[str, set[str]] = defaultdict(set)
    for c in candidates:
        if c.slug:
            by_article[c.slug].add(c.split)
    assert all(len(splits) == 1 for splits in by_article.values())
    sizes = Counter(c.split for c in candidates)
    assert abs(sizes["dev"] - sizes["test"]) <= 0.05 * len(candidates)
    for lang in LANGS:
        per = Counter(c.split for c in candidates if c.lang == lang)
        assert min(per["dev"], per["test"]) >= 0.4 * (per["dev"] + per["test"])


def test_relevance_matches_the_kind() -> None:
    for c in _candidates():
        if c.kind == "unanswerable":
            assert not c.relevant
            assert not c.sources
        else:
            assert set(c.sources) <= set(c.relevant)
            if c.kind == "multi_section":
                assert len(set(c.sources)) >= 2


@pytest.mark.skipif(not QUESTIONS.exists(), reason="review not built yet")
def test_items_keep_their_candidate_split_and_are_validated() -> None:
    candidates = {c.id: c for c in _candidates()}
    for item in load_items(QUESTIONS):
        candidate = candidates[item.id]
        assert item.validated
        assert item.split == candidate.split
        assert (item.lang, item.corpus_lang, item.kind) == (
            candidate.lang,
            candidate.corpus_lang,
            candidate.kind,
        )


@pytest.mark.skipif(not V2_CANDIDATES.exists(), reason="v2 not migrated yet")
def test_migration_keeps_ids_and_splits_of_every_v1_candidate() -> None:
    v1 = {c.id: c for c in _candidates()}
    v2 = {c.id: c for c in read_jsonl(V2_CANDIDATES, Candidate)}
    for cid, old in v1.items():
        new = v2[cid]
        assert (new.split, new.lang, new.corpus_lang) == (old.split, old.lang, old.corpus_lang)
        assert new.wiki_revision
    by_article: defaultdict[str, set[str]] = defaultdict(set)
    for c in v2.values():
        if c.slug:
            by_article[c.slug].add(c.split)
    assert all(len(splits) == 1 for splits in by_article.values())
