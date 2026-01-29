# PROMPTS.md — Codex CLI Prompts + Commands (Month 1)

## How to use this file
1) Create a new repo (GitHub) and clone it to your LG laptop.
2) Add `SPEC.md` (already created), this `PROMPTS.md`, and `ARCHITECTURE.md` to the repo root.
3) Run Codex CLI in the repo root, and paste prompts below.

> Important: Generate code in small chunks. After each prompt, run the commands in “Verification”.

---

## Prerequisites (one-time on Windows)
Install:
- Git
- Node.js LTS
- Python 3.11+
- Docker Desktop
- Cursor
- Codex CLI (`npm i -g @openai/codex`)

---

## Repo layout (target)
/
  SPEC.md
  ARCHITECTURE.md
  PROMPTS.md
  apps/
    web/                 # Next.js (TypeScript)
    mobile/              # Expo (TypeScript) [Month 5]
  services/
    api/                 # FastAPI (Python)
  packages/
    shared/              # shared types, validators (optional)
  infra/
    docker-compose.yml
    env/
      .env.example
  README.md

---

## Prompt 1 — Create the monorepo scaffold
Paste into Codex CLI:

**PROMPT**
You are an expert full-stack engineer. Read SPEC.md and ARCHITECTURE.md carefully.
Create a monorepo with:
- apps/web: Next.js + TypeScript + minimal Tailwind setup
- services/api: FastAPI (Python 3.11+) with /health endpoint returning JSON { "status": "ok" }
- infra/docker-compose.yml running Postgres and Redis for local dev
- infra/env/.env.example including DB_URL, REDIS_URL, GCS_BUCKET (placeholder), and any required app secrets placeholders
- A root README.md with exact Windows commands to run web + api + docker services.

Rules:
- Keep dependencies minimal.
- Use pnpm if available; otherwise npm. Document which is used.
- Do not implement auth yet. Just create a landing page and a dashboard placeholder page.
- Ensure linting/format scripts exist for web and api.
- Ensure API reads DB_URL from environment but does not require DB to start for /health.

Deliver code only. Do not include explanations.

---

## Verification (after Prompt 1)
In a terminal:

```bash
cd infra
docker compose up -d

Read SPEC.md and ARCHITECTURE.md.

In services/api, add:
- A clean project structure: app/, routers/, models/, db/, schemas/, services/
- A DB connection helper using SQLAlchemy with Postgres URL from DB_URL
- Alembic migrations configured (but no migrations yet)
- A `/ready` endpoint that checks DB connectivity and returns:
  - `{ "status": "ok" }` when DB is reachable
  - `{ "status": "degraded", "reason": "<error>" }` when not

Rules:
- `/health` must NOT depend on the database
- `/ready` must test the database
- Use SQLAlchemy 2.0 style
- Use environment variables only
- Keep things minimal and readable
- Ensure everything works on Windows 11

Add concise documentation to `services/api/README.md` explaining:
- how to run the API
- how to run Alembic migrations locally

Return code changes only.

