from pathlib import Path
from .chunking import chunk_text
from .retrieval import Retriever


def load_chunks(folder: str | Path, size: int = 60, overlap: int = 15):
    chunks = []
    for p in sorted(Path(folder).glob("*.txt")) + sorted(Path(folder).glob("*.md")):
        chunks += chunk_text(p.stem, p.read_text(encoding="utf-8"), size, overlap)
    return chunks


def build(folder: str | Path, mode: str = "hybrid") -> Retriever:
    return Retriever(load_chunks(folder), mode)
