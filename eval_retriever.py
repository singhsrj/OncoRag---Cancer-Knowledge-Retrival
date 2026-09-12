"""
Sweeps top_k across your existing routed-retrieval pipeline and scores both
retrieval quality (Recall@k, Precision@k, MRR -- only for queries you've
labeled with relevant_chunk_ids) and generation quality (Faithfulness,
Answer Relevance -- LLM-judged, no labels needed) so you can pick the top_k
that gives the best recall/precision without paying for it in faithfulness
or relevance.

Uses your existing pipeline pieces exactly as run_rag_router.py does:
knowledgebase.multi_doc.build_manifest/ensure_all_embedded,
knowledgebase.router.classify_topic, knowledgebase.retrieval.retrieve,
helper.build_prompt/generate_answer. Nothing in those files is modified.

Usage:
    uv run python eval_retriever.py evaluation/dataset.json
    uv run python eval_retriever.py evaluation/dataset.json --k 1 3 5 7 10
    uv run python eval_retriever.py evaluation/dataset.json --no-router
    uv run python eval_retriever.py evaluation/dataset.json --out evaluation/results.json
"""

import argparse
import json
import statistics
from pathlib import Path

from knowledgebase.multi_doc import build_manifest, ensure_all_embedded
from knowledgebase.router import classify_topic
from knowledgebase.retrieval import retrieve
from helper import build_prompt, generate_answer

from evaluation.metrics import recall_at_k, precision_at_k, mrr
from evaluation.judge import faithfulness_score, answer_relevance_score
from evaluation.list_chunks import chunk_identity


def load_dataset(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def run_one(item: dict, manifest: dict, top_k: int, use_router: bool) -> dict:
    query = item["query"]
    topics = list(manifest.keys())

    # --no-router lets you isolate retrieval/generation quality from routing
    # accuracy, by forcing the labeled topic instead of calling classify_topic.
    topic = classify_topic(query, topics) if use_router else item.get("topic")
    if topic not in manifest:
        return {"query": query, "top_k": top_k, "error": f"unknown topic '{topic}'"}

    with open(manifest[topic]["cache_path"]) as f:
        chunks = json.load(f)

    results = retrieve(query, chunks, top_k=top_k)
    retrieved_ids = [chunk_identity(r) for r in results]

    row = {
        "query": query,
        "top_k": top_k,
        "routed_topic": topic,
        "expected_topic": item.get("topic"),
        "routing_correct": (topic == item["topic"]) if item.get("topic") else None,
    }

    relevant_ids = item.get("relevant_chunk_ids")
    if relevant_ids:
        row["recall"] = recall_at_k(retrieved_ids, relevant_ids)
        row["precision"] = precision_at_k(retrieved_ids, relevant_ids)
        row["mrr"] = mrr(retrieved_ids, relevant_ids)

    prompt = build_prompt(query, [r["text"] for r in results])
    answer = generate_answer(prompt)
    row["faithfulness"] = faithfulness_score(answer, [r["text"] for r in results])
    row["answer_relevance"] = answer_relevance_score(query, answer)
    row["answer"] = answer
    return row


def summarize(rows: list[dict]) -> dict:
    def avg(key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return round(statistics.mean(vals), 4) if vals else None

    return {
        "n_queries": len(rows),
        "avg_recall": avg("recall"),
        "avg_precision": avg("precision"),
        "avg_mrr": avg("mrr"),
        "avg_faithfulness": avg("faithfulness"),
        "avg_answer_relevance": avg("answer_relevance"),
        "routing_accuracy": avg("routing_correct"),
    }


def pick_best_k(summary_by_k: dict) -> int:
    """
    Simple, explainable scoring: reward recall + faithfulness + relevance,
    lightly penalize larger k (more context = more tokens/cost/latency, and
    a higher chance of pulling in an irrelevant chunk that drags an answer
    off-topic). Treat missing metrics (e.g. no labels given) as neutral (0)
    rather than crashing.
    """
    def score(k):
        s = summary_by_k[k]
        return (
            (s["avg_recall"] or 0)
            + (s["avg_faithfulness"] or 0)
            + (s["avg_answer_relevance"] or 0)
            - 0.02 * k
        )

    return max(summary_by_k, key=score)


def main(dataset_path: str, k_values: list[int], use_router: bool, out_path: str) -> None:
    dataset = load_dataset(dataset_path)
    manifest = build_manifest()
    if not manifest:
        raise SystemExit("No source files found in data/ matching *_cancer*.pdf")
    ensure_all_embedded(manifest)

    all_rows = []
    summary_by_k = {}

    for k in k_values:
        print(f"\n=== top_k = {k} ===")
        rows = [run_one(item, manifest, k, use_router) for item in dataset]
        for row in rows:
            print(
                f"  [{row.get('routed_topic')}] {row['query'][:60]!r} | "
                f"recall={row.get('recall')} precision={row.get('precision')} "
                f"faithfulness={row.get('faithfulness')} relevance={row.get('answer_relevance')}"
            )
        all_rows.extend(rows)
        summary_by_k[k] = summarize(rows)

    print("\n=== Summary by top_k ===")
    for k, s in summary_by_k.items():
        print(f"k={k}: {s}")

    best_k = pick_best_k(summary_by_k)
    print(
        f"\nSuggested top_k: {best_k} "
        f"(highest recall + faithfulness + relevance, lightly penalized for larger k)"
    )
    print("This is a starting point, not gospel -- eyeball the per-query rows above, "
          "especially any faithfulness dips, before locking it in.")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(
        json.dumps(
            {"rows": all_rows, "summary_by_k": summary_by_k, "suggested_top_k": best_k},
            indent=2,
        )
    )
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dataset", help="Path to eval dataset JSON (see evaluation/dataset.example.json)")
    parser.add_argument("--k", type=int, nargs="+", default=[1, 3, 5, 7], help="top_k values to sweep")
    parser.add_argument(
        "--no-router",
        action="store_true",
        help="Use each item's labeled 'topic' instead of calling classify_topic (isolates retrieval from routing)",
    )
    parser.add_argument("--out", default="evaluation/results.json", help="Where to write full JSON results")
    args = parser.parse_args()
    main(args.dataset, args.k, use_router=not args.no_router, out_path=args.out)
