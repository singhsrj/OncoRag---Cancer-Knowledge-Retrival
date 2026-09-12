"""
Embedding + generation calls via OpenRouter, following the same pattern
as your helper.py (requests + explicit error checks on the response shape).
This is the ONE place that owns the OpenRouter embedding calls, so both
ingestion (embedding chunks) and querying (embedding a question) share it.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
EMBEDDING_MODEL = "openai/text-embedding-3-small"  # 1536 dims -- must match models.py VectorField


def embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Embed many chunks in a single API call. Same call your main script
    makes for the document chunks, pulled out so ingest.py and the
    query path both go through this one function.
    """
    response = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": EMBEDDING_MODEL, "input": texts},
    )
    data = response.json()

    if "data" not in data:
        raise Exception(f"Embedding API error: {data}")

    return [item["embedding"] for item in data["data"]]


def embed_one(text: str) -> list[float]:
    """Embed a single string (e.g. a user's query)."""
    return embed_batch([text])[0]
