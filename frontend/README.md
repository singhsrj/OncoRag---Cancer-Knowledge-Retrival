# OncoRag Frontend

A minimal React (Vite) client for the OncoRag Django API. Lets you pick a
sample question or type your own, shows which topic file the router chose,
and displays the answer alongside the retrieved source sections.

## Run it

```bash
npm install
cp .env.example .env    # point VITE_API_BASE at your Django server if not localhost:8000
npm run dev
```

Opens on `http://localhost:3000` (change in `vite.config.js` if needed) —
this matches the default `CORS_ALLOWED_ORIGINS` already set in the
Django backend's `config/settings.py`, so no backend changes are required.

Make sure the Django API is running first:

```bash
# from the backend repo root
python manage.py runserver
```

## What it calls

- `GET  /api/topics/` — populates the "Knowledge base" list on load
- `POST /api/query/`  — body `{ "query": "...", "top_k": 3 }`, on submit

## Build for production

```bash
npm run build   # outputs to dist/
```

Deploy `dist/` to any static host (Netlify, S3+CloudFront, Amplify) and set
`CORS_ALLOWED_ORIGINS` on the Django side to that host's origin.
