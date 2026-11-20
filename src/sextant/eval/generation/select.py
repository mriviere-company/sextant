"""Choose which drafted ideas become candidates, and in which language.

Pure and seeded: the same ideas and seed always give the same plan.

Targets (per question language, x6 languages, 288 candidates in total):

| kind | monolingual | cross-lingual |
|---|---|---|
| factual | 12 | 2 |
| procedural | 9 | 2 |
| comparative | 7 | — |
| multi_section | 9 | — |
| unanswerable | 7 | — |

so 42 unanswerable questions (14.6 %, the plan's ~15 %) and 24 cross-lingual
ones, 4 per question language and 4 per searched language. Half of the
multi-section questions span two linked articles, and about a quarter of the
unanswerable ones are out of the wiki's scope altogether; the rest stay close
to an article, which is the hard case for a refusal.

Three spreading rules keep the set diverse: an idea whose sections were
already used is picked last, articles are used evenly, and the languages of
one article's questions differ as much as the quotas allow (so per-language
metrics are not computed on different topics). The review order interleaves
languages and kinds, so stopping the review early still leaves a balanced set.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from collections.abc import Sequence

from sextant.eval.dataset import Kind
from sextant.eval.generation.models import Assignment, Idea, Style
from sextant.models import LANGS, Lang

MONOLINGUAL_PER_LANG: dict[Kind, int] = {
    "factual": 12,
    "procedural": 9,
    "comparative": 7,
    "multi_section": 9,
    "unanswerable": 7,
}
CROSS_LINGUAL_PER_LANG: dict[Kind, int] = {"factual": 2, "procedural": 2}
CROSS_ARTICLE_SHARE = 0.5  # of multi_section questions
OUT_OF_SCOPE_SHARE = 0.25  # of unanswerable questions
STYLE_WEIGHTS: dict[Style, float] = {"short": 0.3, "natural": 0.5, "situated": 0.2}


def kind_totals() -> dict[Kind, int]:
    """Candidates wanted per kind, all languages together."""
    totals: dict[Kind, int] = {}
    for kind, n in MONOLINGUAL_PER_LANG.items():
        totals[kind] = (n + CROSS_LINGUAL_PER_LANG.get(kind, 0)) * len(LANGS)
    return totals


def _pool_quotas(totals: dict[Kind, int]) -> list[tuple[Kind, str, int]]:
    """Split each kind's total over idea origins; scarce pools are served first."""
    multi = totals["multi_section"]
    cross = round(multi * CROSS_ARTICLE_SHARE)
    unanswerable = totals["unanswerable"]
    out_of_scope = round(unanswerable * OUT_OF_SCOPE_SHARE)
    return [
        ("multi_section", "cross_article", cross),
        ("unanswerable", "out_of_scope", out_of_scope),
        ("comparative", "article", totals["comparative"]),
        ("procedural", "article", totals["procedural"]),
        ("multi_section", "article", multi - cross),
        ("unanswerable", "article", unanswerable - out_of_scope),
        ("factual", "article", totals["factual"]),
    ]


def select_ideas(ideas: Sequence[Idea], seed: int = 42) -> tuple[list[Idea], dict[str, int]]:
    """Pick ideas to meet the kind totals; returns them and the shortfall per pool.

    A pool short of ideas passes its shortfall to the next pool of the same
    kind (cross-article → same-article multi-section, out-of-scope → article
    unanswerable); a kind still short is reported, never padded with another
    kind, so the published kind mix stays honest.
    """
    rng = random.Random(seed)
    section_use: Counter[tuple[str, int]] = Counter()
    article_use: Counter[str] = Counter()
    chosen: list[Idea] = []
    shortfall: dict[str, int] = {}
    carry: dict[Kind, int] = defaultdict(int)
    tiebreak = {idea.id: rng.random() for idea in ideas}

    for kind, origin, quota in _pool_quotas(kind_totals()):
        want = quota + carry.pop(kind, 0)
        pool = [i for i in ideas if i.kind == kind and i.origin == origin]
        picked = 0
        while picked < want and pool:

            def cost(idea: Idea) -> tuple[int, int, float]:
                worst = max(
                    (section_use[(s.slug, s.section_index)] for s in idea.sections), default=0
                )
                return (worst, article_use[idea.slug], tiebreak[idea.id])

            best = min(pool, key=cost)
            pool.remove(best)
            chosen.append(best)
            picked += 1
            article_use[best.slug] += 1
            for section in best.sections:
                section_use[(section.slug, section.section_index)] += 1
        if picked < want:
            missing = want - picked
            if origin in ("cross_article", "out_of_scope"):
                carry[kind] += missing
            else:
                shortfall[f"{kind}/{origin}"] = missing
    return chosen, shortfall


