"""Measures retrieval quality on eval/questions.json. A hit means a retrieved chunk comes from the
expected document. Prints hit@1, hit@3, MRR for each retrieval mode. Numbers come from running this script."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rag.store import load_chunks
from rag.retrieval import Retriever

root = Path(__file__).resolve().parent.parent
questions = json.loads((root / "eval" / "questions.json").read_text())
chunks = load_chunks(root / "data" / "docs")
print(f"{len(chunks)} chunks, {len(questions)} questions")
print(f"{'mode':8} hit@1  hit@3  MRR")
for mode in Retriever.MODES:
    r = Retriever(chunks, mode)
    h1 = h3 = rr = 0
    for item in questions:
        docs = [c.doc for c, _ in r.search(item["q"], 5)]
        if docs[:1] == [item["doc"]]:
            h1 += 1
        if item["doc"] in docs[:3]:
            h3 += 1
        if item["doc"] in docs:
            rr += 1 / (docs.index(item["doc"]) + 1)
    n = len(questions)
    print(f"{mode:8} {h1/n:.2f}   {h3/n:.2f}   {rr/n:.3f}")
