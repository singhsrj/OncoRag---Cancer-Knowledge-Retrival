"""
Full pipeline across MULTIPLE cancer-topic PDFs in data/:

  1. Build (or reuse) a per-file embedding cache for every data/*_cancer*.pdf
  2. Ask the LLM which topic the query belongs to
  3. Load ONLY that topic's cached embeddings
  4. Retrieve top_k chunks from within that one file
  5. Generate the answer

Usage:
    uv run python run_rag_router.py "What are the risk factors for lung cancer?"
"""

import argparse
import json

from knowledgebase.multi_doc import build_manifest, ensure_all_embedded
from knowledgebase.router import classify_topic
from knowledgebase.retrieval import retrieve
from helper import build_prompt, generate_answer


def main(query: str, top_k: int = 3):
    manifest = build_manifest()
    if not manifest:
        raise SystemExit("No source files found in data/ matching *_cancer*.pdf")

    ensure_all_embedded(manifest)  # embeds only whatever isn't cached yet

    topics = list(manifest.keys())
    chosen_topic = classify_topic(query, topics)
    print(f"Routed to topic: {chosen_topic}")

    cache_path = manifest[chosen_topic]["cache_path"]
    with open(cache_path) as f:
        embedded_chunks = json.load(f)

    results = retrieve(query, embedded_chunks, top_k=top_k)

    prompt = build_prompt(query, [r["text"] for r in results])
    answer = generate_answer(prompt)

    print("\nAnswer:")
    print(answer)

    print("\nSources used:")
    for r in results:
        print(f"- [{r['section']}] {r['source']} (page {r['page']})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Question to ask")
    parser.add_argument("--top_k", type=int, default=3)
    args = parser.parse_args()

    main(args.query, top_k=args.top_k)
