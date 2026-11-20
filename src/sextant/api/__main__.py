"""`python -m sextant.api`: serve on 127.0.0.1:8000 (put a reverse proxy in front)."""

from __future__ import annotations

import uvicorn

from sextant.api.app import create_app
from sextant.api.logs import configure_logging

HOST = "127.0.0.1"
PORT = 8000


def main() -> None:
    """Start the server with JSON logs."""
    configure_logging()
    uvicorn.run(create_app(), host=HOST, port=PORT, access_log=False, log_config=None)


if __name__ == "__main__":
    main()
