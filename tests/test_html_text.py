import html as html_lib
import re
from collections import Counter
from pathlib import Path

import pytest
import yaml

from sextant.ingest.html_text import html_to_text

WIKI = Path(__file__).resolve().parents[1] / "corpus" / "wiki"


def test_paragraphs_are_separated_and_emphasis_dropped() -> None:
    html = "<p>Un <strong>Chantier</strong>   spatial.</p>\n<p>Deuxième <em>paragraphe</em>.</p>"
    assert html_to_text(html) == "Un Chantier spatial.\n\nDeuxième paragraphe."


def test_lists_ordered_and_nested() -> None:
    html = "<ol><li>Un</li><li>Deux<ul><li>Sous-point</li></ul></li></ol>"
    assert html_to_text(html) == "- Un\n- Deux\n  - Sous-point"


def test_table_keeps_header_row() -> None:
    html = (
        "<table><tr><th>Vaisseau</th><th>Coût</th></tr>"
        "<tr><td>Cargo</td><td>100 | 50</td></tr></table>"
    )
    assert html_to_text(html) == "| Vaisseau | Coût |\n|---|---|\n| Cargo | 100 / 50 |"


def test_links_become_text_and_code_keeps_backticks() -> None:
    html = '<p>Voir <a href="/wiki/market">le marché</a> et tapez <code>/aide</code>.</p>'
    assert html_to_text(html) == "Voir le marché et tapez `/aide`."


def test_h3_and_blockquote() -> None:
    assert html_to_text("<h3>Astuce</h3><blockquote>Restez actif</blockquote>") == (
        "### Astuce\n\n> Restez actif"
    )


def _words(text: str) -> Counter[str]:
    return Counter(re.findall(r"\w+", text))


_BLOCK_TAG = re.compile(r"</?(?:p|li|td|th|tr|h2|h3|ul|ol|table|blockquote|br)\b[^>]*>")
_ANY_TAG = re.compile(r"<[^>]+>")


def _reference_text(body: str) -> str:
    """Independent of the code under test: block tags become spaces, inline tags vanish.

    Inline tags must vanish without a space, or `<strong>Hauptheld</strong>en`
    would read as two words while it is one ("Haupthelden").
    """
    return html_lib.unescape(_ANY_TAG.sub("", _BLOCK_TAG.sub(" ", body)))


@pytest.mark.parametrize("lang", ["fr", "en", "de", "es", "pt", "ru"])
def test_conversion_is_word_for_word_lossless_on_the_whole_corpus(lang: str) -> None:
    articles = yaml.safe_load((WIKI / f"wiki.{lang}.yaml").read_text(encoding="utf-8"))["articles"]
    for slug, article in articles.items():
        source = _reference_text(article["body"])
        assert _words(html_to_text(article["body"])) == _words(source), slug
