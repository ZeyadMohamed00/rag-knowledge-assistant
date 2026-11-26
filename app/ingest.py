import io
import re

from docx import Document as Docx
from pypdf import PdfReader

DOCX_PAGE_CHARS = (
    3000  # .docx has no fixed pages: "page" = every ~3000 characters (approximate, documented)
)


def extract_pages(filename: str, data: bytes) -> list[str]:
    name = filename.lower()
    if name.endswith(".pdf"):
        return [(p.extract_text() or "").strip() for p in PdfReader(io.BytesIO(data)).pages]
    if name.endswith(".docx"):
        text = "\n".join(p.text for p in Docx(io.BytesIO(data)).paragraphs)
        pages, cur = [], ""
        for para in text.split("\n"):
            if len(cur) + len(para) > DOCX_PAGE_CHARS and cur:
                pages.append(cur.strip())
                cur = ""
            cur += para + "\n"
        return pages + [cur.strip()]
    if name.endswith((".txt", ".md")):
        return [data.decode("utf-8", "replace").strip()]
    raise ValueError("Unsupported file type (use PDF, DOCX or TXT)")


def chunk_page(text: str, size: int = 500, overlap_sentences: int = 1) -> list[str]:
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text)) if s.strip()]
    chunks, cur = [], []
    for s in sents:
        if cur and sum(len(x) + 1 for x in cur) + len(s) > size:
            chunks.append(" ".join(cur))
            cur = cur[-overlap_sentences:] if overlap_sentences else []
        cur.append(s)
    if cur and (not chunks or " ".join(cur) != chunks[-1]):
        chunks.append(" ".join(cur))
    return chunks
