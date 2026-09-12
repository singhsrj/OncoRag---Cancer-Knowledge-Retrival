"""
Caches embeddings to a local JSON file so you're not re-calling the
OpenRouter API (and paying for it) every time you run the pipeline.

Behavior:
  - If the cache file exists -> load it, skip embedding entirely.
  - If it doesn't -> embed all chunks, save the result, return it.

The cache file stores the SAME chunk dicts from pdf_preprocessor.py,
just with an "embedding" key added to each one -- so nothing downstream
needs a different shape depending on whether the cache hit or missed.
"""

import json
import os
from knowledgebase.embeddings import embed_batch

DEFAULT_CACHE_PATH = "embedded_chunks.json"


def get_or_create_embedded_chunks(
    chunks: list[dict],
    cache_path: str = DEFAULT_CACHE_PATH,
    force_refresh: bool = False,
) -> list[dict]:
    """
    chunks: output of pdf_preprocessor.py, e.g.
        {"text": ..., "section": ..., "source": ..., "page": ..., "chunk_id": ...}

    Returns the same list, each dict now also containing "embedding".
    """
    if os.path.exists(cache_path) and not force_refresh:
        print(f"Cache hit: loading embeddings from {cache_path}")
        with open(cache_path) as f:
            return json.load(f)

    print(f"No cache found at {cache_path} -- embedding {len(chunks)} chunks via OpenRouter...")
    texts = [c["text"] for c in chunks]

    # Batch to stay under request size limits and keep API calls cheap.
    # 100 is a safe default for text-embedding-3-small; raise it if your
    # chunks are short, lower it if you hit request-size errors.
    batch_size = 100
    embedded_chunks = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        batch_texts = texts[i:i + batch_size]
        vectors = embed_batch(batch_texts)

        for chunk, vector in zip(batch, vectors):
            embedded_chunks.append({**chunk, "embedding": vector})

        print(f"Embedded {len(embedded_chunks)}/{len(chunks)} chunks...")

    with open(cache_path, "w") as f:
        json.dump(embedded_chunks, f)
    print(f"Saved embeddings to {cache_path}")

    return embedded_chunks
