from sextant.models import Chunk
from sextant.retrieval.base import Hit
from sextant.retrieval.hybrid import HybridRetriever, rrf_fuse
from sextant.retrieval.lexical import BM25Retriever, tokenize


def _chunk(cid: str, text: str, lang: str = "fr") -> Chunk:
    return Chunk(
        id=cid,
        lang=lang,  # type: ignore[arg-type]
        slug=cid.split(":", 1)[1].split("#", 1)[0],
        article_title="T",
        category="c",
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
    _chunk("fr:fleet#a:0", "Construire une flotte de vaisseaux au chantier spatial"),
    _chunk("fr:market#a:0", "Vendre des ressources au marché contre des bitcoins"),
    _chunk("fr:prison#a:0", "Le héros capturé peut s'évader de la prison"),
    _chunk("en:fleet#a:0", "Build a fleet of ships at the shipyard", "en"),
]


def test_tokenize_stems_per_language() -> None:
    assert tokenize("Les flottes", "fr") == ["le", "flott"]
    assert tokenize("la flotte", "fr")[-1] == "flott"
    assert tokenize("Fleets", "en") == ["fleet"]
    assert tokenize("флоты", "ru") == ["флот"]


def test_bm25_ranks_matching_chunk_first_and_stays_in_language() -> None:
    bm25 = BM25Retriever(CHUNKS)
    hits = bm25.search("comment construire des flottes ?", "fr", 3)
    assert hits[0].chunk_id == "fr:fleet#a:0"
    assert all(hit.chunk_id.startswith("fr:") for hit in hits)


def test_bm25_returns_nothing_without_overlap() -> None:
    assert BM25Retriever(CHUNKS).search("xylophone", "fr", 5) == []
    assert BM25Retriever(CHUNKS).search("flotte", "ru", 5) == []


def test_rare_terms_outweigh_common_ones() -> None:
    chunks = [
        _chunk("fr:a#a:0", "flotte flotte flotte"),
        _chunk("fr:b#a:0", "flotte prison"),
        _chunk("fr:c#a:0", "flotte"),
    ]
    hits = BM25Retriever(chunks).search("flotte prison", "fr", 3)
    assert hits[0].chunk_id == "fr:b#a:0"


def test_rrf_rewards_agreement_between_lists() -> None:
    fused = rrf_fuse(
        [
            [Hit(chunk_id="x", score=9), Hit(chunk_id="y", score=8)],
            [Hit(chunk_id="y", score=0.9), Hit(chunk_id="z", score=0.8)],
        ]
    )
    assert [h.chunk_id for h in fused] == ["y", "x", "z"]
    assert fused[0].score == 1 / 62 + 1 / 61


class _Fixed:
    def __init__(self, name: str, ids: list[str]) -> None:
        self._name, self._ids = name, ids

    @property
    def name(self) -> str:
        return self._name

    def search(self, query: str, lang: str, k: int) -> list[Hit]:
        return [Hit(chunk_id=i, score=1.0) for i in self._ids[:k]]


def test_hybrid_name_and_cut() -> None:
    hybrid = HybridRetriever([_Fixed("a", ["1", "2"]), _Fixed("b", ["2", "3"])])
    assert hybrid.name == "hybrid(a+b)"
    assert [h.chunk_id for h in hybrid.search("q", "fr", 2)] == ["2", "1"]
