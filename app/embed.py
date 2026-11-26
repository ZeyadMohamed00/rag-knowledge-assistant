"""Embeddings.

Default provider `hash`: signed feature hashing of word unigrams+bigrams into 384 dims, L2-normalised.
It needs no model download and no API key, so it runs anywhere (including a Vercel function), but it is a
LEXICAL embedding: it matches shared words, not paraphrases. Set EMBEDDING_PROVIDER=openai (plus OPENAI_API_KEY)
for semantic embeddings (text-embedding-3-small, truncated to 384 dims via the `dimensions` parameter).
Never mix providers inside one database: vectors from different providers are not comparable.
"""

import hashlib
import os
import re

import numpy as np

DIM = 384
STOP = set(
    "a an the of to in on for and or is are was were be by with as at it its this that from how what why which does do can i you should".split()
)


def _tok(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP]


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    return w


def hash_embed(text: str) -> list[float]:
    v = np.zeros(DIM, dtype=np.float64)
    words = [_stem(w) for w in _tok(text)]
    feats = words + [a + "_" + b for a, b in zip(words, words[1:])]
    for f in feats:
        h = int.from_bytes(hashlib.md5(f.encode()).digest()[:8], "little")
        v[h % DIM] += 1.0 if (h >> 63) & 1 else -1.0
    n = np.linalg.norm(v)
    return (v / n).tolist() if n else v.tolist()


def provider() -> str:
    return os.getenv("EMBEDDING_PROVIDER", "hash")


def embed(texts: list[str]) -> list[list[float]]:
    if provider() == "openai":
        import httpx

        r = httpx.post(
            "https://api.openai.com/v1/embeddings",
            timeout=60,
            headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
            json={"model": "text-embedding-3-small", "input": texts, "dimensions": DIM},
        )
        r.raise_for_status()
        return [d["embedding"] for d in r.json()["data"]]
    return [hash_embed(t) for t in texts]
