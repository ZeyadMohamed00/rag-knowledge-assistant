import io

from fastapi.testclient import TestClient

from app.embed import hash_embed
from app.ingest import chunk_page
from app.main import app

c = TestClient(app)
H = {"X-Client-Id": "testclient-0001"}


def test_embedding_is_unit_and_similarity_orders():
    a, b, z = (
        hash_embed("password hashing with bcrypt"),
        hash_embed("how to hash passwords with bcrypt"),
        hash_embed("football match score"),
    )
    dot = lambda u, v: sum(x * y for x, y in zip(u, v))
    assert abs(dot(a, a) - 1) < 1e-6 and dot(a, b) > dot(a, z)


def test_chunking_keeps_sentences_and_overlap():
    t = " ".join(f"Sentence number {i} is here." for i in range(40))
    ch = chunk_page(t, size=200)
    assert len(ch) > 3 and all(len(x) < 400 for x in ch)
    assert ch[0].split(". ")[-1] in ch[1] or ch[0][-20:] in ch[1]


def test_requires_client_id():
    assert c.get("/documents").status_code == 400


def test_seed_search_and_page_citation():
    assert c.post("/demo/seed", headers=H).json()["seeded"] is True
    assert c.post("/demo/seed", headers=H).json()["seeded"] is False
    docs = c.get("/documents", headers=H).json()
    assert docs[0]["pages"] == 11
    chat = c.post("/chats", headers=H).json()
    r = c.post(
        f"/chats/{chat['id']}/ask",
        headers=H,
        json={"question": "What status code does FastAPI return when validation fails?"},
    ).json()
    assert (
        "422" in r["answer"]
        and r["citations"]
        and r["citations"][0]["page"] == 3
        and r["mode"].startswith("extractive")
    )
    saved = c.get(f"/chats/{chat['id']}", headers=H).json()
    assert [m["role"] for m in saved["messages"]] == ["user", "assistant"]
    assert any(ch["id"] == chat["id"] for ch in c.get("/chats", headers=H).json())


def test_isolation_between_clients():
    other = {"X-Client-Id": "otherclient-0002"}
    assert c.get("/documents", headers=other).json() == []
    chat = c.post("/chats", headers=H).json()
    assert c.get(f"/chats/{chat['id']}", headers=other).status_code == 404


def test_upload_txt_docx_and_reject_bad():
    H2 = {"X-Client-Id": "uploader-0003"}
    r = c.post(
        "/documents",
        headers=H2,
        files={
            "file": (
                "n.txt",
                b"Kubernetes schedules pods onto nodes. A pod is the smallest deployable unit.",
            )
        },
    )
    assert r.status_code == 201
    from docx import Document

    buf = io.BytesIO()
    d = Document()
    d.add_paragraph("Redis is an in-memory key value store used for caching.")
    d.save(buf)
    assert (
        c.post("/documents", headers=H2, files={"file": ("n.docx", buf.getvalue())}).status_code
        == 201
    )
    hits = c.post("/search", headers=H2, json={"question": "what is a pod"}).json()
    assert hits[0]["document"] == "n.txt"
    assert c.post("/documents", headers=H2, files={"file": ("x.exe", b"zz")}).status_code == 415
    assert (
        c.post(
            "/documents", headers=H2, files={"file": ("big.txt", b"a" * (4 * 1024 * 1024 + 1))}
        ).status_code
        == 413
    )


def test_answer_has_no_duplicate_sentences():
    H3 = {"X-Client-Id": "dedupe-0004"}
    c.post("/demo/seed", headers=H3)
    chat = c.post("/chats", headers=H3).json()
    a = c.post(
        f"/chats/{chat['id']}/ask", headers=H3, json={"question": "Why are JWTs hard to revoke?"}
    ).json()["answer"]
    sents = [s for s in a.replace("[1]", "").split(". ") if s.strip()]
    assert len(sents) == len(set(sents))


def _up(name, data, headers=H):
    return c.post("/documents", files={"file": (name, io.BytesIO(data))}, headers=headers)


def test_empty_and_whitespace_upload_rejected():
    assert _up("empty.txt", b"").status_code == 422
    assert _up("blank.txt", b"   \n\n  ").status_code == 422


def test_oversized_upload_rejected_with_413():
    assert _up("big.txt", b"a " * (2 * 1024 * 1024 + 10)).status_code == 413


def test_corrupt_pdf_is_a_clean_error_not_a_500():
    r = _up("broken.pdf", b"%PDF-1.4 this is not really a pdf")
    assert r.status_code in (415, 422)


def test_other_clients_cannot_delete_or_see_my_document():
    mine, other = {"X-Client-Id": "owner-client-001"}, {"X-Client-Id": "other-client-002"}
    r = _up("private.txt", b"The vault code policy is rotated every quarter by the security team.", mine)
    assert r.status_code == 201
    did = r.json()["id"]
    assert c.delete(f"/documents/{did}", headers=other).status_code == 404
    assert all(d["id"] != did for d in c.get("/documents", headers=other).json())
    hits = c.post("/search", json={"question": "vault code policy"}, headers=other).json()
    assert "private.txt" not in str(hits)
    assert c.delete(f"/documents/{did}", headers=mine).status_code == 204
