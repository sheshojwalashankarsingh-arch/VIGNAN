"""
ingest.py — turns an uploaded PDF into searchable chunks.

Step 1: read every page's text with PyMuPDF (keeps the page number)
Step 2: cut each page into overlapping windows of ~120 words ("chunks")
Step 3: store chunks in the database, tagged with resource + page

Why chunks? A whole book is too big to search or send to an AI model.
Small chunks let us find the exact paragraph — and the exact page — that
answers a student's question.
"""

import os
import re
import unicodedata
import uuid

import pymupdf

import db

CHUNK_WORDS = 120     # words per chunk
OVERLAP_WORDS = 30    # words shared between neighbouring chunks (so no idea gets cut in half)


def clean(text: str) -> str:
    for lig in "\ufb00\ufb01\ufb02\ufb03\ufb04\ufb05\ufb06":  # "ﬁ"/"ﬀ" ligatures -> normal letters
        text = text.replace(lig, unicodedata.normalize("NFKC", lig))
    text = text.replace("\u00ad", "")         # soft hyphens
    text = re.sub(r"-\n(\w)", r"\1", text)         # join words broken across lines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def extract_pages(pdf_path):
    """Return [(page_number, text), ...] — page numbers start at 1."""
    pages = []
    with pymupdf.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            pages.append((i + 1, clean(page.get_text("text"))))
    return pages


def chunk_page(text, size=CHUNK_WORDS, overlap=OVERLAP_WORDS):
    words = text.split()
    if not words:
        return []
    if len(words) <= size:
        return [" ".join(words)]
    out, step = [], size - overlap
    for start in range(0, len(words), step):
        piece = words[start:start + size]
        if len(piece) < 25 and out:          # tiny leftover: glue onto the previous chunk
            out[-1] += " " + " ".join(piece)
            break
        out.append(" ".join(piece))
        if start + size >= len(words):
            break
    return out


def ingest_file(resource_id, subject_id, pdf_path):
    """Extract + chunk + store. Returns a small report dict."""
    pages = extract_pages(pdf_path)
    chunks = []
    text_pages = 0
    for page_no, text in pages:
        if len(text.split()) >= 5:
            text_pages += 1
        for piece in chunk_page(text):
            chunks.append((page_no, piece))
    db.save_chunks(resource_id, subject_id, chunks, len(pages), text_pages)
    scanned = len(pages) > 0 and text_pages / len(pages) < 0.3
    return {"pages": len(pages), "text_pages": text_pages, "chunks": len(chunks), "looks_scanned": scanned}


def save_upload(subject_id, filename, data: bytes) -> str:
    """Store the raw file on disk under a unique name and return its path."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)[-80:]
    folder = os.path.join(db.UPLOAD_DIR, f"subject_{subject_id}")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{uuid.uuid4().hex[:8]}_{safe}")
    with open(path, "wb") as f:
        f.write(data)
    return path


def add_pdf(subject_id, title, kind, filename, data: bytes, uploaded_by):
    """Full pipeline used by the faculty upload page."""
    path = save_upload(subject_id, filename, data)
    try:
        with pymupdf.open(path) as _:
            pass
    except Exception as e:
        os.remove(path)
        raise ValueError(f"'{filename}' is not a readable PDF ({e})")
    rid = db.add_resource(subject_id, title, kind, filename, path, uploaded_by)
    report = ingest_file(rid, subject_id, path)
    report["resource_id"] = rid
    return report


def render_page_png(pdf_path, page_number, zoom=1.6) -> bytes:
    """Render one PDF page as a PNG — used by the in-app reader."""
    with pymupdf.open(pdf_path) as doc:
        page_number = max(1, min(page_number, doc.page_count))
        pix = doc[page_number - 1].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        return pix.tobytes("png")


def page_count(pdf_path) -> int:
    with pymupdf.open(pdf_path) as doc:
        return doc.page_count
