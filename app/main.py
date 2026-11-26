import json
import os
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select

from . import db as D
from .auth import identity
from .auth import router as auth_router
from .embed import embed, provider
from .ingest import chunk_page, extract_pages
from .rag import answer, retrieve

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample-handbook.pdf"
MAX_BYTES = 4 * 1024 * 1024
MAX_DOCS_PER_CLIENT = 10


def get_db():
    with D.Session() as s:
        yield s


def client(authorization: str = Header(default=""), x_client_id: str = Header(default="")):
    return identity(authorization, x_client_id)


def add_document(db, client_id: str, filename: str, data: bytes) -> D.Document:
    if db.query(D.Document).filter_by(client_id=client_id).count() >= MAX_DOCS_PER_CLIENT:
        raise HTTPException(
            409, f"Limit of {MAX_DOCS_PER_CLIENT} documents reached; delete one first"
        )
    try:
        pages = extract_pages(filename, data)
    except ValueError as e:
        raise HTTPException(415, str(e))
    except Exception:
        raise HTTPException(422, "Could not read this file")
    pieces = [(i + 1, c) for i, p in enumerate(pages) for c in chunk_page(p)]
    if not pieces:
        raise HTTPException(
            422, "No extractable text (scanned PDFs need OCR, which is not supported)"
        )
    doc = D.Document(client_id=client_id, filename=filename, pages=len(pages))
    vecs = embed([c for _, c in pieces])
    doc.chunks = [
        D.Chunk(client_id=client_id, page=pg, text=t, embedding=v)
        for (pg, t), v in zip(pieces, vecs)
    ]
    db.add(doc)
    db.commit()
    return doc


class Ask(BaseModel):
    question: str
    k: int = 5


def create_app():
    D.init()
    app = FastAPI(title="Knowledge Assistant (RAG)", version="2.0.0")
    app.include_router(auth_router)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "embedding_provider": provider(),
            "llm": bool(os.getenv("OPENAI_API_KEY")),
        }

    @app.get("/documents")
    def docs(cid: str = Depends(client), db=Depends(get_db)):
        return [
            {"id": d.id, "filename": d.filename, "pages": d.pages, "chunks": len(d.chunks)}
            for d in db.scalars(
                select(D.Document).where(D.Document.client_id == cid).order_by(D.Document.id)
            )
        ]

    @app.post("/documents", status_code=201)
    async def upload(file: UploadFile = File(...), cid: str = Depends(client), db=Depends(get_db)):
        data = await file.read()
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "File too large (max 4 MB)")
        d = add_document(db, cid, file.filename or "upload", data)
        return {"id": d.id, "filename": d.filename, "pages": d.pages, "chunks": len(d.chunks)}

    @app.delete("/documents/{did}", status_code=204)
    def delete_doc(did: int, cid: str = Depends(client), db=Depends(get_db)):
        d = db.get(D.Document, did)
        if not d or d.client_id != cid:
            raise HTTPException(404, "Not found")
        db.delete(d)
        db.commit()

    @app.post("/demo/seed", status_code=201)
    def seed(cid: str = Depends(client), db=Depends(get_db)):
        """Load the bundled synthetic sample handbook (11 short topics, one per page) for this visitor."""
        if db.query(D.Document).filter_by(client_id=cid, filename="sample-handbook.pdf").first():
            return {"seeded": False}
        d = add_document(db, cid, "sample-handbook.pdf", SAMPLE.read_bytes())
        return {"seeded": True, "id": d.id, "pages": d.pages}

    @app.post("/search")
    def search(body: Ask, cid: str = Depends(client), db=Depends(get_db)):
        return retrieve(db, cid, body.question, body.k)

    @app.post("/chats", status_code=201)
    def new_chat(cid: str = Depends(client), db=Depends(get_db)):
        c = D.Chat(client_id=cid, title="New chat")
        db.add(c)
        db.commit()
        return {"id": c.id, "title": c.title}

    @app.get("/chats")
    def chats(cid: str = Depends(client), db=Depends(get_db)):
        return [
            {"id": c.id, "title": c.title}
            for c in db.scalars(
                select(D.Chat).where(D.Chat.client_id == cid).order_by(D.Chat.id.desc())
            )
        ]

    @app.get("/chats/{chat_id}")
    def chat(chat_id: int, cid: str = Depends(client), db=Depends(get_db)):
        c = db.get(D.Chat, chat_id)
        if not c or c.client_id != cid:
            raise HTTPException(404, "Not found")
        return {
            "id": c.id,
            "title": c.title,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "citations": json.loads(m.citations),
                    "mode": m.mode,
                }
                for m in c.messages
            ],
        }

    @app.post("/chats/{chat_id}/ask")
    def ask(chat_id: int, body: Ask, cid: str = Depends(client), db=Depends(get_db)):
        c = db.get(D.Chat, chat_id)
        if not c or c.client_id != cid:
            raise HTTPException(404, "Not found")
        if not body.question.strip() or len(body.question) > 1000:
            raise HTTPException(422, "Question must be 1-1000 characters")
        hits = retrieve(db, cid, body.question, body.k)
        text, cites, mode = answer(body.question, hits)
        if c.title == "New chat":
            c.title = body.question[:60]
        db.add_all(
            [
                D.Message(chat_id=c.id, role="user", content=body.question),
                D.Message(
                    chat_id=c.id,
                    role="assistant",
                    content=text,
                    citations=json.dumps(cites),
                    mode=mode,
                ),
            ]
        )
        db.commit()
        return {"answer": text, "citations": cites, "mode": mode}

    return app


app = create_app()
