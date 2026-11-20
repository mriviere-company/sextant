import pytest

from sextant.eval.dataset import SectionRef
from sextant.eval.generation.models import Candidate
from sextant.eval.generation.pipeline import Wiki
from sextant.eval.review import (
    Review,
    ReviewError,
    build_items,
    dataset_stats,
    import_reviews,
    page_record,
    parse_section_key,
    section_key,
)
from sextant.models import LANGS, Article, Lang, Section


def _ref(slug: str, index: int) -> SectionRef:
    return SectionRef(slug=slug, section_index=index)


def _candidate(cid: str, order: int, **overrides: object) -> Candidate:
    base: dict[str, object] = {
        "id": cid,
        "review_order": order,
        "split": "dev",
        "lang": "en",
        "kind": "factual",
        "origin": "article",
        "slug": "fleet",
        "style": "natural",
        "question": "How many ships?",
        "reference_answer": "Three.",
        "question_fr": "Combien de vaisseaux ?",
        "reference_answer_fr": "Trois.",
        "relevant": (_ref("fleet", 0), _ref("fleet", 1)),
        "sources": (_ref("fleet", 0),),
        "judge_added": (_ref("fleet", 1),),
        "idea_id": f"fleet.{order}",
        "prompt_version": "test",
    }
    base.update(overrides)
    return Candidate.model_validate(base)


CANDIDATES = [
    _candidate("q001", 1),
    _candidate("q002", 2, split="test"),
    _candidate(
        "q003",
        3,
        kind="unanswerable",
        relevant=(),
        sources=(),
        judge_added=(),
        judge_found=(_ref("fleet", 1),),
        flags=("judge_found_answer",),
    ),
    _candidate("q004", 4, lang="fr", question="Combien ?", question_fr="Combien ?"),
]


def _review(cid: str, decision: str, **extra: object) -> Review:
    return Review.model_validate(
        {"id": cid, "decision": decision, "reviewed_at": "2026-11-20T10:00:00Z", **extra}
    )


def test_section_keys_round_trip() -> None:
    assert parse_section_key(section_key(_ref("fleet", 3))) == _ref("fleet", 3)
    with pytest.raises(ValueError, match="bad section key"):
        parse_section_key("fleet")


def test_kept_and_corrected_candidates_become_validated_items_in_their_frozen_split() -> None:
    reviews = [
        _review("q002", "edit", question="How many ships do I get?", relevant=["fleet#0"]),
        _review("q001", "keep"),
        _review("q003", "keep"),
        _review("q004", "reject", reject_reason="duplicate"),
    ]
    items = build_items(CANDIDATES, reviews)
    assert [i.id for i in items] == ["q001", "q002", "q003"]
    assert all(i.validated for i in items)
    assert items[0].relevant == (_ref("fleet", 0), _ref("fleet", 1))  # proposal kept as is
    assert items[1].question == "How many ships do I get?"
    assert items[1].relevant == (_ref("fleet", 0),)  # the reviewer unticked the judge's section
    assert items[1].split == "test"
    assert items[2].relevant == ()  # unanswerable stays without relevant sections


def test_a_gloss_only_correction_of_a_foreign_question_is_refused() -> None:
    reviews = [
        _review("q001", "edit", question="How many ships?", question_fr="Combien de navires ?")
    ]
    with pytest.raises(ReviewError, match="French gloss"):
        build_items(CANDIDATES, reviews)
    fixed = [
        _review("q001", "edit", question="How many vessels?", question_fr="Combien de navires ?")
    ]
    assert build_items(CANDIDATES, fixed)[0].question == "How many vessels?"


def test_an_answerable_question_cannot_be_kept_without_sections() -> None:
    with pytest.raises(ReviewError, match="without any relevant"):
        build_items(CANDIDATES, [_review("q001", "keep", relevant=[])])


