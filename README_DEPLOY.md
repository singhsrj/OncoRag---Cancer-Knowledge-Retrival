# OncoRag web server — where these files go & how to deploy

## 1. Drop-in location
Copy everything in this bundle into the **root of your existing repo**, i.e.
next to `manage.py`, `helper.py`, `knowledgebase/`, `data/`, `cache/`:

```
OncoRag---Cancer-Knowledge-Retrival/
├── config/              <- settings.py / urls.py / wsgi.py / asgi.py (this bundle)
├── rag_api/             <- the new Django app (this bundle)
├── knowledgebase/        (already exists — untouched)
├── data/                 (already exists — your 7 PDFs)
├── cache/                (already exists — per-file embedding cache)
├── helper.py             (already exists — untouched)
├── pdf_preprocessor.py   (already exists — untouched)
├── run_rag_router.py     (already exists — untouched, CLI still works)
├── manage.py             (already exists)
├── Dockerfile            (this bundle)
├── requirements.txt      (this bundle)
├── entrypoint.sh
├── .dockerignore
├── .env.example
└── docker-compose.yml
```

If `config/` already has content from an earlier `django-admin startproject`,
merge in: `INSTALLED_APPS` (add `rest_framework`, `corsheaders`, `rag_api`),
the `corsheaders` middleware, `CORS_ALLOWED_ORIGINS`, and `ROOT_URLCONF`.

## 2. API surface
- `GET  /api/health/` → `{"status": "ok"}` — for the ALB/ECS/App Runner health check
- `GET  /api/topics/` → `{"topics": ["lung_cancer", "breast_cancer", ...]}`
- `POST /api/query/`  → body `{"query": "...", "top_k": 3}` →
  `{"query", "topic", "answer", "sources": [{"section","source","page"}]}`

The first request that needs the manifest (`/topics/` or `/query/`) builds
and embeds any not-yet-cached `data/*_cancer*.pdf` files exactly like
`run_rag_router.py` does — after that it's cached in memory for the life of
the worker process, and on disk under `cache/` across restarts.

## 3. Local test
```bash
cp .env.example .env   # fill in OPENROUTER_API_KEY at minimum
docker compose up --build
curl http://localhost:8000/api/health/
curl -X POST http://localhost:8000/api/query/ \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the risk factors for lung cancer?"}'
```

## 4. Ship to AWS
**Build & push to ECR:**
```bash
aws ecr create-repository --repository-name oncorag-api
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker build -t oncorag-api .
docker tag oncorag-api:latest <account>.dkr.ecr.<region>.amazonaws.com/oncorag-api:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/oncorag-api:latest
```

**Run it — pick one:**
- **AWS App Runner** (simplest): point it at the ECR image, set port `8000`,
  add the env vars from `.env.example` as App Runner "Environment variables"
  (mark `OPENROUTER_API_KEY`/`DJANGO_SECRET_KEY` as secrets via Secrets Manager),
  health check path `/api/health/`.
- **ECS Fargate**: task def with this image, container port 8000, ALB target
  group health check `/api/health/`, env vars from Secrets Manager/SSM.

**Bake in the data + cache** so the container doesn't need to call the
embedding API on every fresh deploy: commit `data/*.pdf` and, once you've run
it once, the generated `cache/*.json` files, so `COPY . .` in the Dockerfile
picks them up. If you'd rather not commit the cache, mount an EFS volume at
`/app/cache` on ECS so it persists across deployments/restarts.

**Set `GUNICORN_WORKERS=1`** on the smallest task size if the embedding
manifest build is slow — each worker builds it independently on first use,
so with `>1` you may briefly duplicate embedding calls.

**CORS**: set `CORS_ALLOWED_ORIGINS` to wherever the React app ends up
(CloudFront/S3, Amplify, or its own ECS service).
