#!/usr/bin/env python3
# Copyright (c) 2026 Santander Group
# SPDX-License-Identifier: Apache-2.0
"""Semantic search for ralph-vault.

Optional, dependency-free fallback included. When `sentence-transformers` is
installed (``pip install sentence-transformers``), the module uses a real
multilingual embedding model for proper semantic search. Without it, falls
back to character-n-gram cosine similarity — fast, no deps, but purely
lexical.

Usage
-----
    from search import index_vault, search_vault
    index_vault("vault/")
    results = search_vault("autenticación y autorización", top_k=5)
    for r in results:
        print(f"{r['path']} ({r['score']:.3f}) {r['title']}")
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# Configurable model selector — change to prefer a different embedding model
# --------------------------------------------------------------------------- #
EMBEDDING_MODEL: str = "thenlper/gte-small"  # tiny, fast, multilingual-capable


# --------------------------------------------------------------------------- #
# YAML frontmatter parser (no PyYAML dependency)
# --------------------------------------------------------------------------- #
_YAML_BLOCK = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_YAML_KEY_VAL = re.compile(r"^(\w[\w-]*):\s*(.+)$", re.MULTILINE)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split markdown into (frontmatter_dict, body_text).

    Returns empty dict and full text when no YAML frontmatter is present.
    """
    m = _YAML_BLOCK.match(text)
    if not m:
        return {}, text
    fm = {}
    for km in _YAML_KEY_VAL.finditer(m.group(1)):
        key, val = km.group(1), km.group(2).strip()
        # Try to parse simple YAML types
        if (val.startswith('"') and val.endswith('"')) or \
           (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        elif val.lower() == "true":
            val = "true"
        elif val.lower() == "false":
            val = "false"
        elif val == "null":
            val = ""
        fm[key] = val
    body_start = m.end()
    # Skip leading newlines after the closing ---
    while body_start < len(text) and text[body_start] in ("\n", "\r"):
        body_start += 1
    return fm, text[body_start:] if body_start < len(text) else ""


# --------------------------------------------------------------------------- #
# Document extraction
# --------------------------------------------------------------------------- #
def _scan_docs(vault: Path) -> list[dict[str, str | list[str]]]:
    """Yield every .md file (excluding READMEs, meta, and vault internals)."""
    skip_files = {"README.md", "LAST-UPDATED.md", "config.json"}
    skip_dirs_in_path = {"plan/", "assets/"}

    results: list[dict[str, str | list[str]]] = []
    for md_file in sorted(vault.rglob("*.md")):
        rel = md_file.relative_to(vault)
        rel_str = str(rel)

        # Skip plan/, assets/, READMEs, and non-doc markdown
        if any(skip in rel_str for skip in skip_dirs_in_path):
            continue
        if md_file.name == "README.md":
            continue
        if rel_str in skip_files:
            continue

        try:
            raw = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        fm, body = parse_frontmatter(raw)
        if not body or len(body.strip()) < 20:
            continue  # skip tiny/empty files

        results.append({
            "path": rel_str,
            "title": fm.get("title", md_file.stem),
            "type": fm.get("type", ""),
            "load_tier": fm.get("load_tier", "2"),
            "repo": fm.get("repo", ""),
            "tags": fm.get("tags", []),
            "body": body,
            "raw": raw,
        })

    return results


# --------------------------------------------------------------------------- #
# Embedding backends
# --------------------------------------------------------------------------- #

class EmbeddingBackend:
    """Abstract base for embedding providers."""

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """Cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b, strict=True))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)


class NgramFallbackBackend(EmbeddingBackend):
    """Pure-Python character-4-gram embedding with TF-IDF weighting.

    Works without any ML dependencies. Good enough for vault-sized
    documents where keyword matching matters, but not true semantic
    search.
    """

    NGRAM = 4
    VOCAB: Counter | None = None

    def __init__(self):
        self._idf: dict[str, float] = {}

    def _ngrams(self, text: str) -> list[str]:
        text = text.lower()
        return [text[i:i + self.NGRAM] for i in range(len(text) - self.NGRAM + 1)]

    def build_vocabulary(self, docs: list[str]) -> None:
        """Build IDF from a corpus of document strings."""
        n_docs = len(docs)
        df: Counter = Counter()
        for d in docs:
            for ng in self._ngrams(d):
                df[ng] += 1

        self._idf = {}
        for ng, freq in df.items():
            self._idf[ng] = math.log((1 + n_docs) / (1 + freq)) + 1

    def embed(self, text: str) -> list[float]:
        """Embed a text string as a sparse TF-IDF vector (represented as dense list).

        Uses a fixed hash space to map n-grams to vector indices.
        """
        hash_size = 1024
        counts: Counter = Counter(self._ngrams(text))

        vector = [0.0] * hash_size
        total_tf = sum(counts.values()) or 1
        for ng, tf in counts.items():
            idx = hash(ng) % hash_size
            idf = self._idf.get(ng, 1.0)
            vector[idx] += (tf / total_tf) * idf

        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


class TransformerBackend(EmbeddingBackend):
    """sentence-transformers backed embedding.

    Requires `pip install sentence-transformers` (which pulls in torch/transformers).
    """

    def __init__(self):
        # Lazy import — only loads when first used
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
        except ImportError as err:
            raise ImportError(
                "sentence-transformers no está instalado. "
                "Instálalo con: pip install sentence-transformers\n"
                "O usa el fallback n-gram (busca por keywords, no semánticamente).",
            ) from err

        self._model = SentenceTransformer(EMBEDDING_MODEL)
        self._vocab: Counter | None = None

    def embed(self, text: str) -> list[float]:
        emb = self._model.encode(text, normalize_embeddings=True, show_progress_bar=False)
        return emb.tolist()


# --------------------------------------------------------------------------- #
# Index management
# --------------------------------------------------------------------------- #

INDEX_PATH: str = ".ralphvault/search-index.json"


def _load_index(vault: Path) -> dict[str, Any] | None:
    idx = vault / INDEX_PATH
    if idx.exists():
        return json.loads(idx.read_text(encoding="utf-8"))
    return None


def _save_index(vault: Path, index: dict[str, Any]) -> None:
    idx = vault / INDEX_PATH
    idx.parent.mkdir(parents=True, exist_ok=True)
    idx.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def index_vault(
    vault: Path | str,
    force: bool = False,
    backend: str = "auto",
) -> dict[str, Any]:
    """Index all vault documents for semantic search.

    Args:
        vault: Path to the vault directory.
        force: If True, rebuilds even if index exists.
        backend: "transformers" (requires sentence-transformers),
                 "ngram" (pure Python, keyword-only), or "auto" (tries
                 transformers first, falls back to ngram).

    Returns:
        Index dict with metadata and per-doc embeddings.
    """
    vault = Path(vault).resolve()

    # Determine backend
    if backend == "auto":
        try:
            backend_cls = TransformerBackend()
            backend_name = "transformers"
            _backend = backend_cls
        except ImportError:
            _backend = NgramFallbackBackend()
            backend_name = "ngram"
    elif backend == "transformers":
        _backend = TransformerBackend()
        backend_name = "transformers"
    elif backend == "ngram":
        _backend = NgramFallbackBackend()
        backend_name = "ngram"
    else:
        raise ValueError(f"Unknown backend: {backend}. Use 'auto', 'transformers', or 'ngram'.")

    # Scan docs
    docs = _scan_docs(vault)
    if not docs:
        index_data: dict[str, Any] = {
            "version": 1, "backend": backend_name, "docs": [],
            "indexed_at": _now_iso(), "n_docs": 0,
        }
        _save_index(vault, index_data)
        return index_data

    # Build text corpus
    corpus = [f"{d['title']} {d['type']} {d['tags']} {d['body']}" for d in docs]

    # Train vocabulary (for ngram mode)
    if isinstance(_backend, NgramFallbackBackend):
        _backend.build_vocabulary(corpus)

    # Create embeddings
    embeddings: list[list[float]] = []
    for text in corpus:
        emb = _backend.embed(text)
        embeddings.append(emb)

    index_data: dict[str, Any] = {
        "version": 1,
        "backend": backend_name,
        "indexed_at": _now_iso(),
        "n_docs": len(docs),
        "docs": [],
    }

    for i, doc in enumerate(docs):
        index_data["docs"].append({
            "path": doc["path"],
            "title": doc["title"],
            "type": doc["type"],
            "load_tier": doc["load_tier"],
            "repo": doc["repo"],
            "tags": doc["tags"],
            "embedding": embeddings[i],
            "body_snippet": doc["body"][:300],  # Short preview for display
        })

    _save_index(vault, index_data)

    return index_data


def search_vault(
    vault: Path | str,
    query: str,
    top_k: int = 5,
    backend: str = "auto",
) -> list[dict[str, Any]]:
    """Search vault documents using semantic similarity.

    Args:
        vault: Path to the vault directory.
        query: Search query in natural language.
        top_k: Number of results to return (default 5).
        backend: Same as index_vault.

    Returns:
        List of results sorted by similarity score (highest first).
        Each result: {path, title, type, load_tier, repo, score, snippet}
    """
    vault = Path(vault).resolve()
    index = _load_index(vault)

    if index is None:
        # Auto-index on first query
        index_vault(vault, backend=backend)
        index = _load_index(vault)

    if index is None or not index.get("docs"):
        return []

    # Determine backend for embedding the query
    if index.get("backend") == "ngram" or backend == "ngram":
        _backend = NgramFallbackBackend()
        _backend.build_vocabulary([d["body_snippet"] for d in index["docs"]] + [query])
    else:
        try:
            _backend = TransformerBackend()
        except ImportError:
            _backend = NgramFallbackBackend()
            _backend.build_vocabulary([d["body_snippet"] for d in index["docs"]] + [query])

    query_emb = _backend.embed(query)
    results: list[dict[str, Any]] = []

    for doc in index["docs"]:
        score = _backend.cosine_similarity(query_emb, doc["embedding"])
        results.append({
            "path": doc["path"],
            "title": doc["title"],
            "type": doc["type"],
            "load_tier": doc["load_tier"],
            "repo": doc["repo"],
            "score": round(score, 4),
            "snippet": doc["body_snippet"],
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
# CLI standalone usage (when called directly)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Semantic search for ralph-vault")
    parser.add_argument("--vault", default="vault", help="vault directory")
    parser.add_argument("query", help="search query")
    parser.add_argument("--k", type=int, default=5, help="number of results")
    parser.add_argument("--index", action="store_true", help="rebuild index first")
    parser.add_argument(
        "--backend",
        choices=["auto", "transformers", "ngram"],
        default="auto",
        help="embedding backend (default: auto)",
    )
    args = parser.parse_args()

    if args.index:
        idx = index_vault(args.vault, backend=args.backend)
        print(f"Indexed {idx['n_docs']} docs with {idx['backend']} backend")

    results = search_vault(args.vault, args.query, top_k=args.k, backend=args.backend)

    if not results:
        print("No results found. Try rebuilding the index with --index")
        sys.exit(1)

    print(f"\nResults for \"{args.query}\" (backend: {results[0].get('backend', 'auto')})\n")
    print("-" * 60)
    for i, r in enumerate(results, 1):
        print(f"\n{i}. [{r['score']:.3f}] {r['title']}")
        print(f"   Path: {r['path']}")
        print(f"   Type: {r['type']} | Repo: {r['repo']} | Tier: {r['load_tier']}")
        print(f"   Snippet: {r['snippet'][:120]}…")
        print()