def test_import_rejects_unknown_ids_and_duplicates() -> None:
    known = {c.id for c in CANDIDATES}
    record = {"id": "q001", "decision": "keep", "reviewed_at": "x", "extra_page_field": 1}
    assert import_reviews([record], known)[0].decision == "keep"
    with pytest.raises(ReviewError, match="unknown"):
        import_reviews([{**record, "id": "q999"}], known)
    with pytest.raises(ReviewError, match="same candidate"):
        import_reviews([record, record], known)


def test_stats_count_decisions_splits_and_reviewer_relevance_changes() -> None:
    reviews = [
        _review("q001", "keep"),
        _review("q002", "edit", relevant=["fleet#0"]),
        _review("q003", "keep"),
        _review("q004", "reject", reject_reason="duplicate"),
    ]
    items = build_items(CANDIDATES, reviews)
    stats = dataset_stats(CANDIDATES, reviews, items)
    assert stats["decisions"] == {"edit": 1, "keep": 2, "reject": 1}
    assert stats["reject_reasons"] == {"duplicate": 1}
    assert stats["relevance_changed_by_reviewer"] == 1
    assert stats["validated"]["questions"] == 3
    assert stats["dev"]["questions"] == 2
    assert stats["test"]["questions"] == 1
    assert stats["validated"]["unanswerable_share"] == pytest.approx(1 / 3, abs=1e-3)


def test_stats_publish_the_review_pace() -> None:
    reviews = [
        _review("q001", "keep", dwell_ms=12000),
        _review("q002", "keep", dwell_ms=3000),
        _review("q003", "keep"),
    ]
    pace = dataset_stats(CANDIDATES, reviews, build_items(CANDIDATES, reviews))["review_pace"]
    assert pace["decisions_with_dwell"] == 2
    assert pace["under_5_seconds"] == 1
    assert pace["median_seconds"] == 12.0


def _wiki() -> Wiki:
    def article(lang: Lang) -> Article:
        return Article(
            lang=lang,
            slug="fleet",
            title=f"Flotte ({lang})",
            category="fleet",
            category_label="Flotte",
            order=1,
            tags=(),
            summary="",
            related=(),
            sections=(
                Section(anchor="", title="", text="intro"),
                Section(anchor="envoyer", title="Envoyer", text="texte"),
            ),
        )

    return Wiki({lang: [article(lang)] for lang in LANGS})


def test_page_record_labels_where_each_section_comes_from() -> None:
    record = page_record(CANDIDATES[0], _wiki())
    assert [(s["key"], s["role"]) for s in record["sections"]] == [
        ("fleet#0", "source"),
        ("fleet#1", "judge"),
    ]
    assert record["sections"][1]["url"].endswith("/wiki/fleet#envoyer")
    assert record["sections"][0]["title"] == "Introduction"
    assert "split" not in record  # the reviewer does not see which split a question is in
    unanswerable = page_record(CANDIDATES[2], _wiki())
    assert [s["role"] for s in unanswerable["sections"]] == ["found"]


def test_on_a_migrated_set_only_decisions_on_the_same_wiki_count() -> None:
    carried = _candidate("q001", 1, wiki_revision="v2", status="carried")
    revalidate = _candidate("q002", 2, wiki_revision="v2", status="revalidate")
    rejected = _candidate("q003", 3, wiki_revision="v2", status="rejected")
    candidates = [carried, revalidate, rejected]
    old = [_review("q001", "keep"), _review("q002", "keep"), _review("q003", "reject")]
    # carried: validated by the folded v1 decision; revalidate: the v1 decision no longer counts
    assert [i.id for i in build_items(candidates, old)] == ["q001"]
    new = [*old[:1], _review("q002", "keep", wiki_revision="v2"), old[2]]
    assert [i.id for i in build_items(candidates, new)] == ["q001", "q002"]
    newer = [_review("q001", "reject", wiki_revision="v2"), *new[1:]]
    assert [i.id for i in build_items(candidates, newer)] == ["q002"]  # a v2 decision wins
