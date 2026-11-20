"""Cut sections into chunks.

Wiki sections are short (median ~57 words in French), so one section is one
chunk almost everywhere. A section longer than `max_words` is split on block
boundaries (paragraphs, lists, tables); a block that is itself too long (a big
table or list) is split line by line, and only a single overlong line is cut
on word boundaries. No overlap is added between parts: whether overlap helps
retrieval is a phase 2 measurement, not a default.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

from sextant.models import Article, Chunk, Section

DEFAULT_MAX_WORDS = 300
_WORD = re.compile(r"\w+")


def _word_count(text: str) -> int:
    """Count real words: Markdown table pipes and list dashes are not words."""
    return len(_WORD.findall(text))


def _split_words(line: str, max_words: int) -> Iterator[str]:
    words = line.split()
    for start in range(0, len(words), max_words):
        yield " ".join(words[start : start + max_words])


def _table_header(lines: list[str]) -> list[str]:
    is_table = len(lines) > 1 and lines[0].startswith("|")
    if is_table and set(lines[1]) <= set("|-"):
        return lines[:2]
    return []


def _split_long_block(block: str, max_words: int) -> Iterator[str]:
    """Split one oversized block line by line (list items, table rows).

    A table keeps its header row in every part, so a chunk that starts at row
    40 still says what its columns mean. Only a single line longer than the
    budget is cut on word boundaries.
    """
    lines = block.split("\n")
    header = _table_header(lines)
    body = lines[len(header) :]
    budget = max(1, max_words - _word_count("\n".join(header)))
    current: list[str] = []
    current_words = 0
    for line in body:
        size = _word_count(line)
        if size > budget:
            if current:
                yield "\n".join(header + current)
                current, current_words = [], 0
            for piece in _split_words(line, budget):
                yield "\n".join([*header, piece])
            continue
        if current and current_words + size > budget:
            yield "\n".join(header + current)
            current, current_words = [], 0
        current.append(line)
        current_words += size
    if current:
        yield "\n".join(header + current)


def split_text(text: str, max_words: int = DEFAULT_MAX_WORDS) -> list[str]:
    """Split text into parts of at most `max_words`, preferring block boundaries."""
    if max_words < 1:
        raise ValueError("max_words must be positive")
    parts: list[str] = []
    current: list[str] = []
    current_words = 0
    for block in text.split("\n\n"):
        size = _word_count(block)
        if size > max_words:
            if current:
                parts.append("\n\n".join(current))
                current, current_words = [], 0
            parts.extend(_split_long_block(block, max_words))
            continue
        if current and current_words + size > max_words:
            parts.append("\n\n".join(current))
            current, current_words = [], 0
        current.append(block)
        current_words += size
    if current:
        parts.append("\n\n".join(current))
    return parts


def chunk_id(article: Article, section: Section, part: int) -> str:
    """Stable id: `<lang>:<slug>#<anchor or 'intro'>:<part>`."""
    return f"{article.lang}:{article.slug}#{section.anchor or 'intro'}:{part}"


def chunk_article(article: Article, max_words: int = DEFAULT_MAX_WORDS) -> list[Chunk]:
    """Chunks of one article, in document order."""
    chunks: list[Chunk] = []
    for index, section in enumerate(article.sections):
        header = f"{article.title} — {section.title}" if section.title else article.title
        url = f"{article.url}#{section.anchor}" if section.anchor else article.url
        for part, text in enumerate(split_text(section.text, max_words)):
            chunks.append(
                Chunk(
                    id=chunk_id(article, section, part),
                    lang=article.lang,
                    slug=article.slug,
                    article_title=article.title,
                    category=article.category,
                    section_index=index,
                    section_anchor=section.anchor,
                    section_title=section.title,
                    part=part,
                    text=text,
                    embed_text=f"{header}\n\n{text}",
                    url=url,
                    n_words=_word_count(text),
                )
            )
    return chunks


def chunk_corpus(articles: Iterable[Article], max_words: int = DEFAULT_MAX_WORDS) -> list[Chunk]:
    """Chunks of many articles, in the order given."""
    return [chunk for article in articles for chunk in chunk_article(article, max_words)]
