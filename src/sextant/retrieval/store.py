"""PostgreSQL storage: chunks, full-text vectors and pgvector embeddings.

Layout:
- `chunks`: one row per chunk, with a stored `tsvector` built with the text
  search configuration of the chunk's language (`french`, `english`, …).
- `emb_<model>`: one table per embedding model (pgvector needs a fixed
  dimension per column), with an HNSW cosine index.

Every chunk of every language lives in the same table and queries filter on
`lang`. HNSW filters *after* walking the graph, so with six languages a small
`ef_search` could return fewer than `k` rows; the search raises `ef_search`
for its transaction, and `tests/test_store.py` checks HNSW against exact
search on the real model.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import psycopg
from pgvector.psycopg import register_vector
from psycopg import sql
from pydantic import BaseModel, ConfigDict

from sextant.models import Chunk, Lang
from sextant.retrieval.base import Hit
from sextant.retrieval.embeddings import Embedder, Vectors, safe_key

TS_CONFIG: dict[Lang, str] = {
    "fr": "french",
    "en": "english",
    "de": "german",
    "es": "spanish",
    "pt": "portuguese",
    "ru": "russian",
}

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS chunks (
    id            text PRIMARY KEY,
    lang          text NOT NULL,
    slug          text NOT NULL,
    section_index integer NOT NULL,
    ts_config     regconfig NOT NULL,
    embed_text    text NOT NULL,
    tsv           tsvector GENERATED ALWAYS AS (to_tsvector(ts_config, embed_text)) STORED
);
CREATE INDEX IF NOT EXISTS chunks_lang ON chunks (lang);
CREATE INDEX IF NOT EXISTS chunks_tsv ON chunks USING gin (tsv);
"""

HNSW_EF_SEARCH = 200


class ChunkSync(BaseModel):
    """What a row-by-row update of the chunks table changed."""

    model_config = ConfigDict(frozen=True)

    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()

    @property
    def to_embed(self) -> frozenset[str]:
        """Chunks whose vectors must be computed (new text)."""
        return frozenset(self.added) | frozenset(self.changed)


