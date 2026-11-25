"""Answer generation. Default is EXTRACTIVE (no LLM): return the sentences from the retrieved
chunks that best overlap the question, with citations. If LLM_API_KEY is set, an OpenAI-compatible
chat endpoint is used, with the retrieved chunks as the only allowed context."""
import os, re
import httpx
from .chunking import tokenize

NO_ANSWER = "I don't know based on the provided documents."


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def extractive_answer(question: str, hits) -> str:
    if not hits:
        return NO_ANSWER
    q = set(tokenize(question))
    scored = []
    for chunk, _ in hits:
        for s in _sentences(chunk.text):
            overlap = len(q & set(tokenize(s)))
            if overlap:
                scored.append((overlap, s, chunk.id))
    if not scored:
        return NO_ANSWER
    scored.sort(key=lambda x: -x[0])
    best = scored[:2]
    return " ".join(f"{s} [{cid}]" for _, s, cid in best)


def llm_answer(question: str, hits) -> str:
    ctx = "\n\n".join(f"[{c.id}] {c.text}" for c, _ in hits)
    r = httpx.post(
        os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1") + "/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['LLM_API_KEY']}"},
        json={
            "model": os.environ.get("LLM_MODEL", "gpt-4o-mini"),
            "temperature": 0,
            "messages": [
                {"role": "system", "content": f"Answer ONLY from the context. Cite chunk ids like [doc#0]. If the context does not contain the answer say: {NO_ANSWER}"},
                {"role": "user", "content": f"Context:\n{ctx}\n\nQuestion: {question}"},
            ],
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def answer(question: str, hits) -> str:
    if not hits:
        return NO_ANSWER
    if os.environ.get("LLM_API_KEY"):
        return llm_answer(question, hits)
    return extractive_answer(question, hits)
