from sextant.eval.dataset import SectionRef
from sextant.eval.generation.models import Candidate
from sextant.eval.migration import (
    Reassessment,
    build_section_map,
    confirm_restored,
    decide_status,
    follow_update,
    migrate_candidate,
    parse_reassessment,
    remap,
    restore_candidate,
    second_opinion,
    touched,
    touched_sections,
)
from sextant.eval.review import Review
from sextant.models import Article, Chunk, Section


def _article(slug: str, anchors: list[str]) -> Article:
    return Article(
        lang="fr",
        slug=slug,
        title=slug,
        category="fleet",
        category_label="Flotte",
        order=1,
        tags=(),
        summary="",
        related=(),
        sections=tuple(Section(anchor=a, title=a or "intro", text="t") for a in anchors),
    )


OLD = [_article("fleet", ["", "envoyer", "discord", "rappel"])]
NEW = [_article("fleet", ["", "envoyer", "annuler", "rappel"])]  # one inserted, one removed
SMAP = build_section_map(OLD, NEW)


def _ref(index: int) -> SectionRef:
    return SectionRef(slug="fleet", section_index=index)


def test_section_map_follows_anchors_and_drops_removed_sections() -> None:
    assert SMAP == {"fleet#0": 0, "fleet#1": 1, "fleet#2": None, "fleet#3": 3}
    assert remap([_ref(3), _ref(2), _ref(1)], SMAP) == (_ref(3), _ref(1))
    shifted = build_section_map(
        OLD, [_article("fleet", ["", "nouveau", "envoyer", "discord", "rappel"])]
    )
    assert shifted["fleet#1"] == 2  # an insertion before it moves it down


def _candidate(kind: str = "factual", **extra: object) -> Candidate:
    base: dict[str, object] = {
        "id": "q001",
        "review_order": 1,
        "split": "dev",
        "lang": "fr",
        "kind": kind,
        "origin": "article",
        "slug": "fleet",
        "style": "natural",
        "question": "Combien de temps pour rappeler une flotte ?",
        "reference_answer": "Tant qu'elle n'est pas arrivée [1].",
        "question_fr": "Combien de temps pour rappeler une flotte ?",
        "reference_answer_fr": "Tant qu'elle n'est pas arrivée [1].",
        "relevant": (_ref(3),) if kind != "unanswerable" else (),
        "sources": (_ref(3),) if kind != "unanswerable" else (),
        "idea_id": "fleet.0",
        "prompt_version": "test",
    }
    base.update(extra)
    return Candidate.model_validate(base)


def _verdict(**extra: object) -> Reassessment:
    base: dict[str, object] = {
        "id": "q001",
        "pooled": (_ref(3),),
        "relevant": (_ref(3),),
        "answerable": True,
        "question_valid": True,
        "old_answer": "consistent",
        "new_answer": "Pendant les 2 premières minutes de vol.",
        "new_answer_fr": "Pendant les 2 premières minutes de vol.",
        "kind": "factual",
    }
    base.update(extra)
    return Reassessment.model_validate(base)


def _review(decision: str = "keep", **extra: object) -> Review:
    return Review.model_validate({"id": "q001", "decision": decision, "reviewed_at": "t", **extra})


def test_a_reviewed_answer_carries_over_only_when_nothing_changed() -> None:
    assert decide_status(_candidate(), _review(), _verdict(), False) == ("carried", ())
    status, reasons = decide_status(
        _candidate(), _review(), _verdict(old_answer="contradicted"), False
    )
    assert (status, reasons) == ("revalidate", ("answer_contradicted",))
    _, reasons = decide_status(
        _candidate(), _review(), _verdict(renamed_terms=("Bunker -> Fort",)), True
    )
    assert reasons == ("renamed_terms", "source_removed")
    _, reasons = decide_status(_candidate(), _review(), _verdict(answerable=False), False)
    assert reasons == ("now_unanswerable",)


def test_unanswerable_rejected_and_unreviewed_candidates() -> None:
    unanswerable = _candidate("unanswerable")
    status, reasons = decide_status(
        unanswerable, _review(), _verdict(old_answer="not_applicable"), False
    )
    assert (status, reasons) == ("revalidate", ("now_answerable",))
    assert decide_status(_candidate(), None, _verdict(), False) == ("to_review", ())
    wrong = _review("reject", reject_reason="wrong_answer")
    assert decide_status(_candidate(), wrong, _verdict(), False) == (
        "revalidate",
        ("rejected_wrong_answer",),
    )
    duplicate = _review("reject", reject_reason="duplicate")
    assert decide_status(_candidate(), duplicate, _verdict(), False) == ("rejected", ())


def test_migrated_candidate_keeps_the_reviewed_answer_or_proposes_the_new_one() -> None:
    carried = migrate_candidate(_candidate(), _review(), _verdict(), SMAP, "b2cdaa9")
    assert carried.status == "carried"
    assert carried.reference_answer == "Tant qu'elle n'est pas arrivée [1]."
    assert carried.wiki_revision == "b2cdaa9"
    changed = migrate_candidate(
        _candidate(), _review(), _verdict(old_answer="contradicted"), SMAP, "b2cdaa9"
    )
    assert changed.status == "revalidate"
    assert changed.reference_answer == "Pendant les 2 premières minutes de vol."
    assert changed.previous_answer == "Tant qu'elle n'est pas arrivée [1]."
    now_answered = migrate_candidate(
        _candidate("unanswerable"),
        _review(),
        _verdict(kind="procedural", old_answer="not_applicable"),
        SMAP,
        "x",
    )
    assert (now_answered.kind, now_answered.previous_kind) == ("procedural", "unanswerable")
    assert now_answered.relevant == (_ref(3),)
    edited = migrate_candidate(
        _candidate(), _review("edit", question="Rappel d'une flotte ?"), _verdict(), SMAP, "x"
    )
    assert edited.question == "Rappel d'une flotte ?"


