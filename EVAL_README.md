# Retriever/generator evaluation

Drop `eval_retriever.py` and `evaluation/` into the repo root, next to
`run_rag_router.py` — no changes needed to `helper.py`, `knowledgebase/`,
or the Django web server.

## 1. Build a small labeled eval set (for Recall/Precision/MRR)
List the cached chunks for a topic so you can pick out the ones actually
relevant to a query you're going to test:

```bash
uv run python -m evaluation.list_chunks lung_cancer
```

Copy the `chunk_id`s you judge relevant into `evaluation/dataset.json`
(start from `evaluation/dataset.example.json`). Each entry:

```json
{
  "query": "What are the risk factors for lung cancer?",
  "topic": "lung_cancer",
  "relevant_chunk_ids": ["lung_cancer.pdf::Risk Factors::0", "..."]
}
```

`relevant_chunk_ids` is optional per item — leave it `[]` if you only want
faithfulness/answer-relevance (no labeling needed) for that query. Aim for
5–10 queries per topic covering a mix of narrow ("What stage is...") and
broad ("How is X treated?") questions — that's usually enough to see how
recall/precision move with k.

## 2. Run the sweep
```bash
uv run python eval_retriever.py evaluation/dataset.json --k 1 3 5 7 10
```

This runs your existing `classify_topic → retrieve → build_prompt → generate_answer`
pipeline once per query per k, and prints/saves:
- **Recall@k / Precision@k / MRR** — only for queries with `relevant_chunk_ids`
- **Faithfulness** — % of the answer's claims an LLM judge could verify against
  the retrieved chunks (catches hallucination)
- **Answer relevance** — cosine similarity between your query and questions
  an LLM judge reverse-generates from the answer (catches off-topic/generic answers)
- A suggested `top_k` (recall + faithfulness + relevance, lightly penalized
  for pulling in more context than needed)

Full per-query results land in `evaluation/results.json`.

## 3. Isolate retrieval from routing (optional)
If recall looks bad, first check whether it's the router or the retriever
at fault:
```bash
uv run python eval_retriever.py evaluation/dataset.json --no-router
```
This forces each query to use its labeled `topic` instead of calling
`classify_topic`, so a drop in recall here means it's `retrieve()`/chunking,
not routing.

## 4. Lock in the winner
Once you've picked a `top_k`, set it as the default the web server uses:
```
RAG_DEFAULT_TOP_K=<chosen k>   # in .env
```
(`rag_api/views.py` already reads `top_k` from the request body with `3` as
the fallback if the frontend doesn't send one — bump that fallback to match,
or wire it to `settings.RAG_DEFAULT_TOP_K` if you want it centralized.)

## Cost note
Faithfulness and answer-relevance both make a handful of extra OpenRouter
calls per query per k (claim extraction + per-claim verification, plus
question generation + embeddings). For a 10-query set × 4 k-values that's a
few hundred small calls — fine for a one-off tuning run, but don't wire this
into CI on every commit without thinking about cost/rate limits first.
