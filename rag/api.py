import os
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel
from .store import build
from .generate import answer

DOCS = Path(os.getenv("DOCS_DIR", Path(__file__).resolve().parent.parent / "data" / "docs"))
app = FastAPI(title="RAG Knowledge Assistant")
retriever = build(DOCS)


class Ask(BaseModel):
    question: str
    k: int = 4


@app.get("/health")
def health():
    return {"chunks": len(retriever.chunks)}


@app.post("/ask")
def ask(body: Ask):
    hits = retriever.search(body.question, body.k)
    return {
        "answer": answer(body.question, hits),
        "sources": [{"id": c.id, "score": round(s, 3), "text": c.text} for c, s in hits],
    }
