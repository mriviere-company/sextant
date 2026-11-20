"""Load the Area Universe wiki from its translation files.

The game ships its wiki as one Symfony translation file per language
(`wiki.<lang>.yaml`). Besides UI strings it holds `articles` (slug → title,
category, order, tags, summary, related, HTML body), `categories` (a JSON
object of category labels, stored as a string) and `article_slugs` (the
canonical article order, a comma-separated string).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from sextant.ingest.sections import split_sections
from sextant.models import LANGS, Article, Lang


class CorpusError(ValueError):
    """Raised when the wiki files are inconsistent with each other or with their own index."""


def _csv(value: object) -> tuple[str, ...]:
    return tuple(part.strip() for part in str(value or "").split(",") if part.strip())


def _article(lang: Lang, slug: str, raw: dict[str, Any], categories: dict[str, str]) -> Article:
    category = str(raw["category"])
    if category not in categories:
        raise CorpusError(f"{lang}/{slug}: unknown category {category!r}")
    return Article(
        lang=lang,
        slug=slug,
        title=" ".join(str(raw["title"]).split()),
        category=category,
        category_label=categories[category],
        order=int(raw["order"]),
        tags=_csv(raw.get("tags")),
        summary=" ".join(str(raw.get("summary", "")).split()),
        related=_csv(raw.get("related")),
        sections=tuple(split_sections(str(raw["body"]))),
    )


def load_language(path: Path, lang: Lang) -> list[Article]:
    """Load every article of one language file, in the wiki's canonical order."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    categories: dict[str, str] = json.loads(data["categories"])
    order = _csv(data["article_slugs"])
    raw_articles: dict[str, dict[str, Any]] = data["articles"]
    if set(order) != set(raw_articles) or len(order) != len(raw_articles):
        missing = set(raw_articles) ^ set(order)
        raise CorpusError(f"{lang}: article_slugs and articles disagree on {sorted(missing)}")
    return [_article(lang, slug, raw_articles[slug], categories) for slug in order]


def load_corpus(directory: Path) -> dict[Lang, list[Article]]:
    """Load all six languages and check that they describe the same articles.

    Section anchors are translated (`#principe` in French, `#principle` in
    English), so languages are aligned by section *position*: the same article
    must have the same number of sections, with or without an intro, in every
    language. That alignment is what lets one evaluation question point to the
    same section in all six languages.
    """
    corpus = {lang: load_language(directory / f"wiki.{lang}.yaml", lang) for lang in LANGS}
    reference = [article.slug for article in corpus["fr"]]
    for lang, articles in corpus.items():
        slugs = [article.slug for article in articles]
        if slugs != reference:
            raise CorpusError(f"{lang}: article list differs from French")
        for fr_article, article in zip(corpus["fr"], articles, strict=True):
            shape = [bool(section.anchor) for section in article.sections]
            fr_shape = [bool(section.anchor) for section in fr_article.sections]
            if shape != fr_shape:
                raise CorpusError(f"{lang}/{article.slug}: section layout differs from French")
    return corpus
