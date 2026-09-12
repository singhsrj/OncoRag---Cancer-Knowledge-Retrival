"""
Runs the full pipeline end-to-end:
  PDF -> structure-aware chunks -> cached embeddings -> retrieve -> answer

Usage:
    uv run python run_rag.py path/to/cancer_fact_sheet.pdf "What are the risk factors for cancer?"
"""

import argparse
from pdf_preprocessor import preprocess_pdf
from knowledgebase.embed_cache import get_or_create_embedded_chunks
from knowledgebase.retrieval import retrieve
from helper import build_prompt, generate_answer


def main(pdf_path: str, query: str, cache_path: str = "embedded_chunks.json", top_k: int = 3):
    # Cheap, no API calls -- parses the PDF and splits it into
    # section-scoped chunks every time.
    chunks = preprocess_pdf(pdf_path)

    # Expensive step -- only actually calls OpenRouter if cache_path
    # doesn't exist yet.
    embedded_chunks = get_or_create_embedded_chunks(chunks, cache_path=cache_path)

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
    parser.add_argument("pdf_path", help="Path to the source PDF")
    parser.add_argument("query", help="Question to ask")
    parser.add_argument("--cache", default="embedded_chunks.json", help="Embedding cache file path")
    parser.add_argument("--top_k", type=int, default=3)
    args = parser.parse_args()

    main(args.pdf_path, args.query, cache_path=args.cache, top_k=args.top_k)
