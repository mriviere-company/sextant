import pytest

from sextant.ingest.chunking import chunk_article, split_text
from sextant.models import Article, Section


def _article(*sections: Section) -> Article:
    return Article(
        lang="fr",
        slug="first_fleet",
        title="Première flotte",
        category="beginner",
        category_label="Premiers pas",
        order=1,
        tags=("flotte",),
        summary="Résumé.",
        related=(),
        sections=sections,
    )


def test_short_text_is_one_part() -> None:
    assert split_text("un deux trois", max_words=10) == ["un deux trois"]


def test_long_text_splits_on_block_boundaries() -> None:
    text = "a b c\n\nd e f\n\ng h"
    assert split_text(text, max_words=6) == ["a b c\n\nd e f", "g h"]


def test_single_oversized_line_is_cut_on_words() -> None:
    assert split_text("a b c d e", max_words=2) == ["a b", "c d", "e"]


def test_oversized_list_is_split_between_items() -> None:
    text = "- un deux\n- trois quatre\n- cinq six"
    assert split_text(text, max_words=4) == ["- un deux\n- trois quatre", "- cinq six"]


def test_oversized_table_repeats_its_header_in_every_part() -> None:
    table = "| Nom | Coût |\n|---|---|\n| Cargo | 10 |\n| Chasseur | 20 |\n| Croiseur | 30 |"
    parts = split_text(table, max_words=6)
    assert len(parts) > 1
    for part in parts:
        assert part.startswith("| Nom | Coût |\n|---|---|\n| ")
    rows = [line for part in parts for line in part.split("\n")[2:]]
    assert rows == ["| Cargo | 10 |", "| Chasseur | 20 |", "| Croiseur | 30 |"]


def test_max_words_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        split_text("a", max_words=0)


def test_chunk_ids_urls_and_embed_text() -> None:
    article = _article(
        Section(anchor="", title="", text="Intro."),
        Section(anchor="composer", title="Étape 2", text="Composez la flotte."),
    )
    intro, step = chunk_article(article)
    assert intro.id == "fr:first_fleet#intro:0"
    assert intro.url == "https://www.areauniverse.com/wiki/first_fleet"
    assert intro.embed_text == "Première flotte\n\nIntro."
    assert step.id == "fr:first_fleet#composer:0"
    assert step.section_index == 1
    assert step.url == "https://www.areauniverse.com/wiki/first_fleet#composer"
    assert step.embed_text == "Première flotte — Étape 2\n\nComposez la flotte."
    assert step.n_words == 3


def test_split_section_gets_numbered_parts() -> None:
    long_text = "\n\n".join(["mot " * 200] * 2).strip()
    chunks = chunk_article(_article(Section(anchor="long", title="Long", text=long_text)))
    assert [chunk.id for chunk in chunks] == ["fr:first_fleet#long:0", "fr:first_fleet#long:1"]
