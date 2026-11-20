import pytest

from sextant.ingest.sections import MalformedArticleError, split_sections


def test_intro_then_sections() -> None:
    html = (
        '<p>Intro.</p><h2 id="a">Premier</h2><p>Texte A.</p>'
        '<h2 id="b">Second</h2><ul><li>B</li></ul>'
    )
    sections = split_sections(html)
    assert [(s.anchor, s.title, s.text) for s in sections] == [
        ("", "", "Intro."),
        ("a", "Premier", "Texte A."),
        ("b", "Second", "- B"),
    ]


def test_no_intro_when_body_starts_with_h2() -> None:
    sections = split_sections('<h2 id="a">Titre</h2><p>Texte.</p>')
    assert [s.anchor for s in sections] == ["a"]


def test_h2_without_id_is_rejected() -> None:
    with pytest.raises(MalformedArticleError, match="without id"):
        split_sections("<h2>Titre</h2><p>Texte.</p>")


def test_empty_section_is_rejected() -> None:
    with pytest.raises(MalformedArticleError, match="no content"):
        split_sections('<h2 id="a">Vide</h2><h2 id="b">Plein</h2><p>x</p>')


def test_duplicate_anchor_is_rejected() -> None:
    with pytest.raises(MalformedArticleError, match="duplicate"):
        split_sections('<h2 id="a">Un</h2><p>x</p><h2 id="a">Deux</h2><p>y</p>')
