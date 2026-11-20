"""Load the corpus into PostgreSQL and embed it: `python -m sextant.retrieval.index`.

Usage: `uv run python -m sextant.retrieval.index --models minilm,e5-large`

Prints the embedding throughput of each model on this machine, which the
benchmark report quotes alongside query latencies.
"""

from __future__ import annotations

import argparse
import sys
import time

from sextant.retrieval.base import load_chunks
from sextant.retrieval.factory import RetrievalContext


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", default="minilm", help="comma-separated embedding models")
    args = parser.parse_args(argv)

    context = RetrievalContext(load_chunks())
    context.store.init_schema()
    changed = context.store.load_chunks(context.chunks)
    state = "loaded" if changed else "unchanged"
    print(f"{state}: {len(context.chunks)} chunks")

    for key in [m.strip() for m in args.models.split(",") if m.strip()]:
        embedder = context.embedder(key)
        started = time.perf_counter()
        vectors = embedder.embed_passages([chunk.embed_text for chunk in context.chunks])
        elapsed = time.perf_counter() - started
        context.store.load_embeddings(key, context.chunks, vectors)
        rate = len(context.chunks) / elapsed
        print(f"{key}: dim {embedder.dim}, {elapsed:.1f} s ({rate:.0f} chunks/s), HNSW index built")
    return 0


if __name__ == "__main__":
    sys.exit(main())
