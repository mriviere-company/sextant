r"""Carry the evaluation set to a new wiki snapshot: `python -m sextant.eval.migration <stage>`.

The method is written down in `eval/dataset/MIGRATION_V2.md`; this module applies it.

    map        old and new French snapshots → work/v2/section_map.json (deterministic)
    reassess   every v1 candidate against the v2 wiki, by LLM → work/v2/reassessments.jsonl
    assemble   statuses decided by code → eval/dataset/candidates.jsonl (v2)

Old section positions are mapped to new ones through French anchors, which the rewrite kept
for every existing section; the re-assessment re-pools sections over the v2 index and asks
one model whether the old reference answer still holds; `decide_status` then decides, by
rules fixed before the run, which review decisions carry over and what goes back to review.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast, get_args

from pydantic import BaseModel, ConfigDict

from sextant.eval.dataset import Kind, SectionRef
from sextant.eval.generation.models import Candidate, read_jsonl, write_jsonl
from sextant.eval.generation.pipeline import Wiki, _parallel, pool_sections
from sextant.eval.review import Review
from sextant.ingest.wiki import load_corpus
from sextant.llm import (
    FAST_MODEL,
    DeepSeekJsonLlm,
    DiskCache,
    JsonLlm,
    LlmError,
    Request,
    model_for,
)
from sextant.models import Article, Chunk

ROOT = Path(__file__).resolve().parents[3]
DATASET = ROOT / "eval" / "dataset"
V1 = DATASET / "v1"
WORK = DATASET / "work" / "v2"
CACHE = ROOT / "eval" / ".llm-cache"

Verdict = Literal["consistent", "contradicted", "incomplete", "not_applicable"]
VERDICTS: tuple[Verdict, ...] = get_args(Verdict)
KINDS: tuple[Kind, ...] = get_args(Kind)

REASSESS_SYSTEM = """The Area Universe game wiki was rewritten. You check one question of a \
retrieval evaluation set, and its OLD reference answer, against the CURRENT wiki sections \
below, labelled S1, S2… (possibly in another language than the question). Judge only from \
these sections.

Return one JSON object:
{"relevant": ["S2", …],
 "answerable": true|false,
 "question_valid": true|false,
 "old_answer": "consistent"|"contradicted"|"incomplete"|"not_applicable",
 "renamed_terms": ["old name -> new name", …],
 "new_answer": "…",
 "new_answer_fr": "…",
 "kind": "factual"|"procedural"|"comparative"|"multi_section"|"unanswerable",
 "note": "…"}

- relevant: sections that state the answer, or a needed part of it. A section that only \
mentions the topic is not relevant.
- answerable: the sections together fully answer the question.
- question_valid: false only if the question now relies on something the sections say does \
not exist or was removed, or makes no sense in the current game.
- old_answer: compare EVERY fact of the old answer with the sections. "contradicted" if any \
number, time, name, condition or outcome differs; "incomplete" if it is right but misses \
something the question asks; "consistent" only if every fact is supported; \
"not_applicable" if the old answer says the wiki has no answer.
- renamed_terms: game terms used by the question or the old answer that the sections now \
name differently.
- new_answer: the reference answer, written in the question's language, 1 to 3 sentences, \
only from the relevant sections; empty if not answerable. new_answer_fr: its French \
translation (identical if the question is in French).
- kind: the best kind for this question now ("unanswerable" if not answerable).
- note: one short sentence in French for the human reviewer about what changed, or empty."""


STRICT_SYSTEM = """You verify, strictly, that an answer about the game Area Universe is still \
correct according to the CURRENT wiki sections below (S1, S2…), which are the only truth.

Split the answer into its factual claims: every figure, game name (mission, building, ship, \
regime, menu), cause, condition and outcome. For each claim, quote the sentence of the \
sections that states it. A claim is:
- "supported" only if a quoted sentence states it, with the same figures and the same names;
- "outdated_name" if the sections now call the thing differently;
- "contradicted" if the sections state something different (another figure, cause, rule…);
- "unsupported" if no sentence states it.

