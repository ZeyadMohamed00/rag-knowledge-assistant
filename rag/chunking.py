import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    doc: str
    idx: int
    text: str

    @property
    def id(self) -> str:
        return f"{self.doc}#{self.idx}"


def chunk_text(doc: str, text: str, size: int = 60, overlap: int = 15) -> list[Chunk]:
    """Split by words into windows of `size` words with `overlap` shared words.
    Overlap keeps a sentence that straddles a boundary retrievable from both sides."""
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    words = text.split()
    if not words:
        return []
    step = size - overlap
    out = []
    for i, start in enumerate(range(0, len(words), step)):
        window = words[start:start + size]
        out.append(Chunk(doc, i, " ".join(window)))
        if start + size >= len(words):
            break
    return out


_tok = re.compile(r"[a-z0-9]+")
STOP = {"the", "a", "an", "of", "to", "is", "are", "and", "in", "on", "for", "it", "that", "this", "with", "as", "by",
        "be", "or", "what", "how", "does", "do", "why", "when", "which", "can", "at", "from", "its"}


def tokenize(text: str) -> list[str]:
    return [t for t in _tok.findall(text.lower()) if t not in STOP]
