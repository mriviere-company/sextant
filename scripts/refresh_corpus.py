"""Refresh the wiki snapshot from a local checkout of the game.

Usage: uv run python scripts/refresh_corpus.py --from /path/to/Area-Reborn

Copies the six `translations/wiki.<lang>.yaml` files into `corpus/wiki/` and
records the source commit in `corpus/wiki/SOURCE_REVISION`. Run `make ingest`
afterwards and commit both the snapshot and `corpus/processed/stats.json`.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

LANGS = ("fr", "en", "de", "es", "pt", "ru")
DEST = Path(__file__).resolve().parents[1] / "corpus" / "wiki"


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="source", type=Path, required=True)
    args = parser.parse_args()

    translations = args.source / "translations"
    files = [translations / f"wiki.{lang}.yaml" for lang in LANGS]
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        print(f"missing files: {missing}", file=sys.stderr)
        return 1

    for path in files:
        shutil.copy2(path, DEST / path.name)
    revision = subprocess.run(
        ["git", "-C", str(args.source), "log", "-1", "--format=%H %cs", "--", "translations"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (DEST / "SOURCE_REVISION").write_text(revision + "\n", encoding="utf-8")
    print(f"snapshot refreshed at {revision}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
