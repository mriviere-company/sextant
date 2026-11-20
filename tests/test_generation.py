import json
from collections import Counter
from collections.abc import Sequence
from typing import Any

import pytest

from sextant.eval.dataset import Kind, SectionRef
from sextant.eval.generation import prompts
from sextant.eval.generation.models import Assignment, Idea, Judgement, Realized
from sextant.eval.generation.pipeline import (
    Wiki,
    assemble,
    draft_ideas,
    judge,
    parse_article_ideas,
    parse_cross_ideas,
    pool_sections,
    realize,
)
from sextant.eval.generation.select import (
    CROSS_LINGUAL_PER_LANG,
    MONOLINGUAL_PER_LANG,
    assign_languages,
    kind_totals,
    review_order,
    select_ideas,
)
from sextant.eval.generation.split import assign_splits
from sextant.llm import LlmError, Request
from sextant.models import LANGS, Article, Lang, Section
from sextant.retrieval.base import Hit


def _article(lang: Lang, slug: str, n_sections: int, related: tuple[str, ...] = ()) -> Article:
    return Article(
        lang=lang,
        slug=slug,
        title=f"{slug} ({lang})",
        category="fleet",
        category_label="Flotte",
        order=1,
        tags=(),
        summary=f"résumé {slug}",
        related=related,
        sections=tuple(
            Section(anchor=f"s{i}" if i else "", title=f"Section {i}", text=f"{slug} texte {i}")
            for i in range(n_sections)
        ),
    )


WIKI = Wiki(
    {
        lang: [
            _article(lang, "fleet", 3, related=("market",)),
            _article(lang, "market", 2, related=("fleet",)),
        ]
        for lang in LANGS
    }
)


def _ref(slug: str, index: int) -> SectionRef:
    return SectionRef(slug=slug, section_index=index)


# --- parsing -------------------------------------------------------------------------------


def test_parse_article_ideas_keeps_only_well_formed_ideas() -> None:
    payload = {
        "ideas": [
            {
                "kind": "factual",
                "question": "Combien de vaisseaux ?",
                "answer": "3",
                "sections": [1],
            },
            {
                "kind": "multi_section",
                "question": "Une seule section ?",
                "answer": "x",
                "sections": [0],
            },
            {"kind": "factual", "question": "Section inconnue ?", "answer": "x", "sections": [9]},
            {
                "kind": "unanswerable",
                "question": "Et la météo du jeu ?",
                "answer": "-",
                "sections": [1],
            },
            {"kind": "bogus", "question": "Type inconnu ici ?", "answer": "x", "sections": [0]},
            "pas un objet",
        ]
    }
    ideas = parse_article_ideas("fleet", payload, WIKI)
    assert [(i.id, i.kind) for i in ideas] == [("fleet.0", "factual"), ("fleet.3", "unanswerable")]
    assert ideas[0].sections == (_ref("fleet", 1),)
    assert ideas[1].sections == ()  # an unanswerable idea never carries sections


def test_parse_cross_ideas_requires_both_articles() -> None:
    payload = {
        "ideas": [
            {"question": "Question sur les deux ?", "answer": "a", "sections": ["A:0", "B:1"]},
            {"question": "Question sur A seul ?", "answer": "a", "sections": ["A:0", "A:2"]},
            {"question": "Section hors limite ?", "answer": "a", "sections": ["A:0", "B:7"]},
        ]
    }
    ideas = parse_cross_ideas("fleet", "market", payload, WIKI)
    assert len(ideas) == 1
    assert ideas[0].sections == (_ref("fleet", 0), _ref("market", 1))
    assert ideas[0].kind == "multi_section"
    assert ideas[0].origin == "cross_article"


# --- selection -----------------------------------------------------------------------------


