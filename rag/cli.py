import sys
from .store import build
from .generate import answer

if __name__ == "__main__":
    r = build(sys.argv[1] if len(sys.argv) > 1 else "data/docs")
    q = " ".join(sys.argv[2:]) or input("Question: ")
    hits = r.search(q)
    print(answer(q, hits))
    for c, s in hits:
        print(f"  - {c.id} ({s:.2f})")
