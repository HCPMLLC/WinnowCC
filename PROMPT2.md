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