Return one JSON object: {"claims": [{"claim": "…", "status": "supported"|"outdated_name"|\
"contradicted"|"unsupported", "quote": "…"}], "verdict": "consistent"|"not_consistent"}
"consistent" only if every claim is "supported"."""


class StrictCheck(BaseModel):
    """The claim-by-claim check of a reviewed answer before it is carried over."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    consistent: bool
    claims: tuple[dict[str, str], ...] = ()


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Reassessment(_Frozen):
    """What the v2 wiki says about one candidate."""

    id: str
    pooled: tuple[SectionRef, ...]
    relevant: tuple[SectionRef, ...]
    answerable: bool
    question_valid: bool
    old_answer: Verdict
    renamed_terms: tuple[str, ...] = ()
    new_answer: str = ""
    new_answer_fr: str = ""
    kind: Kind
    note: str = ""


# --- 1. section map ------------------------------------------------------------------------


def section_key(slug: str, index: int) -> str:
    """`slug#index`."""
    return f"{slug}#{index}"


def build_section_map(old: Sequence[Article], new: Sequence[Article]) -> dict[str, int | None]:
    """Old French section position → new position, through the French anchor (None: removed)."""
    new_anchors = {a.slug: [s.anchor for s in a.sections] for a in new}
    mapping: dict[str, int | None] = {}
    for article in old:
        anchors = new_anchors.get(article.slug, [])
        for index, section in enumerate(article.sections):
            key = section_key(article.slug, index)
            mapping[key] = anchors.index(section.anchor) if section.anchor in anchors else None
    return mapping


def remap(refs: Sequence[SectionRef], smap: Mapping[str, int | None]) -> tuple[SectionRef, ...]:
    """Refs at their new positions; refs to removed sections are dropped."""
    out: list[SectionRef] = []
    for ref in refs:
        new_index = smap[section_key(ref.slug, ref.section_index)]
        if new_index is not None:
            out.append(SectionRef(slug=ref.slug, section_index=new_index))
    return tuple(out)


# --- 2. re-assessment ----------------------------------------------------------------------


def parse_reassessment(
    cid: str, payload: Mapping[str, Any], labels: Mapping[str, SectionRef]
) -> Reassessment:
    """Validate the model's answer; unknown labels and values fall back to strict defaults."""

    def text(key: str) -> str:
        value = payload.get(key)
        return " ".join(value.split()) if isinstance(value, str) else ""

    raw = payload.get("relevant")
    relevant = tuple(
        dict.fromkeys(labels[k] for k in (raw if isinstance(raw, list) else []) if k in labels)
    )
    verdict = payload.get("old_answer")
    kind = payload.get("kind")
    renamed = payload.get("renamed_terms")
    return Reassessment(
        id=cid,
        pooled=tuple(labels.values()),
        relevant=relevant,
        answerable=payload.get("answerable") is True,
        question_valid=payload.get("question_valid") is not False,
        # anything unexpected counts as a contradiction, which forces a human review
        old_answer=cast(Verdict, verdict) if verdict in VERDICTS else "contradicted",
        renamed_terms=tuple(t for t in (renamed if isinstance(renamed, list) else []) if t),
        new_answer=text("new_answer"),
        new_answer_fr=text("new_answer_fr"),
        kind=cast(Kind, kind) if kind in KINDS else "factual",
        note=text("note"),
    )


