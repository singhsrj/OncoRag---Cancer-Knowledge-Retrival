"""
Same retrieval logic as helper.retrieve(), adapted to work over the
cached chunk dicts (which carry full metadata) instead of two separate
parallel lists of chunks/embeddings.
"""

import numpy as np
from knowledgebase.embeddings import embed_one


def cosine_similarity(a, b) -> float:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def retrieve(query: str, embedded_chunks: list[dict], top_k: int = 3) -> list[dict]:
    """
    embedded_chunks: output of get_or_create_embedded_chunks() --
    each dict has "text", "section", "source", "page", "chunk_id", "embedding".

    Returns the top_k chunk dicts (full metadata, not just text) ranked
    by similarity to the query.
    """
    query_embedding = embed_one(query)

    scores = [
        cosine_similarity(query_embedding, chunk["embedding"])
        for chunk in embedded_chunks
    ]
    top_indices = np.argsort(scores)[::-1][:top_k]

    return [embedded_chunks[int(i)] for i in top_indices]
