# OncoRag — Cancer Knowledge Retrieval

A production-shaped Retrieval-Augmented Generation (RAG) system that answers oncology questions by grounding LLM responses in real medical source documents (WHO/NCI-style cancer fact sheets), instead of letting the model hallucinate. It ships as a full-stack service: a structure-aware PDF ingestion pipeline, a multi-document retrieval + routing engine, a Django REST API, a Dockerized deployment, and a from-scratch RAG evaluation harness.

I built this to go deep on the kind of problem a small, senior-heavy engineering team actually hits when they build software around imaging/document-heavy medical workflows: **the naive version is easy, the correct version requires understanding the whole system.**

> Applying to: **Full Stack Engineering Intern, Morphle Labs Inc.** — a YC-backed digital pathology company building robotics-enabled cancer diagnostics (Robotome, Morpholens, Hemolens). This project is a deliberate proxy for that stack: Python/Django backend, API-first architecture, and domain data that's messy, structured, and high-stakes — much like the imaging/lab workflows Morphle's software sits on top of.

---

## Why this project, why this way

Most RAG tutorials chunk a PDF into fixed 500-character blobs and call it done. That throws away the one thing medical documents actually have going for them: **structure**. A WHO fact sheet's "Risk Factors" section and its "Prevention" section should never bleed into the same chunk — a chunk that mixes them is a chunk that misleads a downstream answer. So the first real engineering decision in this repo was: **don't tokenize the document, parse it.**

That single decision cascades through the whole system and is the throughline of everything below.

---

## What it does

1. **Ingests** 7 cancer-topic PDFs (breast, cervical, childhood, colorectal, HPV, lung, general) and parses each one into heading-scoped sections instead of blind text chunks.
2. **Embeds** each section-aware chunk via OpenRouter (`text-embedding-3-small`) and caches the vectors to disk per source file, so re-runs never re-pay for embeddings they already have.
3. **Routes** an incoming question to the single most relevant source document using an LLM classifier — so retrieval searches one focused knowledge base instead of diluting similarity search across every topic at once.
4. **Retrieves** the top-k most relevant chunks via cosine similarity and **generates** a grounded answer, explicitly instructed to say "not in context" rather than invent an answer — critical in a medical domain where a wrong confident answer is worse than no answer.
5. **Serves** all of this over a Django REST API (`/api/health`, `/api/topics`, `/api/query`) built for a decoupled frontend, containerized and deploy-ready for AWS (App Runner / ECS Fargate + ALB).
6. **Evaluates itself** — a custom harness scores Recall@k, Precision@k, MRR against hand-labeled relevant chunks, plus two label-free LLM-judged metrics (faithfulness and answer relevance) to catch hallucination and off-topic drift, and recommends the best `top_k` automatically.

---

## Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │              data/*.pdf (7 topics)           │
                    └───────────────────────┬───────────────────────┘
                                             ▼
                    ┌─────────────────────────────────────────────┐
                    │  pdf_preprocessor.py                          │
                    │  PyMuPDF → font-aware line extraction         │
                    │  → heading classification → section grouping  │
                    │  → section-scoped chunking (context-preserving)│
                    └───────────────────────┬───────────────────────┘
                                             ▼
                    ┌─────────────────────────────────────────────┐
                    │  knowledgebase/embeddings.py + embed_cache.py │
                    │  OpenRouter batch embeddings → cache/*.json   │
                    │  (per-topic cache, never re-embeds on re-run) │
                    └───────────────────────┬───────────────────────┘
                                             ▼
          ┌───────────────────────────────────────────────────────────┐
          │  knowledgebase/multi_doc.py (topic manifest)                 │
          │  knowledgebase/router.py   (LLM picks ONE topic per query)   │
          │  knowledgebase/retrieval.py (cosine top-k within that topic) │
          └───────────────────────────────┬───────────────────────────┘
                                             ▼
                    ┌─────────────────────────────────────────────┐
                    │  helper.py: build_prompt() + generate_answer()│
                    │  Context-grounded generation via OpenRouter   │
                    └───────────────────────┬───────────────────────┘
                                             ▼
          ┌────────────────┐      ┌──────────────────────┐
          │  CLI            │      │  Django REST API      │
          │  run_rag.py     │      │  rag_api/ + config/    │
          │  run_rag_router │      │  /health /topics /query│
          └────────────────┘      └──────────────────────┘
                                             │
                                             ▼
                              ┌───────────────────────────┐
                              │  eval_retriever.py          │
                              │  Recall/Precision/MRR        │
                              │  + LLM-judged faithfulness   │
                              │  + answer relevance          │
                              │  → suggests optimal top_k    │
                              └───────────────────────────┘
```

---

## Engineering decisions worth a recruiter's five minutes

### 1. Structure-aware PDF parsing, not naive chunking (`pdf_preprocessor.py`)
Extracts every text line via PyMuPDF along with font size and weight, then classifies headings using a **size-ratio threshold** (1.3× the document's modal body size) rather than a fixed point size — because "big enough to be a heading" is relative to each document's own typography, not a magic number. Bold-but-body-sized emphasis text (e.g. *"lung (2.6 million cases)"*) is explicitly excluded so it isn't misclassified as a section header. A second pass detects and discards **runs of consecutive same-style lines** — i.e. bulleted lists rendered in a heading-like font — which would otherwise flood the section list with false headings. Chunks are built *within* a section (never spanning a boundary) and the heading is prepended to every chunk, so a chunk retrieved in isolation still carries its topical context.

### 2. Retrieval-scoped routing, not brute-force search over everything (`knowledgebase/router.py`)
Rather than embedding a query and searching across all 7 documents' vectors at once (slower, noisier — a lung cancer chunk can look deceptively similar to a colorectal cancer query), an LLM first classifies which single topic file the question belongs to. The router doesn't trust the LLM's output blindly — it falls back to case-insensitive and substring matching before raising, since LLMs occasionally add stray punctuation or wrapper text to an otherwise-correct answer.

### 3. A real evaluation harness, not "it looks right to me" (`eval_retriever.py`, `evaluation/`)
This is the part most side projects skip entirely. The harness:
- Computes **Recall@k / Precision@k / MRR** against a hand-labeled dataset of query → relevant-chunk-id pairs.
- Computes **Faithfulness** with no labels needed at all: an LLM judge decomposes the generated answer into atomic factual claims, then checks each claim against the retrieved context individually — catching hallucination at the claim level, not just eyeballing the paragraph.
- Computes **Answer Relevance**: reverse-generates questions from the answer and cosine-compares them to the original query, catching answers that are technically grounded but have wandered off-topic or gone generic.
- Sweeps multiple `top_k` values and recommends the best one, penalizing larger `k` for the added cost/latency/off-topic risk of extra context — with the reasoning printed, not just a number.
- Supports `--no-router` to isolate *retrieval quality* from *routing accuracy* — so when something's wrong, you know which of the two systems to fix first.

### 4. API-first, frontend-agnostic backend (`rag_api/`, `config/`)
The RAG pipeline is wrapped in a thin Django REST Framework service layer (`rag_api/services.py`) that mirrors the CLI pipeline exactly — so the web API and the CLI never drift apart in behavior. The embedding manifest is built **once per worker process** behind a thread lock (not once per request), and CORS is pre-wired for a decoupled React frontend — the same separation-of-concerns Morphle's own stack uses (React.js frontend + Django/Python backend + REST APIs).

### 5. Deploy-ready from day one
Dockerfile with a non-root user, health-checked container, `entrypoint.sh` running migrations + gunicorn, `docker-compose.yml` with host-mounted cache/data volumes for fast local iteration, and a deployment README covering AWS App Runner and ECS Fargate, including operational gotchas (e.g. why `GUNICORN_WORKERS=1` on small tasks avoids duplicate embedding calls on cold start).

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend framework | Django + Django REST Framework |
| PDF parsing | PyMuPDF (`fitz`) — font/layout-aware, not OCR |
| Embeddings & generation | OpenRouter (`text-embedding-3-small`, `upstage/solar-pro4`) |
| Similarity search | NumPy cosine similarity (brute-force, no vector DB — deliberate for this corpus size) |
| Serving | Gunicorn, WhiteNoise for static, CORS via `django-cors-headers` |
| Packaging | `uv` / `pyproject.toml` + pinned `requirements.txt` for Docker |
| Deployment | Docker, docker-compose, AWS App Runner / ECS Fargate |
| Evaluation | Custom-built — Recall/Precision/MRR + LLM-as-judge faithfulness & relevance |

---

## Repo tour

```
├── pdf_preprocessor.py       # Structure-aware PDF → section-scoped chunks
├── helper.py                  # Prompt building + generation + core retrieval primitives
├── run_rag.py                 # CLI: single-PDF pipeline
├── run_rag_router.py          # CLI: multi-doc pipeline with topic routing
├── eval_retriever.py          # Retrieval + generation quality evaluation sweep
│
├── knowledgebase/              # Core RAG engine (Django app)
│   ├── embeddings.py             # OpenRouter embedding calls (single source of truth)
│   ├── embed_cache.py            # Disk-cached embeddings, no redundant API calls
│   ├── multi_doc.py              # Per-topic manifest + cache-path management
│   ├── router.py                  # LLM-based topic classification
│   └── retrieval.py               # Cosine similarity top-k retrieval
│
├── rag_api/                    # Django REST API (Django app)
│   ├── services.py                # Thin service layer over the RAG pipeline
│   ├── views.py                   # /health /topics /query endpoints
│   └── urls.py
│
├── evaluation/                 # Evaluation harness
│   ├── metrics.py                 # Recall@k, Precision@k, MRR
│   ├── judge.py                   # LLM-judged faithfulness & answer relevance
│   └── list_chunks.py             # CLI to inspect cached chunks for labeling
│
├── config/                     # Django project settings, URLs, WSGI/ASGI
├── data/                       # Source PDFs (7 cancer topics)
├── cache/                      # Per-topic embedding caches (JSON)
├── Dockerfile / docker-compose.yml / entrypoint.sh
└── README_DEPLOY.md / EVAL_README.md   # Deep-dive docs for deployment & evaluation
```

---

## Running it locally

```bash
# 1. Install deps
uv sync   # or: pip install -r requirements.txt

# 2. Set your API key
cp .env.example .env   # fill in OPENROUTER_API_KEY

# 3. Ask a question via CLI (auto-routes to the right topic file)
uv run python run_rag_router.py "What are the risk factors for lung cancer?"

# 4. Or run the full web API
docker compose up --build
curl -X POST http://localhost:8000/api/query/ \
  -H "Content-Type: application/json" \
  -d '{"query": "How is breast cancer typically diagnosed?"}'

# 5. Evaluate retrieval/generation quality
uv run python eval_retriever.py evaluation/dataset.json --k 1 3 5 7