def _many_ideas() -> list[Idea]:
    """Plenty of ideas of every pool, over 40 articles of 6 sections."""
    ideas: list[Idea] = []
    for a in range(40):
        slug = f"art{a}"
        for kind in ("factual", "procedural", "comparative", "multi_section", "unanswerable"):
            for n in range(3):
                sections: tuple[SectionRef, ...] = ()
                if kind == "multi_section":
                    sections = (_ref(slug, n), _ref(slug, n + 1))
                elif kind != "unanswerable":
                    sections = (_ref(slug, n),)
                ideas.append(
                    Idea(
                        id=f"{slug}.{kind}.{n}",
                        origin="article",
                        slug=slug,
                        kind=kind,
                        question=f"question {slug} {kind} {n}",
                        answer="réponse",
                        sections=sections,
                    )
                )
        ideas.append(
            Idea(
                id=f"x.{slug}",
                origin="cross_article",
                slug=slug,
                kind="multi_section",
                question=f"question croisée {slug}",
                answer="réponse",
                sections=(_ref(slug, 5), _ref(f"art{(a + 1) % 40}", 4)),
            )
        )
    ideas += [
        Idea(
            id=f"oos.{n}",
            origin="out_of_scope",
            kind="unanswerable",
            question=f"hors {n} ?",
            answer="-",
        )
        for n in range(20)
    ]
    return ideas


def test_select_meets_every_kind_total_and_spreads_sections() -> None:
    selected, shortfall = select_ideas(_many_ideas())
    assert shortfall == {}
    assert Counter(i.kind for i in selected) == Counter(kind_totals())
    origins = Counter((i.kind, i.origin) for i in selected)
    assert origins[("multi_section", "cross_article")] == 27
    assert origins[("unanswerable", "out_of_scope")] == 10
    uses = Counter((s.slug, s.section_index) for i in selected for s in i.sections)
    assert max(uses.values()) <= 2
    assert select_ideas(_many_ideas()) == (selected, shortfall)  # deterministic


def test_select_carries_a_scarce_pool_and_reports_a_short_kind() -> None:
    ideas = [i for i in _many_ideas() if i.origin != "cross_article" and i.kind != "comparative"]
    selected, shortfall = select_ideas(ideas)
    assert Counter(i.kind for i in selected)["multi_section"] == kind_totals()["multi_section"]
    assert shortfall == {"comparative/article": kind_totals()["comparative"]}


def test_languages_follow_the_quotas_and_cross_lingual_targets_are_spread() -> None:
    selected, _ = select_ideas(_many_ideas())
    plan = assign_languages(selected)
    by_id = {i.id: i for i in selected}
    assert len(plan) == len(selected)
    for lang in LANGS:
        for kind, mono in MONOLINGUAL_PER_LANG.items():
            mine = [a for a in plan if a.lang == lang and by_id[a.idea_id].kind == kind]
            cross = [a for a in mine if a.corpus_lang]
            assert len(mine) == mono + CROSS_LINGUAL_PER_LANG.get(kind, 0)
            assert len(cross) == CROSS_LINGUAL_PER_LANG.get(kind, 0)
    crossed = [a for a in plan if a.corpus_lang]
    assert all(a.corpus_lang != a.lang for a in crossed)
    assert Counter(a.corpus_lang for a in crossed) == dict.fromkeys(LANGS, 4)
    assert len({(a.lang, a.corpus_lang) for a in crossed}) == len(crossed)  # no pair reused
    # an article's questions use different languages while quotas allow it
    per_article = Counter((by_id[a.idea_id].slug, a.lang) for a in plan if by_id[a.idea_id].slug)
    assert max(per_article.values()) <= 2


def test_review_order_keeps_every_prefix_balanced() -> None:
    items = [f"{lang}-{n}" for lang in ("fr", "en", "de") for n in range(10)]
    ordered = review_order(items, {p: item[:2] for p, item in enumerate(items)})
    assert sorted(ordered) == sorted(items)
    first = Counter(item[:2] for item in ordered[:9])
    assert all(2 <= n <= 4 for n in first.values())


# --- split ---------------------------------------------------------------------------------