def reassess(
    llm: JsonLlm,
    wiki: Wiki,
    entries: Sequence[tuple[Candidate, Sequence[SectionRef]]],
    workers: int = 8,
) -> list[Reassessment]:
    """One model call per candidate: pooled v2 sections, old answer, question."""

    def one(entry: tuple[Candidate, Sequence[SectionRef]]) -> Reassessment | None:
        cand, pool = entry
        shown = sorted(set(pool), key=lambda r: (wiki.order.index(r.slug), r.section_index))
        labels = {f"S{n}": ref for n, ref in enumerate(shown, start=1)}
        lang = cand.corpus_lang or cand.lang
        sections = "\n\n".join(wiki.render_section(lang, r, k) for k, r in labels.items())
        user = (
            f"Question ({cand.lang}): {cand.question}\n"
            f"Old kind: {cand.kind}\nOld reference answer: {cand.reference_answer}\n\n"
            f"Current wiki sections ({lang}):\n\n{sections}"
        )
        request = Request(
            model=model_for("reassessment"),
            system=REASSESS_SYSTEM,
            user=user,
            max_tokens=1500,
            temperature=0.0,
        )
        try:
            payload = llm.complete_json(request)
        except LlmError:
            return None
        return parse_reassessment(cand.id, payload, labels)

    return _parallel(one, entries, workers)


def strict_check(
    llm: JsonLlm,
    wiki: Wiki,
    entries: Sequence[tuple[Candidate, str, Sequence[SectionRef]]],
    workers: int = 8,
    model: str | None = None,
) -> list[StrictCheck]:
    """Check reviewed answers (candidate, answer, sections) claim by claim against the wiki.

    `model` overrides the strict-check role, for the second opinion of amendment 2.
    """

    def one(entry: tuple[Candidate, str, Sequence[SectionRef]]) -> StrictCheck | None:
        cand, answer, refs = entry
        shown = sorted(set(refs), key=lambda r: (wiki.order.index(r.slug), r.section_index))
        lang = cand.corpus_lang or cand.lang
        sections = "\n\n".join(
            wiki.render_section(lang, r, f"S{n}") for n, r in enumerate(shown, 1)
        )
        user = f"Question: {cand.question}\nAnswer to verify: {answer}\n\nSections:\n\n{sections}"
        request = Request(
            model=model or model_for("strict_check"),
            system=STRICT_SYSTEM,
            user=user,
            max_tokens=2500,
            temperature=0.0,
        )
        try:
            payload = llm.complete_json(request)
        except LlmError:
            return StrictCheck(id=cand.id, consistent=False)
        return parse_strict(cand.id, payload)

    return _parallel(one, entries, workers)


def parse_strict(cid: str, payload: Mapping[str, Any]) -> StrictCheck:
    """Consistent only if the verdict says so and every listed claim is supported."""
    raw = payload.get("claims")
    claims = tuple(
        {k: str(c.get(k, "")) for k in ("claim", "status", "quote")}
        for c in (raw if isinstance(raw, list) else [])
        if isinstance(c, dict)
    )
    ok = payload.get("verdict") == "consistent" and all(c["status"] == "supported" for c in claims)
    return StrictCheck(id=cid, consistent=ok and bool(claims), claims=claims)


def second_opinion(  # noqa: PLR0913 — the migration's full context
    current: Sequence[Candidate],
    originals: Mapping[str, Candidate],
    reviews: Mapping[str, Review],
    verdicts: Mapping[str, Reassessment],
    smap: Mapping[str, int | None],
    *,
    flash_ok: Mapping[str, bool],
) -> list[Candidate]:
    """Amendment 2: a carried answer that the second judge does not verify goes back to review.

    Only `carried` candidates can change, and only towards review; the revision they were
    assessed on is kept. Everything else is returned untouched.
    """
    out = []
    for cand in current:
        if cand.status == "carried" and not flash_ok.get(cand.id, False):
            cand = migrate_candidate(  # noqa: PLW2901 — replaced on purpose
                originals[cand.id],
                reviews.get(cand.id),
                verdicts[cand.id],
                smap,
                cand.wiki_revision,
                strictly_verified=False,
            )
        out.append(cand)
    return out


# --- 3. status -----------------------------------------------------------------------------

Status = Literal["to_review", "carried", "revalidate", "rejected"]


