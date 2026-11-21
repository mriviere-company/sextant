"""Load the corpus into PostgreSQL and embed it: `python -m sextant.retrieval.index`.

Usage: `uv run python -m sextant.retrieval.index --models minilm,e5-large [--full]`

By default the update is incremental: chunks are synced row by row and only the chunks
that are new or whose text changed are embedded again, so a wiki edit of one article costs
seconds, not the 40 minutes of embedding the whole corpus with e5-large. A model never
indexed before is embedded in full. `--full` rebuilds everything, as the benchmarks did.
Either way, every model's table is checked to cover exactly the corpus at the end.

Prints the embedding throughput of each model on this machine, which the benchmark report
quotes alongside query latencies.
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
    parser.add_argument("--full", action="store_true", help="rebuild every table from scratch")
    args = parser.parse_args(argv)

    context = RetrievalContext(load_chunks())
    store = context.store
    store.init_schema()
    expected = {chunk.id for chunk in context.chunks}
    if args.full:
        changed = store.load_chunks(context.chunks)
        print(f"{'loaded' if changed else 'unchanged'}: {len(context.chunks)} chunks")
        to_embed: frozenset[str] | None = None
    else:
        sync = store.sync_chunks(context.chunks)
        print(
            f"synced {len(context.chunks)} chunks: {len(sync.added)} added, "
            f"{len(sync.changed)} changed, {len(sync.removed)} removed"
        )
        to_embed = sync.to_embed

    for key in [m.strip() for m in args.models.split(",") if m.strip()]:
        embedder = context.embedder(key)
        present = None if args.full else store.embedded_ids(key)
        if present is None:
            targets = context.chunks
        else:
            missing = expected - present
            targets = [c for c in context.chunks if c.id in missing]
            if not targets:  # nothing changed: embedding an empty batch would fail
                print(f"{key}: up to date, nothing to embed")
                if store.embedded_ids(key) != expected:
                    raise SystemExit(f"{key}: the embedding table does not cover the corpus")
                continue
        started = time.perf_counter()
        vectors = embedder.embed_passages([chunk.embed_text for chunk in targets])
        elapsed = time.perf_counter() - started
        if present is None:
            store.load_embeddings(key, targets, vectors)
            rate = len(targets) / elapsed if elapsed else 0.0
            print(f"{key}: dim {embedder.dim}, {elapsed:.1f} s ({rate:.0f} chunks/s), full")
        else:
            store.add_embeddings(key, targets, vectors)
            print(f"{key}: {len(targets)} chunks embedded in {elapsed:.1f} s, incremental")
        if store.embedded_ids(key) != expected:
            raise SystemExit(f"{key}: the embedding table does not cover the corpus exactly")
    if to_embed is not None and to_embed - expected:
        raise SystemExit("synced chunks missing from the corpus")
    return 0


if __name__ == "__main__":
    sys.exit(main())
