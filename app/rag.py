import json, os, re
from sqlalchemy import select
from .db import Chunk, Document
from .embed import embed, _tok, _stem


def retrieve(db, client_id: str, question: str, k: int = 5):
    qv = embed([question])[0]
    dist = Chunk.embedding.cosine_distance(qv)
    rows = db.execute(select(Chunk, Document.filename, dist.label("d")).join(Document, Document.id == Chunk.document_id)
                      .where(Chunk.client_id == client_id).order_by(dist).limit(k)).all()
    return [{"chunk_id": c.id, "document": fn, "page": c.page, "text": c.text, "score": round(1 - d, 4)} for c, fn, d in rows]


def _sentences(t):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", t) if s.strip()]


def extractive_answer(question: str, hits: list[dict]) -> tuple[str, list[dict]]:
    """No-LLM answer: pick the sentences most lexically similar to the question from the retrieved chunks."""
    q = {_stem(w) for w in _tok(question)}
    cands = []
    for rank, h in enumerate(hits[:3]):
        for s in _sentences(h["text"]):
            sw = {_stem(w) for w in _tok(s)}
            cands.append((len(q & sw) / (len(q) or 1) - 0.02 * rank, s, h))
    cands.sort(key=lambda x: -x[0])
    seen, uniq = set(), []
    for c in cands:  # overlapping chunks repeat sentences
        if c[1] not in seen:
            seen.add(c[1]); uniq.append(c)
    cands = uniq
    chosen = [c for c in cands[:2] if c[0] > 0 and c[0] >= 0.6 * cands[0][0]]
    if not chosen:
        return "I could not find this in your documents.", []
    cites, parts = [], []
    for _, s, h in chosen:
        key = (h["document"], h["page"])
        if key not in [(c["document"], c["page"]) for c in cites]:
            cites.append({"document": h["document"], "page": h["page"], "snippet": h["text"][:200]})
        n = [(c["document"], c["page"]) for c in cites].index(key) + 1
        parts.append(f"{s} [{n}]")
    return " ".join(parts), cites


def llm_answer(question: str, hits: list[dict]) -> tuple[str, list[dict]]:
    import httpx
    ctx = "\n\n".join(f"[{i+1}] ({h['document']}, page {h['page']}) {h['text']}" for i, h in enumerate(hits))
    r = httpx.post("https://api.openai.com/v1/chat/completions", timeout=60,
                   headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                   json={"model": os.getenv("LLM_MODEL", "gpt-4o-mini"), "temperature": 0,
                         "messages": [{"role": "system", "content": "Answer ONLY from the numbered context. Cite sources like [1]. If the context does not contain the answer, say you cannot find it."},
                                      {"role": "user", "content": f"Context:\n{ctx}\n\nQuestion: {question}"}]})
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    used = sorted({int(n) for n in re.findall(r"\[(\d+)\]", text) if 0 < int(n) <= len(hits)})
    cites = [{"document": hits[i - 1]["document"], "page": hits[i - 1]["page"], "snippet": hits[i - 1]["text"][:200], "n": i} for i in used]
    return text, cites


def answer(question: str, hits: list[dict]):
    if os.getenv("OPENAI_API_KEY") and os.getenv("LLM_PROVIDER", "openai") == "openai":
        return (*llm_answer(question, hits), "llm")
    return (*extractive_answer(question, hits), "extractive (no LLM key configured)")
