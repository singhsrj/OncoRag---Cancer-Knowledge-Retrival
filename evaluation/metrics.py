"""
Standard retrieval metrics. All take the list of chunk identities the
retriever actually returned (`retrieved_ids`, already truncated to top_k)
and the hand-labeled list of chunk identities that are actually relevant
to the query (`relevant_ids`).
"""


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str]) -> float | None:
    """Of all relevant chunks that exist, what fraction did we surface in top-k?"""
    if not relevant_ids:
        return None
    hits = len(set(retrieved_ids) & set(relevant_ids))
    return hits / len(relevant_ids)


def precision_at_k(retrieved_ids: list[str], relevant_ids: list[str]) -> float | None:
    """Of the chunks we returned, what fraction were actually relevant?"""
    if not retrieved_ids:
        return 0.0
    hits = len(set(retrieved_ids) & set(relevant_ids))
    return hits / len(retrieved_ids)


def mrr(retrieved_ids: list[str], relevant_ids: list[str]) -> float | None:
    """Reciprocal rank of the first relevant chunk (0 if none found)."""
    if not relevant_ids:
        return None
    for rank, cid in enumerate(retrieved_ids, start=1):
        if cid in relevant_ids:
            return 1.0 / rank
    return 0.0
