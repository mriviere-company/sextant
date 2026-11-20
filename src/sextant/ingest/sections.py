"""Split an article body into its `<h2>` sections.

Sections are the natural retrieval unit here: every `<h2>` in the wiki carries
an `id`, so a citation can link straight to `…/wiki/<slug>#<anchor>`. Text
before the first `<h2>` becomes an intro section with an empty anchor.
"""

from __future__ import annotations

from bs4.element import Tag

from sextant.ingest.html_text import block_text, fragment_soup, inline_text
from sextant.models import Section


class MalformedArticleError(ValueError):
    """Raised when an article body does not have the structure the wiki guarantees."""


def split_sections(html: str) -> list[Section]:
    """Return the sections of one article body, in document order."""
    soup = fragment_soup(html)
    sections: list[Section] = []
    anchor, title = "", ""
    blocks: list[str] = []

    def flush() -> None:
        text = "\n\n".join(block for block in blocks if block)
        if text:
            sections.append(Section(anchor=anchor, title=title, text=text))
        elif anchor:
            raise MalformedArticleError(f"section #{anchor} ({title!r}) has no content")

    for child in soup.children:
        if isinstance(child, Tag) and child.name == "h2":
            flush()
            found = child.get("id")
            if not isinstance(found, str) or not found:
                raise MalformedArticleError(f"<h2> without id: {child}")
            anchor, title, blocks = found, " ".join(inline_text(child).split()), []
        else:
            blocks.append(block_text(child))
    flush()

    anchors = [section.anchor for section in sections if section.anchor]
    if len(anchors) != len(set(anchors)):
        raise MalformedArticleError(f"duplicate section anchors: {anchors}")
    return sections
