"""Integrity of the real wiki snapshot: the acceptance criteria of phase 0."""

from collections import Counter
from functools import cache

from sextant.ingest.chunking import DEFAULT_MAX_WORDS, chunk_corpus
from sextant.ingest.cli import WIKI_DIR, build, main
from sextant.ingest.wiki import load_corpus
from sextant.models import LANGS, Article, Chunk, Lang


@cache
def _corpus() -> dict[Lang, list[Article]]:
    return load_corpus(WIKI_DIR)


@cache
def _chunks() -> list[Chunk]:
    return chunk_corpus(article for articles in _corpus().values() for article in articles)


def test_all_72_articles_in_all_six_languages() -> None:
    corpus = _corpus()
    assert set(corpus) == set(LANGS)
    assert {len(articles) for articles in corpus.values()} == {72}


def test_every_section_is_aligned_across_languages() -> None:
    corpus = _corpus()
    for index, fr_article in enumerate(corpus["fr"]):
        counts = {len(corpus[lang][index].sections) for lang in LANGS}
        assert counts == {len(fr_article.sections)}, fr_article.slug


def test_chunk_ids_are_unique_and_sizes_bounded() -> None:
    chunks = _chunks()
    ids = Counter(chunk.id for chunk in chunks)
    assert max(ids.values()) == 1
    assert max(chunk.n_words for chunk in chunks) <= DEFAULT_MAX_WORDS


def test_every_section_produces_at_least_one_chunk() -> None:
    covered = {(chunk.lang, chunk.slug, chunk.section_index) for chunk in _chunks()}
    for lang, articles in _corpus().items():
        for article in articles:
            for index in range(len(article.sections)):
                assert (lang, article.slug, index) in covered


def test_committed_stats_match_the_snapshot() -> None:
    _, stats = build()
    assert stats["total_chunks"] == len(_chunks())
    assert main(["--check"]) == 0
