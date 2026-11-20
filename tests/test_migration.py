from sextant.eval.dataset import SectionRef
from sextant.eval.generation.models import Candidate
from sextant.eval.migration import (
    Reassessment,
    build_section_map,
    decide_status,
    migrate_candidate,
    parse_reassessment,
    remap,
)
from sextant.eval.review import Review
from sextant.models import Article, Section


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