def decide_status(
    candidate: Candidate,
    review: Review | None,
    verdict: Reassessment,
    source_removed: bool,
    strictly_verified: bool = True,
) -> tuple[Status, tuple[str, ...]]:
    """Apply the table of MIGRATION_V2.md, step 3: carry only what the reviewer saw unchanged."""
    if review is None:
        return "to_review", ()
    if review.decision == "reject":
        if review.reject_reason == "wrong_answer":
            return "revalidate", ("rejected_wrong_answer",)
        return "rejected", ()
    was_answerable = candidate.kind != "unanswerable"
    reasons: list[str] = []
    if not verdict.question_valid:
        reasons.append("question_invalid")
    if was_answerable and not verdict.answerable:
        reasons.append("now_unanswerable")
    if not was_answerable and verdict.answerable:
        reasons.append("now_answerable")
    if was_answerable and verdict.old_answer == "contradicted":
        reasons.append("answer_contradicted")
    if was_answerable and verdict.old_answer == "incomplete":
        reasons.append("answer_incomplete")
    if verdict.renamed_terms:
        reasons.append("renamed_terms")
    if source_removed:
        reasons.append("source_removed")
    if not reasons and not strictly_verified:
        reasons.append("answer_not_verified")
    return ("revalidate", tuple(reasons)) if reasons else ("carried", ())


def migrate_candidate(  # noqa: PLR0913 — one candidate's full context
    candidate: Candidate,
    review: Review | None,
    verdict: Reassessment,
    smap: Mapping[str, int | None],
    revision: str,
    *,
    strictly_verified: bool = True,
) -> Candidate:
    """Build the v2 version of a candidate: remapped refs, status, answer and relevance."""
    sources = remap(candidate.sources, smap)
    source_removed = len(sources) < len(candidate.sources)
    status, reasons = decide_status(candidate, review, verdict, source_removed, strictly_verified)
    question, answer = candidate.question, candidate.reference_answer
    question_fr, answer_fr = candidate.question_fr, candidate.reference_answer_fr
    if review is not None and review.decision == "edit":
        question = review.question or question
        answer = review.reference_answer or answer
        question_fr = review.question_fr or question_fr
        answer_fr = review.reference_answer_fr or answer_fr
    was_answerable = candidate.kind != "unanswerable"
    if verdict.answerable:
        kind: Kind = candidate.kind if was_answerable else _answerable_kind(verdict.kind)
        relevant = verdict.relevant or sources
    else:
        kind, relevant = "unanswerable", ()
    if status != "carried" and verdict.answerable and verdict.new_answer:
        answer, answer_fr = verdict.new_answer, verdict.new_answer_fr or verdict.new_answer
    if candidate.lang == "fr":
        answer_fr = answer
    return candidate.model_copy(
        update={
            "question": question,
            "question_fr": question_fr,
            "kind": kind,
            "reference_answer": answer,
            "reference_answer_fr": answer_fr,
            "relevant": relevant,
            "sources": sources,
            "judge_added": tuple(r for r in relevant if r not in sources),
            "judge_found": (),
            "flags": tuple(
                dict.fromkeys(
                    [f for f in candidate.flags if f != "judge_found_answer"]
                    + [f"renamed:{t}" for t in verdict.renamed_terms]
                )
            ),
            "judge_note": verdict.note,
            "wiki_revision": revision,
            "status": status,
            "reasons": reasons,
            "previous_answer": candidate.reference_answer
            if review is None or review.decision != "edit"
            else (review.reference_answer or candidate.reference_answer),
            "previous_answer_fr": candidate.reference_answer_fr,
            "previous_kind": candidate.kind,
        }
    )


def _answerable_kind(kind: Kind) -> Kind:
    return "factual" if kind == "unanswerable" else kind


# --- later wiki updates ------------------------------------------------------------------


def touched_sections(old: Sequence[Chunk], new: Sequence[Chunk]) -> set[tuple[str, int]]:
    """Return the sections whose chunks were added, removed or changed between two snapshots."""
    before, after = {c.id: c for c in old}, {c.id: c for c in new}
    ids = {i for i in before.keys() | after.keys() if before.get(i) != after.get(i)}
    found = (before.get(i) for i in ids), (after.get(i) for i in ids)
    return {(c.slug, c.section_index) for group in found for c in group if c is not None}


