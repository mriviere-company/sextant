r"""Okapi BM25, written out rather than imported.

Why not PostgreSQL's full-text ranking alone: `ts_rank` and `ts_rank_cd` score
term frequency and proximity but have no inverse document frequency, so a
common word weighs as much as a rare one. BM25 is the standard lexical
baseline in information retrieval, and ~2 300 chunks fit comfortably in
memory. PostgreSQL full text stays in the benchmark as its own strategy
(`pg_fts.py`) so the difference is measured, not asserted.

Tokens are lower-cased `\\w+` words reduced by the Snowball stemmer of the
query's language (all six wiki languages have one). No stopword list: BM25's
IDF already pushes very common words towards zero.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from functools import cache

import snowballstemmer

from sextant.models import Chunk, Lang
from sextant.retrieval.base import Hit

_WORD = re.compile(r"\w+", re.UNICODE)
_STEMMERS: dict[Lang, str] = {
    "fr": "french",
    "en": "english",
    "de": "german",
    "es": "spanish",
    "pt": "portuguese",
    "ru": "russian",
}


@cache
def _stemmer(lang: Lang) -> snowballstemmer.stemmer:
    return snowballstemmer.stemmer(_STEMMERS[lang])


def tokenize(text: str, lang: Lang) -> list[str]:
    """Lower-cased, stemmed word tokens."""
    words = _WORD.findall(text.lower())
    return list(_stemmer(lang).stemWords(words))


class _LanguageIndex:
    def __init__(self, chunks: Sequence[Chunk], k1: float, b: float) -> None:
        self.ids = [chunk.id for chunk in chunks]
        self.term_freqs = [Counter(tokenize(chunk.embed_text, chunk.lang)) for chunk in chunks]
        self.lengths = [sum(tf.values()) for tf in self.term_freqs]
        self.avg_length = sum(self.lengths) / max(len(self.lengths), 1)
        doc_freq: Counter[str] = Counter()
        for tf in self.term_freqs:
            doc_freq.update(tf.keys())
        n = len(chunks)
        # Lucene's IDF: the `+ 1` inside the log keeps the weight positive even for a
        # term found in more than half the chunks (classic Robertson IDF goes negative).
        self.idf = {
            term: math.log(1 + (n - df + 0.5) / (df + 0.5)) for term, df in doc_freq.items()
        }
        self.k1, self.b = k1, b

    def score(self, query_terms: list[str]) -> list[float]:
        scores = [0.0] * len(self.ids)
        for term in set(query_terms):
            idf = self.idf.get(term)
            if not idf:
                continue
            for doc, tf in enumerate(self.term_freqs):
                freq = tf.get(term)
                if not freq:
                    continue
                norm = self.k1 * (1 - self.b + self.b * self.lengths[doc] / self.avg_length)
                scores[doc] += idf * freq * (self.k1 + 1) / (freq + norm)
        return scores


class BM25Retriever:
    """BM25 over each language's chunks (k1=1.2, b=0.75, the usual defaults)."""

    def __init__(self, chunks: Sequence[Chunk], k1: float = 1.2, b: float = 0.75) -> None:
        by_lang: dict[Lang, list[Chunk]] = {}
        for chunk in chunks:
            by_lang.setdefault(chunk.lang, []).append(chunk)
        self._indexes = {lang: _LanguageIndex(items, k1, b) for lang, items in by_lang.items()}

    @property
    def name(self) -> str:
        """Identifier in reports."""
        return "bm25"

    def search(self, query: str, lang: Lang, k: int) -> list[Hit]:
        """Top-k chunks of `lang` by BM25 score; chunks scoring zero are never returned."""
        index = self._indexes.get(lang)
        if index is None:
            return []
        scores = index.score(tokenize(query, lang))
        ranked = sorted(range(len(scores)), key=lambda doc: (-scores[doc], index.ids[doc]))
        return [
            Hit(chunk_id=index.ids[doc], score=scores[doc]) for doc in ranked[:k] if scores[doc] > 0
        ]
