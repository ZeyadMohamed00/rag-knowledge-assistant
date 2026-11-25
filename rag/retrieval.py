import math
from collections import Counter
from .chunking import Chunk, tokenize


class BM25:
    """Okapi BM25, written from scratch so the scoring is explainable.
    score(q,d) = sum_t idf(t) * tf*(k1+1) / (tf + k1*(1-b+b*|d|/avgdl))"""

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks, self.k1, self.b = chunks, k1, b
        self.tfs = [Counter(tokenize(c.text)) for c in chunks]
        self.lens = [sum(tf.values()) for tf in self.tfs]
        self.avgdl = (sum(self.lens) / len(self.lens)) if self.lens else 0.0
        df = Counter()
        for tf in self.tfs:
            df.update(tf.keys())
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def scores(self, query: str) -> list[float]:
        q = tokenize(query)
        out = []
        for tf, dl in zip(self.tfs, self.lens):
            s = 0.0
            for t in q:
                if t in tf:
                    f = tf[t]
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            out.append(s)
        return out


class TfidfIndex:
    """Cosine similarity over TF-IDF vectors (scikit-learn), with word bigrams."""

    def __init__(self, chunks: list[Chunk]):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.chunks = chunks
        self.vec = TfidfVectorizer(tokenizer=tokenize, lowercase=False, ngram_range=(1, 2), token_pattern=None)
        self.matrix = self.vec.fit_transform([c.text for c in chunks])

    def scores(self, query: str) -> list[float]:
        q = self.vec.transform([query])
        return (self.matrix @ q.T).toarray().ravel().tolist()


def _norm(xs):
    m = max(xs) if xs else 0
    return [x / m if m > 0 else 0.0 for x in xs]


class Retriever:
    MODES = ("bm25", "tfidf", "hybrid")

    def __init__(self, chunks: list[Chunk], mode: str = "hybrid"):
        if mode not in self.MODES:
            raise ValueError(f"mode must be one of {self.MODES}")
        self.chunks, self.mode = chunks, mode
        self.bm25 = BM25(chunks)
        self.tfidf = TfidfIndex(chunks) if chunks else None

    def search(self, query: str, k: int = 4) -> list[tuple[Chunk, float]]:
        if not self.chunks:
            return []
        if self.mode == "bm25":
            sc = self.bm25.scores(query)
        elif self.mode == "tfidf":
            sc = self.tfidf.scores(query)
        else:  # hybrid: average of max-normalised scores
            a, b = _norm(self.bm25.scores(query)), _norm(self.tfidf.scores(query))
            sc = [(x + y) / 2 for x, y in zip(a, b)]
        order = sorted(range(len(sc)), key=lambda i: -sc[i])[:k]
        return [(self.chunks[i], sc[i]) for i in order if sc[i] > 0]