def test_splits_keep_groups_together_and_balance_cells() -> None:
    groups = {f"q{i}": f"article{i // 3}" for i in range(60)}
    cells = {f"q{i}": ("fr", "en")[i % 2] for i in range(60)}
    splits = assign_splits(groups, cells)
    for article in set(groups.values()):
        assert len({splits[q] for q, g in groups.items() if g == article}) == 1
    sizes = Counter(splits.values())
    assert abs(sizes["dev"] - sizes["test"]) <= 3
    for cell in ("fr", "en"):
        per = Counter(splits[q] for q in groups if cells[q] == cell)
        assert abs(per["dev"] - per["test"]) <= 3
    assert assign_splits(groups, cells) == splits


# --- stages with a scripted LLM ------------------------------------------------------------


class _ScriptedLlm:
    """Answers by matching the start of the system prompt; records every request."""

    def __init__(self, script: dict[str, Any]) -> None:
        self.script = script
        self.requests: list[Request] = []

    def complete_json(self, request: Request) -> dict[str, Any]:
        self.requests.append(request)
        for marker, answer in self.script.items():
            if marker in request.system or marker in request.user:
                if isinstance(answer, Exception):
                    raise answer
                return answer(request) if callable(answer) else dict(answer)
        raise AssertionError(f"no scripted answer for {request.system[:60]!r}")


def test_draft_ideas_covers_articles_pairs_and_out_of_scope() -> None:
    llm = _ScriptedLlm(
        {
            "deux articles liés": {
                "ideas": [
                    {"question": "Croisée A et B ?", "answer": "a", "sections": ["A:0", "B:0"]}
                ]
            },
            "liste des articles": {
                "ideas": [{"question": "Comment payer en ligne ?", "answer": "-"}]
            },
            "# fleet": {
                "ideas": [
                    {
                        "kind": "factual",
                        "question": "Fait sur fleet ?",
                        "answer": "a",
                        "sections": [0],
                    }
                ]
            },
            "# market": LlmError("bad json twice"),
        }
    )
    ideas = draft_ideas(llm, WIKI, workers=2)
    assert sorted(i.id for i in ideas) == ["fleet.0", "oos.0", "x.fleet.market.0"]
    assert all(r.user.count("## [") >= 1 for r in llm.requests if "# fleet" in r.user)


def test_realize_shows_the_searched_language_and_keeps_french_glosses() -> None:
    idea = Idea(
        id="fleet.0",
        origin="article",
        slug="fleet",
        kind="factual",
        question="Combien ?",
        answer="Trois.",
        sections=(_ref("fleet", 1),),
    )
    answer = {
        "question": "How many?",
        "answer": "Three.",
        "question_fr": "Combien ?",
        "answer_fr": "Trois.",
    }
    llm = _ScriptedLlm({"Idée de question": answer})
    plan = [
        Assignment(idea_id="fleet.0", lang="en", corpus_lang="ru", style="short"),
    ]
    realized = realize(llm, WIKI, {"fleet.0": idea}, plan, workers=1)
    assert realized[0].question == "How many?"
    assert realized[0].corpus_lang == "ru"
    request = llm.requests[0]
    assert "fleet (ru)" in request.user  # sections shown in the searched corpus
    assert "anglais (en)" in request.system

    french = realize(
        llm,
        WIKI,
        {"fleet.0": idea},
        [plan[0].model_copy(update={"lang": "fr", "corpus_lang": None})],
        1,
    )
    assert french[0].question_fr == french[0].question  # no gloss needed in French


def test_pool_sections_unions_the_top_sections_of_every_strategy() -> None:
    class _Fixed:
        def __init__(self, ids: Sequence[str]) -> None:
            self.ids = ids

        @property
        def name(self) -> str:
            return "fixed"

        def search(self, query: str, lang: Lang, k: int) -> list[Hit]:
            return [Hit(chunk_id=i, score=1.0) for i in self.ids[:k]]

    section_of = {
        "a0": _ref("fleet", 0),
        "a1": _ref("fleet", 0),
        "b": _ref("fleet", 1),
        "c": _ref("market", 0),
    }
    pooled = pool_sections(
        "q", "fr", [_Fixed(["a0", "a1", "b"]), _Fixed(["c", "b"])], section_of, depth=2
    )
    assert pooled == [_ref("fleet", 0), _ref("fleet", 1), _ref("market", 0)]


