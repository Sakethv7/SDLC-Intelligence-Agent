"""
RAG Store
=========
Lightweight retrieval-augmented generation store for security policy docs.
Ported from github.com/Sakethv7/RAG_mini-phase-2.

Uses sentence-transformers for embeddings when available and falls back to a
deterministic local embedder in offline or restricted environments. NumPy backs
the local vector store, so the MVP does not require Qdrant.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

CHUNK_SIZE = 800
CHUNK_OVERLAP = 200
TOP_K = 6
STORE_DIR = Path(__file__).parent / "store"
EMBED_DIM = 384

_model: SentenceTransformer | None = None
logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())


def _fallback_embed(texts: list[str]) -> np.ndarray:
    """
    Deterministic hash-based embedding used when the transformer model cannot
    be loaded. This keeps retrieval functional enough for tests and local demos.
    """
    vectors = np.zeros((len(texts), EMBED_DIM), dtype=np.float32)
    for row, text in enumerate(texts):
        for token in _tokenize(text):
            idx = hash(token) % EMBED_DIM
            vectors[row, idx] += 1.0

        norm = np.linalg.norm(vectors[row])
        if norm:
            vectors[row] /= norm

    return vectors


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        model_name = os.environ.get(
            "SECURITY_EMBED_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2",
        )
        try:
            _model = SentenceTransformer(model_name)
        except Exception as exc:
            logger.warning(
                "Falling back to local hash embeddings because model load failed: %s",
                exc,
            )
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
    if model is None:
        return _fallback_embed(texts)
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
    return np.empty((0, EMBED_DIM), dtype=np.float32), []


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
    vectors = vectors[keep] if keep else np.empty((0, EMBED_DIM), dtype=np.float32)
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
