# Corpus

## `wiki/` — source snapshot

The six translation files of the Area Universe wiki (`wiki.<lang>.yaml`), copied as is from
the game's code base. `SOURCE_REVISION` records the commit and date they come from. The same
content is public at <https://www.areauniverse.com/wiki>.

**Rights:** the wiki text is © Area Universe, all rights reserved. It is included here so
the ingestion and evaluation can be reproduced; the MIT license of this repository covers the
code, not this content.

To refresh it from a local checkout of the game:

```bash
uv run python scripts/refresh_corpus.py --from /path/to/Area-Reborn
make ingest
```

Then commit both `wiki/` and `processed/stats.json`.

## `processed/` — derived

- `chunks.jsonl` (git-ignored): one chunk per line, rebuilt by `make ingest`.
- `stats.json` (committed): articles, sections, chunks and words per language. CI rebuilds
  the corpus and fails if this file no longer matches the snapshot, so the figures published
  in the README cannot drift from the data.