def _realized(idea_id: str, lang: Lang = "fr") -> Realized:
    return Realized(
        idea_id=idea_id,
        lang=lang,
        style="natural",
        question=f"question {idea_id}",
        answer="réponse",
        question_fr=f"question {idea_id}",
        answer_fr="réponse",
    )


def test_judge_maps_labels_back_to_sections_in_wiki_order() -> None:
    idea = Idea(
        id="fleet.0",
        origin="article",
        slug="fleet",
        kind="factual",
        question="q ?",
        answer="a",
        sections=(_ref("fleet", 2),),
    )
    llm = _ScriptedLlm(
        {"You judge relevance": {"relevant": ["S1", "S9"], "answerable": True, "note": ""}}
    )
    pool = [_ref("market", 0), _ref("fleet", 0)]
    [verdict] = judge(llm, WIKI, [(_realized("fleet.0"), idea, pool)], workers=1)
    assert verdict.pooled == (_ref("fleet", 0), _ref("fleet", 2), _ref("market", 0))
    assert verdict.relevant == (_ref("fleet", 0),)  # S9 does not exist and is ignored
    assert verdict.answerable


def test_assemble_proposes_relevance_flags_and_a_frozen_split() -> None:
    ideas = {
        "fleet.0": Idea(
            id="fleet.0",
            origin="article",
            slug="fleet",
            kind="factual",
            question="q ?",
            answer="a",
            sections=(_ref("fleet", 1),),
        ),
        "market.1": Idea(
            id="market.1",
            origin="article",
            slug="market",
            kind="unanswerable",
            question="u ?",
            answer="-",
        ),
    }
    judgements = {
        "fleet.0": Judgement(
            idea_id="fleet.0",
            pooled=(_ref("fleet", 0), _ref("fleet", 1), _ref("market", 0)),
            relevant=(_ref("market", 0),),
            answerable=True,
        ),
        "market.1": Judgement(
            idea_id="market.1",
            pooled=(_ref("market", 0), _ref("market", 1)),
            relevant=(_ref("market", 1),),
            answerable=False,
        ),
    }
    candidates = assemble(ideas, [_realized("fleet.0"), _realized("market.1", "de")], judgements)
    by_idea = {c.idea_id: c for c in candidates}
    factual = by_idea["fleet.0"]
    assert factual.relevant == (_ref("fleet", 1), _ref("market", 0))
    assert factual.judge_added == (_ref("market", 0),)
    assert factual.flags == ("source_not_confirmed",)
    unanswerable = by_idea["market.1"]
    assert unanswerable.relevant == ()
    assert unanswerable.judge_found == (_ref("market", 1),)
    assert unanswerable.flags == ("judge_found_answer",)
    assert sorted(c.id for c in candidates) == ["q001", "q002"]
    assert {c.split for c in candidates} <= {"dev", "test"}
    json.dumps([c.model_dump(mode="json") for c in candidates])


@pytest.mark.parametrize(
    "kind", ["factual", "procedural", "comparative", "multi_section", "unanswerable"]
)
def test_every_kind_has_a_quota(kind: Kind) -> None:
    assert kind_totals()[kind] > 0


def test_every_json_prompt_says_json() -> None:
    # DeepSeek refuses response_format=json_object unless the prompt mentions JSON.
    for name in (
        "IDEAS_SYSTEM",
        "CROSS_SYSTEM",
        "OUT_OF_SCOPE_SYSTEM",
        "REALIZE_SYSTEM",
        "JUDGE_SYSTEM",
    ):
        assert "json" in getattr(prompts, name).lower(), name
