"""
search.py — finds the most relevant chunks for a student's question.

Two search methods, combined ("hybrid search"):

1. BM25 keyword search (always on)
   Classic search-engine ranking: chunks that contain the question's rare
   words many times score high. Fast, works offline, no model download.

2. Semantic search with embeddings (optional, turns on automatically if
   `sentence-transformers` is installed)
   Each chunk becomes a vector of 384 numbers describing its *meaning*.
   "voltage around a closed path" can then match a chunk about
   "Kirchhoff's voltage law" even with few shared words.

Final score = 0.5 * keyword score + 0.5 * meaning score (both scaled 0..1).
"""

import os
import re
from functools import lru_cache

import numpy as np
from rank_bm25 import BM25Okapi

import db

STOPWORDS = set("""
a an the and or but if then else of to in on at by for with from as is are was were be been being
this that these those it its into about over under what which who whom whose why how when where
do does did done can could should would will shall may might must i you he she we they me my your
our their them his her explain define describe write short note notes give list state discuss
derive what's whats between also any all each some such than too very just not no yes so
""".split())

EMBED_MODEL_NAME = os.environ.get("VIGNAN_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


# ---------------------------------------------------------------- text helpers
def stem(word: str) -> str:
    for suf in ("ations", "ation", "ings", "ing", "ies", "ed", "s"):
        if len(word) > len(suf) + 3 and word.endswith(suf):
            return word[: -len(suf)] + ("y" if suf == "ies" else "")
    return word


def tokenize(text: str):
    text = re.sub(r"['’]s\b", "", text.lower())        # Thevenin's -> thevenin
    words = re.findall(r"[a-z][a-z0-9]+|\d+", text)
    return [stem(w) for w in words if w not in STOPWORDS]


def best_snippet(text: str, query: str, max_chars=320) -> str:
    """Pick the sentence(s) in a chunk that share the most words with the query."""
    q = set(tokenize(query))
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if not sentences:
        return text[:max_chars]
    scored = sorted(
        range(len(sentences)),
        key=lambda i: -len(q & set(tokenize(sentences[i]))),
    )
    keep = sorted(scored[:2])
    snippet = " ".join(sentences[i] for i in keep)
    return snippet if len(snippet) <= max_chars else snippet[: max_chars - 1] + "…"


# ---------------------------------------------------------------- embeddings (optional)
@lru_cache(maxsize=1)
def _embedder():
    if os.environ.get("VIGNAN_DISABLE_EMBEDDINGS") == "1":
        return None
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(EMBED_MODEL_NAME)
    except Exception:
        return None


def embeddings_available() -> bool:
    return _embedder() is not None


def _embed(texts):
    model = _embedder()
    vecs = model.encode(texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True)
    return np.asarray(vecs, dtype=np.float32)


# ---------------------------------------------------------------- the index
class Index:
    """Search index over the chunks of one or more subjects."""

    def __init__(self, subject_ids):
        self.chunks = db.load_chunks(subject_ids)
        tokens = [tokenize(c["text"] + " " + c["resource_title"]) for c in self.chunks]
        self.bm25 = BM25Okapi(tokens) if self.chunks else None
        self.vectors = None
        if self.chunks and embeddings_available():
            self.vectors = _embed([c["text"] for c in self.chunks])

    def search(self, query, k=6, resource_ids=None, min_score=0.05):
        if not self.chunks or not query.strip():
            return []
        q_tokens = tokenize(query)
        kw = np.asarray(self.bm25.get_scores(q_tokens), dtype=np.float32) if q_tokens else np.zeros(len(self.chunks))
        kw = kw / kw.max() if kw.max() > 0 else kw

        if self.vectors is not None:
            sem = self.vectors @ _embed([query])[0]
            sem = np.clip(sem, 0, None)
            sem = sem / sem.max() if sem.max() > 0 else sem
            score = 0.5 * kw + 0.5 * sem
        else:
            score = kw

        allowed = set(resource_ids) if resource_ids else None
        order = np.argsort(-score)
        hits, per_page = [], set()
        for i in order:
            if score[i] < min_score or len(hits) >= k:
                break
            c = self.chunks[i]
            if allowed and c["resource_id"] not in allowed:
                continue
            key = (c["resource_id"], c["page"])
            if key in per_page:          # one hit per page keeps results varied
                continue
            per_page.add(key)
            hits.append({**c, "score": float(score[i]), "snippet": best_snippet(c["text"], query)})
        return hits


_cache = {}


def get_index(subject_ids):
    """Build the index once and reuse it until a faculty member uploads/deletes something."""
    ids = tuple(sorted(subject_ids))
    sig = db.chunk_signature(ids)
    cached = _cache.get(ids)
    if cached is None or cached[0] != sig:
        _cache[ids] = (sig, Index(ids))
    return _cache[ids][1]


def search(subject_ids, query, k=6, resource_ids=None):
    return get_index(subject_ids).search(query, k=k, resource_ids=resource_ids)