def touched(
    candidates: Sequence[Candidate], sections: set[tuple[str, int]], also: set[str]
) -> list[Candidate]:
    """Live candidates whose answering sections changed, plus those named in `also`."""
    return [
        c
        for c in candidates
        if c.status != "rejected"
        and (
            c.id in also
            or {(r.slug, r.section_index) for r in (*c.relevant, *c.sources)} & sections
        )
    ]


def still_valid(candidate: Candidate, verdict: Reassessment) -> bool:
    """Whether a candidate's current answer survives a newer wiki unchanged."""
    was_answerable = candidate.kind != "unanswerable"
    return (
        verdict.question_valid
        and verdict.answerable == was_answerable
        and not verdict.renamed_terms
        and (verdict.old_answer == "consistent" or not was_answerable)
    )


def follow_update(
    candidate: Candidate,
    verdict: Reassessment,
    revision: str,
    *,
    strictly_verified: bool = True,
) -> Candidate:
    """Apply a re-assessment on a newer wiki to a v2 candidate.

    A candidate whose answer still holds is returned untouched, with its revision, so a
    decision taken on it stays valid; it must also pass both strict checks. Any
    other gets the regenerated answer, the reason `wiki_updated` and the new revision, which
    voids a decision taken before: carried and revalidated candidates go to revalidation,
    unreviewed ones stay to review.
    """
    if still_valid(candidate, verdict) and strictly_verified:
        return candidate
    was_answerable = candidate.kind != "unanswerable"
    answer, answer_fr = candidate.reference_answer, candidate.reference_answer_fr
    if verdict.answerable:
        kind: Kind = candidate.kind if was_answerable else _answerable_kind(verdict.kind)
        relevant = verdict.relevant or candidate.relevant
        if verdict.new_answer:
            answer, answer_fr = verdict.new_answer, verdict.new_answer_fr or verdict.new_answer
    else:
        kind, relevant = "unanswerable", ()
    if candidate.lang == "fr":
        answer_fr = answer
    carried = candidate.status == "carried"
    return candidate.model_copy(
        update={
            "kind": kind,
            "reference_answer": answer,
            "reference_answer_fr": answer_fr,
            "relevant": relevant,
            "judge_added": tuple(r for r in relevant if r not in candidate.sources),
            "flags": tuple(
                dict.fromkeys([*candidate.flags, *(f"renamed:{t}" for t in verdict.renamed_terms)])
            ),
            "judge_note": verdict.note,
            "wiki_revision": revision,
            "status": "to_review" if candidate.status == "to_review" else "revalidate",
            "reasons": tuple(dict.fromkeys([*candidate.reasons, "wiki_updated"])),
            "previous_answer": candidate.reference_answer if carried else candidate.previous_answer,
            "previous_answer_fr": candidate.reference_answer_fr
            if carried
            else candidate.previous_answer_fr,
            "previous_kind": candidate.kind if carried else candidate.previous_kind,
        }
    )


def section_by_anchor(wiki: Wiki, key: str) -> SectionRef:
    """Return the section `slug#anchor`, by its French anchor ("" is the introduction)."""
    slug, _, anchor = key.partition("#")
    sections = wiki.article("fr", slug).sections
    for index, section in enumerate(sections):
        if section.anchor == anchor:
            return SectionRef(slug=slug, section_index=index)
    raise SystemExit(f"no section {key}")


def restore_candidate(current: Candidate, original: Candidate, review: Review | None) -> Candidate:
    """Put back the v1 answer and kind of a candidate whose answer the author confirms.

    The reviewed answer when the reviewer corrected it, else the v1 reference answer. Status,
    revision and relevance are left to `confirm_restored` or `follow_update`.
    """
    answer, answer_fr = original.reference_answer, original.reference_answer_fr
    if review is not None and review.decision == "edit" and review.reference_answer:
        answer = review.reference_answer
        answer_fr = review.reference_answer_fr or answer_fr
    return current.model_copy(
        update={"reference_answer": answer, "reference_answer_fr": answer_fr, "kind": original.kind}
    )