class PgStore:
    """Thin wrapper over one PostgreSQL database."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @contextmanager
    def connect(self) -> Iterator[psycopg.Connection[Any]]:
        """Open a connection with the pgvector type registered."""
        with psycopg.connect(self._dsn) as conn:
            register_vector(conn)
            yield conn

    def init_schema(self) -> None:
        """Create the extension, the chunks table and its indexes (idempotent)."""
        with psycopg.connect(self._dsn) as conn:
            conn.execute(SCHEMA)

    def load_chunks(self, chunks: Sequence[Chunk]) -> bool:
        """Make the chunks table match `chunks`; return whether anything changed.

        Idempotent: when the stored corpus is already identical, nothing is
        touched and the embedding tables stay valid. When it differs, the table
        is replaced and every embedding table is emptied (`CASCADE`), because
        their vectors describe the old text — re-run the indexing for each model.
        """
        rows = [
            (c.id, c.lang, c.slug, c.section_index, TS_CONFIG[c.lang], c.embed_text) for c in chunks
        ]
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, lang, slug, section_index, ts_config::text, embed_text FROM chunks"
            )
            if sorted(cur.fetchall()) == sorted(rows):
                return False
            cur.execute("TRUNCATE chunks CASCADE")
            cur.executemany(
                "INSERT INTO chunks (id, lang, slug, section_index, ts_config, embed_text) "
                "VALUES (%s, %s, %s, %s, %s::regconfig, %s)",
                rows,
            )
        return True

    def sync_chunks(self, chunks: Sequence[Chunk]) -> ChunkSync:
        """Make the chunks table match `chunks` row by row, keeping unchanged chunks' vectors.

        A wiki edit touches a few chunks; `load_chunks` would empty every embedding table.
        Here removed and changed chunks lose their row and their vectors in every embedding
        table, new and changed ones are inserted, and the rest is left untouched: only
        `ChunkSync.to_embed` needs embedding again (`index --incremental`).
        """
        rows = {
            c.id: (c.id, c.lang, c.slug, c.section_index, TS_CONFIG[c.lang], c.embed_text)
            for c in chunks
        }
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, lang, slug, section_index, ts_config::text, embed_text FROM chunks"
            )
            stored = {row[0]: tuple(row) for row in cur.fetchall()}
            removed = sorted(set(stored) - set(rows))
            added = sorted(set(rows) - set(stored))
            changed = sorted(i for i in set(rows) & set(stored) if rows[i] != stored[i])
            gone = removed + changed
            if gone:
                for table in self._embedding_tables(cur):
                    cur.execute(
                        sql.SQL("DELETE FROM {} WHERE chunk_id = ANY(%s)").format(
                            sql.Identifier(table)
                        ),
                        (gone,),
                    )
                cur.execute("DELETE FROM chunks WHERE id = ANY(%s)", (gone,))
            fresh = added + changed
            if fresh:
                cur.executemany(
                    "INSERT INTO chunks (id, lang, slug, section_index, ts_config, embed_text) "
                    "VALUES (%s, %s, %s, %s, %s::regconfig, %s)",
                    [rows[i] for i in fresh],
                )
        return ChunkSync(added=tuple(added), removed=tuple(removed), changed=tuple(changed))

    @staticmethod
    def _embedding_tables(cur: psycopg.Cursor[Any]) -> list[str]:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name LIKE 'emb\\_%'"
        )
        return [row[0] for row in cur.fetchall()]

    def embedded_ids(self, model_key: str) -> set[str] | None:
        """Chunk ids that have a vector for this model, or None if it was never indexed."""
        with self.connect() as conn, conn.cursor() as cur:
            if f"emb_{safe_key(model_key)}" not in self._embedding_tables(cur):
                return None
            cur.execute(sql.SQL("SELECT chunk_id FROM {}").format(self._table(model_key)))
            return {row[0] for row in cur.fetchall()}

    def add_embeddings(self, model_key: str, chunks: Sequence[Chunk], vectors: Vectors) -> None:
        """Insert vectors into a model's existing table (its HNSW index updates itself)."""
        if len(chunks) != len(vectors):
            raise ValueError("one vector per chunk expected")
        with self.connect() as conn, conn.cursor() as cur:
            cur.executemany(
                sql.SQL("INSERT INTO {} (chunk_id, lang, embedding) VALUES (%s, %s, %s)").format(
                    self._table(model_key)
                ),
                [(c.id, c.lang, v) for c, v in zip(chunks, vectors, strict=True)],
            )

    @staticmethod
    def _table(model_key: str) -> sql.Identifier:
        return sql.Identifier(f"emb_{safe_key(model_key)}")

    def load_embeddings(self, model_key: str, chunks: Sequence[Chunk], vectors: Vectors) -> None:
        """Create (or replace) the embedding table of one model, then build its HNSW index."""
        if len(chunks) != len(vectors):
            raise ValueError("one vector per chunk expected")
        table, dim = self._table(model_key), int(vectors.shape[1])
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(table))
            cur.execute(
                sql.SQL(
                    "CREATE TABLE {} (chunk_id text PRIMARY KEY REFERENCES chunks(id), "
                    "lang text NOT NULL, embedding vector({}) NOT NULL)"
                ).format(table, sql.Literal(dim))
            )
            cur.executemany(
                sql.SQL("INSERT INTO {} (chunk_id, lang, embedding) VALUES (%s, %s, %s)").format(
                    table
                ),
                [(c.id, c.lang, v) for c, v in zip(chunks, vectors, strict=True)],
            )
            cur.execute(
                sql.SQL("CREATE INDEX ON {} USING hnsw (embedding vector_cosine_ops)").format(table)
            )

    def dense_search(
        self, model_key: str, vector: Vectors, lang: Lang, k: int, *, exact: bool = False
    ) -> list[Hit]:
        """Cosine nearest neighbours in one language (HNSW unless `exact`)."""
        table = self._table(model_key)
        query = sql.SQL(
            "SELECT chunk_id, 1 - (embedding <=> %(v)s) AS score FROM {} "
            "WHERE lang = %(lang)s ORDER BY embedding <=> %(v)s, chunk_id LIMIT %(k)s"
        ).format(table)
        with self.connect() as conn, conn.transaction(), conn.cursor() as cur:
            if exact:
                cur.execute("SET LOCAL enable_indexscan = off")
            else:
                cur.execute(
                    sql.SQL("SET LOCAL hnsw.ef_search = {}").format(sql.Literal(HNSW_EF_SEARCH))
                )
            cur.execute(query, {"v": vector.reshape(-1), "lang": lang, "k": k})
            return [Hit(chunk_id=row[0], score=float(row[1])) for row in cur.fetchall()]

    def fts_search(self, query: str, lang: Lang, k: int) -> list[Hit]:
        """PostgreSQL full text, any query word (OR), ranked by `ts_rank_cd`.

        `plainto_tsquery` ANDs every word, which almost never matches a
        natural-language question; replacing `&` with `|` makes it an OR query.
        """
        cfg = TS_CONFIG[lang]
        statement = (
            "WITH q AS (SELECT to_tsquery(%(cfg)s::regconfig, "
            "replace(plainto_tsquery(%(cfg)s::regconfig, %(q)s)::text, '&', '|')) AS query) "
            "SELECT id, ts_rank_cd(tsv, q.query) AS score FROM chunks, q "
            "WHERE lang = %(lang)s AND tsv @@ q.query ORDER BY score DESC, id LIMIT %(k)s"
        )
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(statement, {"cfg": cfg, "q": query, "lang": lang, "k": k})
            return [Hit(chunk_id=row[0], score=float(row[1])) for row in cur.fetchall()]


class DenseRetriever:
    """Embed the query, search the model's pgvector table."""

    def __init__(self, embedder: Embedder, store: PgStore) -> None:
        self._embedder = embedder
        self._store = store

    @property
    def name(self) -> str:
        """Identifier in reports."""
        return f"dense:{self._embedder.key}"

    def search(self, query: str, lang: Lang, k: int) -> list[Hit]:
        """Top-k by cosine similarity."""
        vector = self._embedder.embed_queries([query])[0]
        return self._store.dense_search(self._embedder.key, vector, lang, k)


class PgFtsRetriever:
    """PostgreSQL full-text search as a retrieval strategy."""

    def __init__(self, store: PgStore) -> None:
        self._store = store

    @property
    def name(self) -> str:
        """Identifier in reports."""
        return "pg_fts"

    def search(self, query: str, lang: Lang, k: int) -> list[Hit]:
        """Top-k by `ts_rank_cd`."""
        return self._store.fts_search(query, lang, k)
