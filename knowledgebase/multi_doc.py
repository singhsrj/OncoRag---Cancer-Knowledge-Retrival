"""
Handles multiple source PDFs (e.g. data/lung_cancer.pdf, data/breast_cancer.pdf)
instead of a single document.

Each source file gets its own embedding cache, named after the source file
(not a generic "embedded_chunks.json"), so caches don't collide and stay
identifiable at a glance:

    data/lung_cancer.pdf   -> cache/lung_cancer_embeddings.json
    data/breast_cancer.pdf -> cache/breast_cancer_embeddings.json

"Topic" names (used for routing) are just the filename stem, e.g. "lung_cancer".
"""

import os
import glob
from pathlib import Path

from pdf_preprocessor import preprocess_pdf
from knowledgebase.embed_cache import get_or_create_embedded_chunks

DATA_DIR = "data"
CACHE_DIR = "cache"


def discover_source_files(data_dir: str = DATA_DIR, pattern: str = "*_cancer*.pdf") -> list[str]:
    """Find every source PDF matching the *_cancer naming convention."""
    return sorted(glob.glob(os.path.join(data_dir, pattern)))


def cache_path_for(source_path: str, cache_dir: str = CACHE_DIR) -> str:
    stem = Path(source_path).stem  # "lung_cancer.pdf" -> "lung_cancer"
    return os.path.join(cache_dir, f"{stem}_embeddings.json")


def build_manifest(data_dir: str = DATA_DIR, cache_dir: str = CACHE_DIR) -> dict[str, dict]:
    """
    Returns: {"lung_cancer": {"source": "data/lung_cancer.pdf", "cache_path": "cache/lung_cancer_embeddings.json"}, ...}
    """
    manifest = {}
    for source_path in discover_source_files(data_dir):
        topic = Path(source_path).stem
        manifest[topic] = {
            "source": source_path,
            "cache_path": cache_path_for(source_path, cache_dir),
        }
    return manifest


def ensure_all_embedded(manifest: dict[str, dict]) -> None:
    """
    For each topic, embed ONLY if its cache file doesn't already exist.
    Skips PDF parsing entirely on a cache hit -- not just the embedding call --
    since there's no reason to touch the source file if we already have vectors.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)

    for topic, info in manifest.items():
        if os.path.exists(info["cache_path"]):
            print(f"[{topic}] cache exists, skipping ({info['cache_path']})")
            continue

        print(f"[{topic}] no cache found, processing {info['source']}...")
        chunks = preprocess_pdf(info["source"])
        get_or_create_embedded_chunks(chunks, cache_path=info["cache_path"])
