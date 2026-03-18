"""
RAG Store
=========
Lightweight retrieval-augmented generation store for security policy docs.
Ported from github.com/Sakethv7/RAG_mini-phase-2.

Uses sentence-transformers for embeddings (no external API needed) and
NumPy for local vector storage — no Qdrant required for the MVP.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

CHUNK_SIZE = 800
CHUNK_OVERLAP = 200
TOP_K = 6
STORE_DIR = Path(__file__).parent / "store"

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model


def _chunk(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return [c.strip() for c in chunks if c.strip()]


def _embed(texts: list[str]) -> np.ndarray:
    model = _get_model()
    vecs = model.encode(texts, normalize_embeddings=True)
    return vecs.astype(np.float32)


# ── Persistence ───────────────────────────────────────────────────────────────

def _load_store() -> tuple[np.ndarray, list[dict]]:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    vec_path = STORE_DIR / "vectors.npy"
    meta_path = STORE_DIR / "metadata.json"
    if vec_path.exists() and meta_path.exists():
        vectors = np.load(str(vec_path))
        metadata = json.loads(meta_path.read_text())
        return vectors, metadata
    return np.empty((0, 384), dtype=np.float32), []


def _save_store(vectors: np.ndarray, metadata: list[dict]) -> None:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(str(STORE_DIR / "vectors.npy"), vectors)
    (STORE_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2))


# ── Public API ────────────────────────────────────────────────────────────────

def ingest_file(path: str | Path) -> int:
    """Chunk, embed, and store a policy document. Returns chunk count."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    chunks = _chunk(text)
    if not chunks:
        return 0

    new_vecs = _embed(chunks)
    new_meta = [{"source": path.name, "chunk_index": i, "text": c} for i, c in enumerate(chunks)]

    vectors, metadata = _load_store()
    # Remove existing chunks from same file
    keep = [i for i, m in enumerate(metadata) if m["source"] != path.name]
    vectors = vectors[keep] if keep else np.empty((0, 384), dtype=np.float32)
    metadata = [metadata[i] for i in keep]

    vectors = np.vstack([vectors, new_vecs]) if vectors.size else new_vecs
    metadata.extend(new_meta)
    _save_store(vectors, metadata)
    return len(chunks)


def ingest_directory(doc_dir: str | Path | None = None) -> dict[str, int]:
    """Ingest all .md and .txt files from a directory."""
    doc_dir = Path(doc_dir or os.environ.get("POLICY_DOCS_DIR", "policy_docs"))
    results = {}
    for f in sorted(doc_dir.glob("**/*.md")) + sorted(doc_dir.glob("**/*.txt")):
        results[f.name] = ingest_file(f)
    return results


def retrieve(query: str, top_k: int = TOP_K) -> list[dict]:
    """Return top_k most relevant policy chunks for a query."""
    vectors, metadata = _load_store()
    if vectors.size == 0:
        return []

    q_vec = _embed([query])[0]
    scores = vectors @ q_vec                     # cosine similarity (already normalized)
    top_indices = np.argsort(scores)[::-1][:top_k]
    return [
        {**metadata[i], "score": float(scores[i])}
        for i in top_indices
        if scores[i] > 0.2                       # relevance threshold
    ]


def store_size() -> int:
    _, metadata = _load_store()
    return len(metadata)
