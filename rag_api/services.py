"""
Thin service layer around the existing OncoRag pipeline
(knowledgebase.multi_doc / knowledgebase.router / knowledgebase.retrieval /
helper.py). This mirrors run_rag_router.py's main() exactly, just reshaped so
a Django view can call it and get a dict back instead of printed output.

Nothing in helper.py, knowledgebase/, or pdf_preprocessor.py is modified.
"""

import json
import logging
import threading

# These are the exact modules run_rag_router.py already imports and uses.
from knowledgebase.multi_doc import build_manifest, ensure_all_embedded
from knowledgebase.router import classify_topic
from knowledgebase.retrieval import retrieve
from helper import build_prompt, generate_answer

logger = logging.getLogger(__name__)

_manifest = None
_manifest_lock = threading.Lock()


class RagServiceError(Exception):
    """Raised for expected, user-facing failures (no data, bad topic, etc.)."""


def get_manifest() -> dict:
    """
    Build (or reuse) the per-file embedding manifest exactly once per worker
    process, and make sure every data/*_cancer*.pdf has a cached embedding
    file on disk -- identical to what run_rag_router.py does before every
    query, except we only pay that cost once instead of once per request.
    """
    global _manifest
    if _manifest is not None:
        return _manifest

    with _manifest_lock:
        if _manifest is None:
            manifest = build_manifest()
            if not manifest:
                raise RagServiceError(
                    "No source files found in data/ matching *_cancer*.pdf"
                )
            logger.info("Building/verifying embedding cache for %d topic(s)...", len(manifest))
            ensure_all_embedded(manifest)
            _manifest = manifest
            logger.info("OncoRag manifest ready: topics=%s", list(manifest.keys()))
    return _manifest


def list_topics() -> list[str]:
    return list(get_manifest().keys())


def answer_query(query: str, top_k: int = 3) -> dict:
    """
    Route -> retrieve -> generate, same as run_rag_router.main(), returned as
    a plain dict instead of printed to stdout.
    """
    if not query or not query.strip():
        raise RagServiceError('"query" is required')

    manifest = get_manifest()
    topics = list(manifest.keys())

    chosen_topic = classify_topic(query, topics)
    if chosen_topic not in manifest:
        raise RagServiceError(
            f"Router returned an unknown topic '{chosen_topic}' (known topics: {topics})"
        )

    cache_path = manifest[chosen_topic]["cache_path"]
    with open(cache_path) as f:
        embedded_chunks = json.load(f)

    results = retrieve(query, embedded_chunks, top_k=top_k)
    prompt = build_prompt(query, [r["text"] for r in results])
    answer = generate_answer(prompt)

    return {
        "query": query,
        "topic": chosen_topic,
        "answer": answer,
        "sources": [
            {
                "section": r.get("section"),
                "source": r.get("source"),
                "page": r.get("page"),
            }
            for r in results
        ],
    }
