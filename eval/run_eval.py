"""Retrieval + answer evaluation on the 50-question reference set (eval/questions.json).
Runs against a real PostgreSQL+pgvector (embedded via pgserver), with the default `hash` embedder and extractive answers.
Metrics:
  Retrieval Recall@k : gold page (the topic page for the question) appears in the top-k retrieved chunks.
  MRR                : mean reciprocal rank of the first chunk from the gold page.
  Faithfulness (proxy): share of answer sentences whose content words are >=80% present in the retrieved context.
                        LEXICAL PROXY, not an LLM judge; an extractive answerer scores high by construction.
Caveat: questions were written by the project author from the same documents, so they are not an independent benchmark."""

import glob
import json
import os
import re
import sys
import tempfile

import pgserver

srv = pgserver.get_server(tempfile.mkdtemp())
os.environ["DATABASE_URL"] = srv.get_uri().replace("postgresql://", "postgresql+psycopg2://", 1)
os.environ.pop("OPENAI_API_KEY", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import db as D
from app.embed import _stem, _tok
from app.main import SAMPLE, add_document
from app.rag import answer, retrieve

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
names = [os.path.basename(f)[:-4] for f in sorted(glob.glob(f"{root}/data/docs/*.txt"))]
qs = json.load(open(f"{root}/eval/questions.json"))
D.init()
with D.Session() as db:
    add_document(db, "evalclient", "engineering-handbook.pdf", SAMPLE.read_bytes())
    ks = (1, 3, 5)
    hit = {k: 0 for k in ks}
    rr = 0
    faith = []
    miss = []
    for x in qs:
        gold = names.index(x["doc"]) + 1
        hits = retrieve(db, "evalclient", x["q"], 5)
        pages = [h["page"] for h in hits]
        for k in ks:
            hit[k] += gold in pages[:k]
        if gold in pages:
            rr += 1 / (pages.index(gold) + 1)
        else:
            miss.append(x["q"])
        text, cites, mode = answer(x["q"], hits)
        ctx = {_stem(w) for h in hits for w in _tok(h["text"])}
        sents = [
            s for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\s*\[\d+\]", "", text)) if s.strip()
        ]
        for s in sents:
            ws = [_stem(w) for w in _tok(s)]
            faith.append(sum(w in ctx for w in ws) / (len(ws) or 1) >= 0.8)
    n = len(qs)
    res = {
        "questions": n,
        **{f"recall@{k}": round(hit[k] / n, 3) for k in ks},
        "mrr": round(rr / n, 3),
        "faithfulness_proxy": round(sum(faith) / len(faith), 3),
        "embedder": "hash (lexical, 384d)",
        "answerer": "extractive",
        "missed_at_5": miss,
    }
    json.dump(res, open(f"{root}/eval/results.json", "w"), indent=1)
    print(json.dumps(res, indent=1))
