"""Build the processed corpus: `python -m sextant.ingest` (or `make ingest`).

Writes `corpus/processed/chunks.jsonl` (derived, git-ignored) and
`corpus/processed/stats.json` (committed). `--check` rebuilds in memory and
fails if the committed stats no longer match the snapshot: CI uses it so the
published corpus figures can never drift from the data.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sextant.ingest.chunking import DEFAULT_MAX_WORDS, chunk_corpus
from sextant.ingest.wiki import load_corpus
from sextant.models import Article, Chunk, Lang

ROOT = Path(__file__).resolve().parents[3]
WIKI_DIR = ROOT / "corpus" / "wiki"
OUT_DIR = ROOT / "corpus" / "processed"


def corpus_stats(corpus: dict[Lang, list[Article]], chunks: list[Chunk]) -> dict[str, Any]:
    """Deterministic statistics: no timestamps, so the file only changes when the data does."""
    per_lang: dict[str, Any] = {}
    for lang, articles in corpus.items():
        lang_chunks = [chunk for chunk in chunks if chunk.lang == lang]
        per_lang[lang] = {
            "articles": len(articles),
            "sections": sum(len(article.sections) for article in articles),
            "chunks": len(lang_chunks),
            "words": sum(chunk.n_words for chunk in lang_chunks),
            "max_chunk_words": max(chunk.n_words for chunk in lang_chunks),
        }
    return {
        "max_words_per_chunk": DEFAULT_MAX_WORDS,
        "languages": per_lang,
        "total_chunks": len(chunks),
        "categories": sorted({article.category for article in corpus["fr"]}),
    }


def build() -> tuple[list[Chunk], dict[str, Any]]:
    """Load the wiki snapshot and return its chunks and statistics."""
    corpus = load_corpus(WIKI_DIR)
    chunks = chunk_corpus(article for articles in corpus.values() for article in articles)
    return chunks, corpus_stats(corpus, chunks)


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if committed stats are stale")
    args = parser.parse_args(argv)

    chunks, stats = build()
    stats_path = OUT_DIR / "stats.json"
    rendered = json.dumps(stats, indent=2, ensure_ascii=False, sort_keys=True) + "\n"

    if args.check:
        if not stats_path.exists() or stats_path.read_text(encoding="utf-8") != rendered:
            print("corpus/processed/stats.json is stale: run `make ingest`", file=sys.stderr)
            return 1
        print(f"corpus OK: {stats['total_chunks']} chunks")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "chunks.jsonl").open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(chunk.model_dump_json() + "\n")
    stats_path.write_text(rendered, encoding="utf-8")
    print(f"wrote {len(chunks)} chunks to {OUT_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
