"""Turn the wiki's HTML into light Markdown text.

The wiki bodies use a small, regular subset of HTML (paragraphs, lists,
tables, `<h3>`, inline emphasis). An LLM reads Markdown well and an embedding
model only needs the words, so the conversion keeps structure where it carries
meaning (list items, table rows with their headers) and drops presentation
(bold, italics, links become their text).

Ordered lists are rendered with `- ` like unordered ones: the order survives in
the sequence, and not injecting list numbers keeps the conversion word-for-word
lossless, which `tests/test_html_text.py` checks on the whole corpus.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, PageElement, Tag

_WS = re.compile(r"\s+")


def inline_text(node: PageElement) -> str:
    """Text of an inline fragment with whitespace collapsed; `<code>` keeps backticks."""
    if isinstance(node, Comment):
        return ""
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""
    if node.name == "code":
        return f"`{_WS.sub(' ', node.get_text()).strip()}`"
    if node.name == "br":
        return " "
    return "".join(inline_text(child) for child in node.children)


def _clean(text: str) -> str:
    return _WS.sub(" ", text).strip()


def _list(node: Tag, depth: int) -> list[str]:
    lines: list[str] = []
    for item in node.find_all("li", recursive=False):
        nested = [
            child
            for child in item.children
            if isinstance(child, Tag) and child.name in {"ul", "ol"}
        ]
        own = "".join(
            inline_text(child)
            for child in item.children
            if not (isinstance(child, Tag) and child.name in {"ul", "ol"})
        )
        if _clean(own):
            lines.append(f"{'  ' * depth}- {_clean(own)}")
        for sub in nested:
            lines.extend(_list(sub, depth + 1))
    return lines


def _table(node: Tag) -> list[str]:
    rows: list[list[str]] = []
    header_rows = 0
    for tr in node.find_all("tr"):
        cells = tr.find_all(["th", "td"], recursive=False)
        if not cells:
            continue
        rows.append([_clean(inline_text(cell)).replace("|", "/") for cell in cells])
        if all(cell.name == "th" for cell in cells) and len(rows) == header_rows + 1:
            header_rows += 1
    if not rows:
        return []
    lines = [f"| {' | '.join(row)} |" for row in rows]
    if header_rows:
        width = len(rows[header_rows - 1])
        lines.insert(header_rows, "|" + "---|" * width)
    return lines


def _prefixed(prefix: str) -> Callable[[Tag], str]:
    def render(node: Tag) -> str:
        text = _clean(inline_text(node))
        return f"{prefix}{text}" if text else ""

    return render


_RENDERERS: dict[str, Callable[[Tag], str]] = {
    "ul": lambda node: "\n".join(_list(node, 0)),
    "ol": lambda node: "\n".join(_list(node, 0)),
    "table": lambda node: "\n".join(_table(node)),
    "h3": _prefixed("### "),
    "blockquote": _prefixed("> "),
}


def block_text(node: PageElement) -> str:
    """Markdown text of one block-level node (empty string when it carries no text)."""
    if isinstance(node, Comment) or not isinstance(node, Tag | NavigableString):
        return ""
    if isinstance(node, NavigableString):
        return _clean(str(node))
    render = _RENDERERS.get(node.name)
    return render(node) if render else _clean(inline_text(node))


def fragment_soup(html: str) -> BeautifulSoup:
    """Parse an HTML fragment with the standard-library parser (no native dependency)."""
    return BeautifulSoup(html, "html.parser")


def html_to_text(html: str) -> str:
    """Convert a whole HTML fragment to Markdown text, blocks separated by blank lines."""
    soup = fragment_soup(html)
    blocks = (block_text(child) for child in soup.children)
    return "\n\n".join(block for block in blocks if block)