def confirm_restored(
    restored: Candidate, verdict: Reassessment, revision: str, *, reviewed: bool
) -> Candidate:
    """Accept a restored answer the judges verify: carried if reviewed in v1, else to review."""
    relevant = verdict.relevant or restored.relevant
    return restored.model_copy(
        update={
            "relevant": relevant,
            "judge_added": tuple(r for r in relevant if r not in restored.sources),
            "status": "carried" if reviewed else "to_review",
            "reasons": (),
            "judge_note": "Réponse d'origine confirmée par l'auteur et par les deux vérifications "
            "strictes (pro et flash).",
            "wiki_revision": revision,
        }
    )


# --- CLI -----------------------------------------------------------------------------------


def _revision() -> str:
    return (ROOT / "corpus" / "wiki" / "SOURCE_REVISION").read_text(encoding="utf-8").split()[0]


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0912, PLR0915 — one branch per stage
    """Entry point."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "stage", choices=("map", "reassess", "verify", "assemble", "second-check", "update")
    )
    parser.add_argument("--old-wiki", type=Path, help="v1 YAML snapshot directory (map stage)")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--old-chunks", type=Path, help="chunks.jsonl of the previous snapshot (update stage)"
    )
    parser.add_argument("--also", default="", help="extra candidate ids, comma-separated (update)")
    parser.add_argument(
        "--hint",
        default="",
        help="sections the judge must see, as q041=defense#temps;q050=x#y (update, FR anchors)",
    )
    parser.add_argument(
        "--restore",
        default="",
        help="candidates whose v1 answer the author confirms, comma-separated (update)",
    )
    args = parser.parse_args(argv)
    smap_path = WORK / "section_map.json"

    if args.stage == "update":
        if args.old_chunks is None:
            parser.error("--old-chunks is required for the update stage")
        hints: dict[str, list[str]] = {}
        for pair in filter(None, args.hint.split(";")):
            cid, key = pair.split("=", 1)
            hints.setdefault(cid, []).append(key)
        restore = {i for i in args.restore.split(",") if i}
        also = {i for i in args.also.split(",") if i} | set(hints) | restore
        return _update(args.old_chunks, also, args.workers, hints=hints, restore=restore)

    if args.stage == "map":
        if args.old_wiki is None:
            parser.error("--old-wiki is required for the map stage")
        old = load_corpus(args.old_wiki)["fr"]
        new = load_corpus(ROOT / "corpus" / "wiki")["fr"]
        smap = build_section_map(old, new)
        WORK.mkdir(parents=True, exist_ok=True)
        smap_path.write_text(json.dumps(smap, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        moved = sum(1 for k, v in smap.items() if v is not None and int(k.split("#")[1]) != v)
        removed = sorted(k for k, v in smap.items() if v is None)
        print(f"{len(smap)} old sections: {moved} moved, removed: {removed}")
        return 0

    smap = json.loads(smap_path.read_text(encoding="utf-8"))
    candidates = read_jsonl(V1 / "candidates.jsonl", Candidate)

    if args.stage == "reassess":
        from sextant.eval.generation.pipeline import POOL_STRATEGIES  # noqa: PLC0415
        from sextant.eval.retrieval_bench import section_map as chunk_sections  # noqa: PLC0415
        from sextant.retrieval.base import load_chunks  # noqa: PLC0415
        from sextant.retrieval.factory import RetrievalContext  # noqa: PLC0415

        wiki = Wiki.load(ROOT / "corpus" / "wiki")
        chunks = load_chunks()
        context = RetrievalContext(chunks)
        retrievers = [context.build(spec) for spec in POOL_STRATEGIES]
        sections = chunk_sections(chunks)
        entries = []
        for cand in candidates:
            pool = pool_sections(cand.question, cand.corpus_lang or cand.lang, retrievers, sections)
            entries.append((cand, [*pool, *remap(cand.sources, smap)]))
        llm = DeepSeekJsonLlm(DiskCache(CACHE))
        verdicts = reassess(llm, wiki, entries, args.workers)
        write_jsonl(WORK / "reassessments.jsonl", verdicts)
        print(f"reassessed {len(verdicts)} / {len(candidates)}; usage {llm.usage.model_dump()}")
        return 0

    reviews = {r.id: r for r in read_jsonl(V1 / "reviews.jsonl", Review)}
    by_id = {v.id: v for v in read_jsonl(WORK / "reassessments.jsonl", Reassessment)}
    missing = [c.id for c in candidates if c.id not in by_id]
    if missing:
        raise SystemExit(f"no re-assessment for {missing[:5]}… — rerun the reassess stage")
    strict_path = WORK / "strict_checks.jsonl"

    if args.stage == "verify":
        # first pass without the strict check: which candidates would be carried?
        to_check = []
        for cand in candidates:
            review, verdict = reviews.get(cand.id), by_id[cand.id]
            lost = len(remap(cand.sources, smap)) < len(cand.sources)
            if decide_status(cand, review, verdict, lost)[0] == "carried":
                assert review is not None
                answer = (review.reference_answer or cand.reference_answer).strip()
                to_check.append((cand, answer, verdict.pooled))
        llm = DeepSeekJsonLlm(DiskCache(CACHE))
        checks = strict_check(llm, Wiki.load(ROOT / "corpus" / "wiki"), to_check, args.workers)
        write_jsonl(strict_path, checks)
        passed = sum(c.consistent for c in checks)
        print(
            f"strict check: {passed} / {len(checks)} still verified; usage {llm.usage.model_dump()}"
        )
        return 0

    if args.stage == "second-check":
        current = read_jsonl(DATASET / "candidates.jsonl", Candidate)
        carried = [
            (c, c.reference_answer.strip(), by_id[c.id].pooled)
            for c in current
            if c.status == "carried"
        ]
        llm = DeepSeekJsonLlm(DiskCache(CACHE))
        wiki = Wiki.load(ROOT / "corpus" / "wiki")
        checks = strict_check(llm, wiki, carried, args.workers, model=FAST_MODEL)
        write_jsonl(WORK / "strict_checks_flash.jsonl", checks)
        updated = second_opinion(
            current,
            {c.id: c for c in candidates},
            reviews,
            by_id,
            smap,
            flash_ok={c.id: c.consistent for c in checks},
        )
        write_jsonl(DATASET / "candidates.jsonl", updated)
        back = sorted(c.id for c, u in zip(current, updated, strict=True) if c.status != u.status)
        print(f"second check: {len(back)} of {len(carried)} carried sent back: {back}")
        print(json.dumps(summary(updated), indent=1, ensure_ascii=False))
        return 0

    if not strict_path.exists():
        raise SystemExit("run the verify stage first: nothing is carried unverified")
    strict = {c.id: c.consistent for c in read_jsonl(strict_path, StrictCheck)}
    revision = _revision()
    migrated = [
        migrate_candidate(
            c,
            reviews.get(c.id),
            by_id[c.id],
            smap,
            revision,
            strictly_verified=strict.get(c.id, False),
        )
        for c in candidates
    ]
    write_jsonl(DATASET / "candidates.jsonl", migrated)
    print(json.dumps(summary(migrated), indent=1, ensure_ascii=False))
    return 0


def _update(
    old_chunks: Path,
    also: set[str],
    workers: int,
    *,
    hints: Mapping[str, Sequence[str]],
    restore: set[str],
) -> int:
    """Re-assess the candidates a later wiki commit touches (MIGRATION_V2.md, later updates)."""
    from sextant.eval.generation.pipeline import POOL_STRATEGIES  # noqa: PLC0415
    from sextant.eval.retrieval_bench import section_map as chunk_sections  # noqa: PLC0415
    from sextant.retrieval.base import load_chunks  # noqa: PLC0415
    from sextant.retrieval.factory import RetrievalContext  # noqa: PLC0415

    revision = _revision()
    chunks = load_chunks()
    sections = touched_sections(load_chunks(old_chunks), chunks)
    current = read_jsonl(DATASET / "candidates.jsonl", Candidate)
    originals = {c.id: c for c in read_jsonl(V1 / "candidates.jsonl", Candidate)}
    reviews = {r.id: r for r in read_jsonl(V1 / "reviews.jsonl", Review)}
    base = {
        c.id: restore_candidate(c, originals[c.id], reviews.get(c.id)) if c.id in restore else c
        for c in current
    }
    chosen = [base[c.id] for c in touched(current, sections, also)]
    print(f"changed sections: {sorted(sections)}; candidates: {[c.id for c in chosen]}")
    wiki = Wiki.load(ROOT / "corpus" / "wiki")
    hinted = {cid: [section_by_anchor(wiki, key) for key in keys] for cid, keys in hints.items()}
    context = RetrievalContext(chunks)
    retrievers = [context.build(spec) for spec in POOL_STRATEGIES]
    by_section = chunk_sections(chunks)
    entries = [
        (
            c,
            [
                *pool_sections(c.question, c.corpus_lang or c.lang, retrievers, by_section),
                *c.relevant,
                *c.sources,
                *hinted.get(c.id, ()),
            ],
        )
        for c in chosen
    ]
    llm = DeepSeekJsonLlm(DiskCache(CACHE))
    verdicts = {v.id: v for v in reassess(llm, wiki, entries, workers)}
    missing = [c.id for c in chosen if c.id not in verdicts]
    if missing:
        raise SystemExit(f"no re-assessment for {missing}: rerun")
    write_jsonl(WORK / f"reassessments_{revision[:7]}.jsonl", list(verdicts.values()))
    # every answer the re-assessment would leave alone must also pass both strict checks:
    # at 4da9931 the re-assessment kept an answer quoting the removed +250 PDG bonus
    keep = [
        (c, c.reference_answer.strip(), verdicts[c.id].pooled)
        for c in chosen
        if c.kind != "unanswerable" and still_valid(c, verdicts[c.id])
    ]
    pro = {s.id: s.consistent for s in strict_check(llm, wiki, keep, workers)}
    flash = {s.id: s.consistent for s in strict_check(llm, wiki, keep, workers, model=FAST_MODEL)}

    def verified(cid: str) -> bool:
        return pro.get(cid, True) and flash.get(cid, True)

    updated = []
    for c in current:
        if c.id not in verdicts:
            updated.append(c)
            continue
        cand, verdict = base[c.id], verdicts[c.id]
        if c.id in restore and still_valid(cand, verdict) and verified(c.id):
            reviewed = c.id in reviews and reviews[c.id].decision in ("keep", "edit")
            updated.append(confirm_restored(cand, verdict, revision, reviewed=reviewed))
        else:
            updated.append(follow_update(cand, verdict, revision, strictly_verified=verified(c.id)))
    write_jsonl(DATASET / "candidates.jsonl", updated)
    changed = [u.id for c, u in zip(current, updated, strict=True) if c != u]
    print(f"changed: {changed}; unchanged: {sorted(set(verdicts) - set(changed))}")
    print(f"usage {llm.usage.model_dump()}")
    return 0


def summary(candidates: Sequence[Candidate]) -> dict[str, Any]:
    """Count candidates by status, reason and kind change."""
    return {
        "candidates": len(candidates),
        "by_status": dict(sorted(Counter(c.status for c in candidates).items())),
        "reasons": dict(sorted(Counter(r for c in candidates for r in c.reasons).items())),
        "kind_changes": dict(
            sorted(
                Counter(
                    f"{c.previous_kind}->{c.kind}" for c in candidates if c.previous_kind != c.kind
                ).items()
            )
        ),
        "unanswerable": sum(c.kind == "unanswerable" for c in candidates),
    }


if __name__ == "__main__":
    sys.exit(main())
