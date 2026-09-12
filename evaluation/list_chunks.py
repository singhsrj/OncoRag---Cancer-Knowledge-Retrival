"""
Two jobs:

1. chunk_identity() -- a single stable id for a retrieved/cached chunk, used
   to compare "what we retrieved" against "what's labeled relevant" in
   metrics.py. Prefers pdf_preprocessor.py's own chunk_id
   ("source.pdf::Section::0"); falls back to a composite key if a given
   knowledgebase.retrieval.retrieve() implementation strips chunk_id out of
   its return dicts.

2. A CLI (`python -m evaluation.list_chunks <topic>`) that prints every
   cached chunk's identity + a text preview for a topic, so you can build
   evaluation/dataset.json by eye instead of guessing ids.
"""

import argparse
import json

from knowledgebase.multi_doc import build_manifest, ensure_all_embedded


def chunk_identity(chunk: dict) -> str:
    if chunk.get("chunk_id"):
        return chunk["chunk_id"]
    return f"{chunk.get('source')}::{chunk.get('section')}::{chunk.get('page')}"


def main(topic: str) -> None:
    manifest = build_manifest()
    if topic not in manifest:
        raise SystemExit(f"Unknown topic '{topic}'. Known topics: {list(manifest.keys())}")
    ensure_all_embedded(manifest)

    with open(manifest[topic]["cache_path"]) as f:
        chunks = json.load(f)

    print(f"{len(chunks)} chunks cached for topic '{topic}':\n")
    for chunk in chunks:
        preview = chunk["text"][:120].replace("\n", " ")
        print(f"{chunk_identity(chunk)}")
        print(f"    {preview}...\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("topic", help="Topic key as shown by build_manifest() / GET /api/topics/")
    main(parser.parse_args().topic)
