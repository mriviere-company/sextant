"""PostgreSQL integration: needs a *disposable* database with pgvector (`TEST_DATABASE_URL`).

These tests truncate tables, so they never read `DATABASE_URL` (the working
index). Skipped when no test database is reachable; CI runs them against a
pgvector service. A deterministic fake embedder keeps them independent of model downloads.
"""

import hashlib
import os
from collections.abc import Sequence

import numpy as np
import psycopg
import pytest

from sextant.models import Chunk
from sextant.retrieval.embeddings import Vectors, normalize
from sextant.retrieval.store import DenseRetriever, PgFtsRetriever, PgStore

DSN = os.environ.get("TEST_DATABASE_URL", "")


def _reachable() -> bool:
    if not DSN:
        return False
    try:
        with psycopg.connect(DSN, connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


pytestmark = pytest.mark.skipif(
    not _reachable(), reason="no PostgreSQL with pgvector (TEST_DATABASE_URL)"
)


class HashEmbedder:
    """Bag of hashed words: similar texts get similar vectors, deterministically."""

    key = "test_hash"
    dim = 64

    def _embed(self, texts: Sequence[str]) -> Vectors:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in text.lower().split():
                out[row, int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dim] += 1
        return normalize(out)

    def embed_queries(self, texts: Sequence[str]) -> Vectors:
        return self._embed(texts)

    def embed_passages(self, texts: Sequence[str]) -> Vectors:
        return self._embed(texts)


def _chunk(cid: str, text: str, lang: str) -> Chunk:
    return Chunk(
        id=cid,
        lang=lang,
        slug=cid.split(":", 1)[1].split("#", 1)[0],
        article_title="T",
        category="c",  # type: ignore[arg-type]
        section_index=0,
        section_anchor="a",
        section_title="S",
        part=0,
        text=text,
        embed_text=text,
        url="https://example.test",
        n_words=len(text.split()),
    )


CHUNKS = [
    _chunk("fr:fleet#a:0", "construire une flotte de vaisseaux", "fr"),
    _chunk("fr:market#a:0", "vendre des ressources au marché", "fr"),
    _chunk("fr:prison#a:0", "le héros peut s'évader de la prison", "fr"),
    _chunk("en:fleet#a:0", "build a fleet of ships", "en"),
    _chunk("en:market#a:0", "sell resources at the market", "en"),
]


@pytest.fixture
def store() -> PgStore:
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS emb_test_hash")
    store = PgStore(DSN)
    store.init_schema()
    return store


def test_load_chunks_is_idempotent(store: PgStore) -> None:
    store.load_chunks(CHUNKS)
    assert store.load_chunks(CHUNKS) is False


def test_dense_search_filters_language_and_matches_exact_search(store: PgStore) -> None:
    store.load_chunks(CHUNKS)
    embedder = HashEmbedder()
    store.load_embeddings(
        embedder.key, CHUNKS, embedder.embed_passages([c.embed_text for c in CHUNKS])
    )
    hits = DenseRetriever(embedder, store).search("construire une flotte", "fr", 3)
    assert hits[0].chunk_id == "fr:fleet#a:0"
    assert all(h.chunk_id.startswith("fr:") for h in hits)
    vector = embedder.embed_queries(["vendre au marché"])[0]
    approx = store.dense_search(embedder.key, vector, "fr", 3)
    exact = store.dense_search(embedder.key, vector, "fr", 3, exact=True)
    assert [h.chunk_id for h in approx] == [h.chunk_id for h in exact]


def test_full_text_search_uses_language_stemming(store: PgStore) -> None:
    store.load_chunks(CHUNKS)
    hits = PgFtsRetriever(store).search("les flottes", "fr", 3)
    assert [h.chunk_id for h in hits] == ["fr:fleet#a:0"]


def test_sync_updates_only_what_changed_and_keeps_other_vectors(store: PgStore) -> None:
    embedder = HashEmbedder()
    store.load_chunks(CHUNKS)
    store.load_embeddings(
        embedder.key, CHUNKS, embedder.embed_passages([c.embed_text for c in CHUNKS])
    )
    edited = [
        CHUNKS[0],
        _chunk("fr:market#a:0", "acheter des vaisseaux au marchand", "fr"),  # changed text
        CHUNKS[3],
        CHUNKS[4],
        _chunk("fr:faq#a:0", "jouer sur plusieurs serveurs", "fr"),  # added
    ]  # fr:prison#a:0 removed
    sync = store.sync_chunks(edited)
    assert sync.added == ("fr:faq#a:0",)
    assert sync.changed == ("fr:market#a:0",)
    assert sync.removed == ("fr:prison#a:0",)
    # vectors of removed and changed chunks are gone, the others are kept
    assert store.embedded_ids(embedder.key) == {"fr:fleet#a:0", "en:fleet#a:0", "en:market#a:0"}
    fresh = [c for c in edited if c.id in sync.to_embed]
    store.add_embeddings(
        embedder.key, fresh, embedder.embed_passages([c.embed_text for c in fresh])
    )
    assert store.embedded_ids(embedder.key) == {c.id for c in edited}
    hits = DenseRetriever(embedder, store).search("plusieurs serveurs", "fr", 1)
    assert hits[0].chunk_id == "fr:faq#a:0"
    assert store.sync_chunks(edited) == type(sync)()  # nothing left to do
    assert store.embedded_ids("never_indexed") is None


def test_index_command_is_a_no_op_when_nothing_changed(
    store: PgStore, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from sextant.retrieval import index  # noqa: PLC0415 — the command under test
    from sextant.retrieval.factory import RetrievalContext  # noqa: PLC0415

    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE chunks CASCADE")
    monkeypatch.setattr(index, "load_chunks", lambda: CHUNKS)
    monkeypatch.setattr(RetrievalContext, "embedder", lambda self, key: HashEmbedder())
    monkeypatch.setattr(index, "RetrievalContext", lambda chunks: RetrievalContext(chunks, DSN))
    assert index.main(["--models", "test_hash"]) == 0
    assert index.main(["--models", "test_hash"]) == 0  # used to crash on an empty batch
    out = capsys.readouterr().out
    assert "0 added, 0 changed, 0 removed" in out
    assert "test_hash: up to date, nothing to embed" in out
