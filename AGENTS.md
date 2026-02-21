# Repository Guidelines

## Project Structure & Module Organization
- `apps/web`: Next.js 14 frontend (`app/` routes, `globals.css`, Tailwind config).
- `services/api`: FastAPI backend (`app/` routers, services, models, schemas) with Alembic in `alembic/`.
- `infra`: Local infrastructure (`docker-compose.yml`) and example env files in `infra/env`.
- Top-level docs like `README.md`, `ARCHITECTURE.md`, and prompt specs live at repo root.

## Build, Test, and Development Commands
- `start-dev.ps1`: One-command startup (Docker, API, worker, web) in separate PowerShell windows.
- Infra: `cd infra; docker compose up -d` to start Postgres + Redis.
- API: `cd services/api; python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt -r requirements-dev.txt; uvicorn app.main:app --reload`.
- Web: `cd apps/web; npm install; npm run dev` for local frontend.
- Web build: `cd apps/web; npm run build` (Next.js production build).

## Coding Style & Naming Conventions
- Python: Ruff is the formatter/linter; line length 88 (`services/api/pyproject.toml`). Use `python -m ruff format .` and `python -m ruff check .`.
- TypeScript/Next.js: Prettier for formatting and `next lint` for linting (`apps/web/package.json`).
- File naming: Keep Next.js route folders lowercase (`app/login`, `app/matches`) and Python modules snake_case.

## Testing Guidelines
- API tests live in `services/api/tests` and run via pytest: `cd services/api; .\.venv\Scripts\Activate.ps1; .\scripts\test.ps1`.
- Web testing is not wired yet; Playwright is listed as a dev dependency, so add e2e tests under a `tests/` or `e2e/` folder if needed.

## Commit & Pull Request Guidelines
- Current Git history includes a single “Initial baseline …” commit, so no formal convention exists yet. Prefer imperative, scoped summaries (e.g., `api: add trust gating endpoints`).
- PRs should include: a short description, key commands run (e.g., `.\scripts\test.ps1`, `npm run lint`), and screenshots for UI changes (`apps/web`).

## Security & Configuration Tips
- Use the sample envs: `services/api/.env.example` and `infra/env/.env.example`.
- Keep `AUTH_SECRET` stable across restarts to preserve sessions; set `AUTH_COOKIE_NAME` explicitly when testing auth.