def test_parse_reassessment_is_strict_on_unexpected_values() -> None:
    labels = {"S1": _ref(1), "S2": _ref(3)}
    verdict = parse_reassessment(
        "q001",
        {"relevant": ["S2", "S9"], "answerable": True, "old_answer": "maybe", "kind": "weird"},
        labels,
    )
    assert verdict.relevant == (_ref(3),)
    assert verdict.old_answer == "contradicted"  # unknown verdicts force a human review
    assert verdict.kind == "factual"
    assert verdict.question_valid


def test_an_unverified_answer_is_not_carried() -> None:
    status, reasons = decide_status(
        _candidate(), _review(), _verdict(), False, strictly_verified=False
    )
    assert (status, reasons) == ("revalidate", ("answer_not_verified",))


def test_the_second_opinion_only_sends_carried_answers_back_to_review() -> None:
    carried = migrate_candidate(_candidate(), _review(), _verdict(), SMAP, "b2cdaa9")
    unreviewed = migrate_candidate(_candidate(), None, _verdict(), SMAP, "b2cdaa9")
    unreviewed = unreviewed.model_copy(update={"id": "q002"})
    context = ({"q001": _candidate()}, {"q001": _review()}, {"q001": _verdict()}, SMAP)
    kept = second_opinion([carried, unreviewed], *context, flash_ok={"q001": True})
    assert kept == [carried, unreviewed]
    back = second_opinion([carried, unreviewed], *context, flash_ok={})
    assert (back[0].status, back[0].reasons) == ("revalidate", ("answer_not_verified",))
    assert back[0].wiki_revision == "b2cdaa9"
    assert back[1] == unreviewed


def _chunk(cid: str, index: int, text: str) -> Chunk:
    return Chunk.model_validate(
        {
            "id": cid,
            "lang": "fr",
            "slug": "fleet",
            "article_title": "t",
            "category": "fleet",
            "section_index": index,
            "section_anchor": "",
            "section_title": "t",
            "part": 0,
            "text": text,
            "embed_text": text,
            "url": "/wiki/fleet",
            "n_words": 1,
        }
    )


def test_touched_sections_are_the_changed_ones() -> None:
    old = [_chunk("a", 1, "x"), _chunk("b", 2, "y")]
    new = [_chunk("a", 1, "x"), _chunk("b", 2, "z"), _chunk("c", 3, "w")]
    assert touched_sections(old, new) == {("fleet", 2), ("fleet", 3)}
    others = _candidate(relevant=(_ref(1),), sources=(_ref(1),)).model_copy(update={"id": "q2"})
    picked = touched([_candidate(), others], {("fleet", 3)}, also={"q2"})
    assert [c.id for c in picked] == ["q001", "q2"]


def test_an_answer_the_newer_wiki_still_backs_is_left_alone() -> None:
    carried = migrate_candidate(_candidate(), _review(), _verdict(), SMAP, "b2cdaa9")
    assert follow_update(carried, _verdict(), "4da9931") is carried
    unverified = follow_update(carried, _verdict(), "4da9931", strictly_verified=False)
    assert (unverified.status, unverified.reasons) == ("revalidate", ("wiki_updated",))


def test_a_contradicted_answer_is_regenerated_with_the_new_revision() -> None:
    carried = migrate_candidate(_candidate(), _review(), _verdict(), SMAP, "b2cdaa9")
    updated = follow_update(carried, _verdict(old_answer="contradicted"), "4da9931")
    assert updated.status == "revalidate"
    assert updated.wiki_revision == "4da9931"  # voids a decision taken on b2cdaa9
    assert updated.reference_answer == "Pendant les 2 premières minutes de vol."
    assert updated.previous_answer == carried.reference_answer
    unreviewed = migrate_candidate(_candidate(), None, _verdict(), SMAP, "b2cdaa9")
    again = follow_update(unreviewed, _verdict(old_answer="incomplete"), "4da9931")
    assert (again.status, again.reasons) == ("to_review", ("wiki_updated",))


def test_a_confirmed_v1_answer_is_restored_and_carried_only_if_reviewed() -> None:
    original = _candidate()
    current = migrate_candidate(
        original, _review(), _verdict(old_answer="contradicted"), SMAP, "b2cdaa9"
    )
    restored = restore_candidate(current, original, _review())
    assert restored.reference_answer == original.reference_answer
    carried = confirm_restored(restored, _verdict(), "df6465b", reviewed=True)
    assert (carried.status, carried.reasons, carried.wiki_revision) == ("carried", (), "df6465b")
    unreviewed = confirm_restored(restored, _verdict(), "df6465b", reviewed=False)
    assert unreviewed.status == "to_review"
    edited = restore_candidate(current, original, _review("edit", reference_answer="Corrigée."))
    assert edited.reference_answer == "Corrigée."