def assign_languages(selected: Sequence[Idea], seed: int = 42) -> list[Assignment]:
    """Give each selected idea a question language, a search corpus and a style.

    Language slots per kind follow the quotas exactly when enough ideas were
    selected; when a kind is short, its slots are left empty evenly across
    languages (the largest remaining quota is served first).
    """
    rng = random.Random(seed)
    article_langs: defaultdict[str, Counter[Lang]] = defaultdict(Counter)
    assignments: list[Assignment] = []

    by_kind: defaultdict[Kind, list[Idea]] = defaultdict(list)
    for idea in selected:
        by_kind[idea.kind].append(idea)

    for kind, mono in MONOLINGUAL_PER_LANG.items():
        ideas = sorted(by_kind.get(kind, []), key=lambda i: i.id)
        rng.shuffle(ideas)
        cross = CROSS_LINGUAL_PER_LANG.get(kind, 0)
        remaining: dict[Lang, int] = dict.fromkeys(LANGS, mono + cross)
        per_lang: defaultdict[Lang, list[Idea]] = defaultdict(list)
        for idea in ideas:
            open_langs = [lang for lang in LANGS if remaining[lang] > 0]
            if not open_langs:
                break
            seen = article_langs[idea.slug] if idea.slug else Counter[Lang]()
            lang = min(open_langs, key=lambda la: (seen[la], -remaining[la], rng.random()))
            remaining[lang] -= 1
            if idea.slug:
                article_langs[idea.slug][lang] += 1
            per_lang[lang].append(idea)
        for lang_index, lang in enumerate(LANGS):
            group = per_lang[lang]
            cross_ids = {i.id for i in rng.sample(group, min(cross, len(group)))}
            offset = 0
            for idea in group:
                corpus: Lang | None = None
                if idea.id in cross_ids:
                    # (i + 1), (i + 2)… so every language is searched by others equally.
                    corpus = LANGS[(lang_index + 1 + _cross_offset(kind) + offset) % len(LANGS)]
                    offset += 1
                assignments.append(
                    Assignment(idea_id=idea.id, lang=lang, corpus_lang=corpus, style=_style(rng))
                )
    return assignments


def _cross_offset(kind: Kind) -> int:
    """Shift each kind's cross-lingual targets so a language pair is not reused."""
    return sum(CROSS_LINGUAL_PER_LANG[k] for k in CROSS_LINGUAL_PER_LANG if k < kind)


def _style(rng: random.Random) -> Style:
    styles = list(STYLE_WEIGHTS)
    return rng.choices(styles, weights=[STYLE_WEIGHTS[s] for s in styles])[0]


def review_order[T](items: Sequence[T], bucket: dict[int, str], seed: int = 42) -> list[T]:
    """Interleave buckets (language x kind) so that every prefix is balanced.

    Each item gets the key `(rank within its bucket + u) / bucket size`, with
    `u` uniform in [0, 1): a bucket's items spread evenly over the whole order.
    `bucket` maps an item's position in `items` to its bucket name.
    """
    rng = random.Random(seed)
    members: defaultdict[str, list[int]] = defaultdict(list)
    for position in range(len(items)):
        members[bucket[position]].append(position)
    keys: dict[int, float] = {}
    for name in sorted(members):
        positions = members[name]
        rng.shuffle(positions)
        for rank, position in enumerate(positions):
            keys[position] = (rank + rng.random()) / len(positions)
    return [items[p] for p in sorted(range(len(items)), key=lambda p: (keys[p], p))]
