from pathlib import Path
import pytest
from rag.chunking import chunk_text, tokenize
from rag.retrieval import BM25, Retriever
from rag.store import load_chunks
from rag.generate import answer, NO_ANSWER

DOCS = Path(__file__).resolve().parent.parent / "data" / "docs"


def test_chunk_overlap_and_coverage():
    text = " ".join(f"w{i}" for i in range(100))
    cs = chunk_text("d", text, size=40, overlap=10)
    assert cs[0].text.split()[-10:] == cs[1].text.split()[:10]
    assert "w99" in cs[-1].text and len(cs) == 3


def test_chunk_validation_and_empty():
    assert chunk_text("d", "") == []
    with pytest.raises(ValueError):
        chunk_text("d", "a b c", size=5, overlap=5)


def test_tokenize_drops_stopwords():
    assert tokenize("The Cat is on the mat") == ["cat", "mat"]


def test_bm25_prefers_rare_matching_term():
    cs = chunk_text("a", "apples oranges bananas") + chunk_text("b", "quantum physics lecture")
    s = BM25(cs).scores("quantum")
    assert s[1] > s[0] == 0


@pytest.mark.parametrize("mode", Retriever.MODES)
def test_each_mode_finds_obvious_doc(mode):
    r = Retriever(load_chunks(DOCS), mode)
    hits = r.search("how to prevent SQL injection", 3)
    assert hits[0][0].doc == "sql-databases"


def test_unknown_mode():
    with pytest.raises(ValueError):
        Retriever([], "nope")


def test_no_hits_says_dont_know():
    r = Retriever(load_chunks(DOCS))
    hits = r.search("zzzz qqqq", 3)
    assert answer("zzzz qqqq", hits) == NO_ANSWER


def test_answer_has_citation():
    r = Retriever(load_chunks(DOCS))
    q = "What does a foreign key do?"
    out = answer(q, r.search(q, 3))
    assert "[sql-databases#" in out


def test_api():
    from fastapi.testclient import TestClient
    from rag.api import app
    c = TestClient(app)
    assert c.get("/health").json()["chunks"] > 10
    j = c.post("/ask", json={"question": "Why are JWTs hard to revoke?"}).json()
    assert j["sources"][0]["id"].startswith("authentication")
