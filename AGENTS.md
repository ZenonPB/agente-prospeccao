# AGENTS.md

Compact guidance for OpenCode sessions working in this repo. Read alongside `docs/` (see _Start here_).

## Start here

`docs/context.md` is the canonical "live state" doc — read it first and **update it at the end of every session** (sections _Estado atual_ and _Próximo passo imediato_). Then read `docs/architecture.md` and `docs/business-rules.md`. For _why_ something is the way it is, consult `docs/decisions.md` and `docs/decisions/` before proposing changes. All docs are in Portuguese.

`CLAUDE.MD` is a pointer doc that just redirects to the same `docs/` files — no need to reconcile its content.

## Environment & secrets

- `.env` is **gitignored**; the working tree currently holds real-looking values (live Google API key, DB password). Never commit `.env` / `.env.*` / API keys. **Never echo or paste secret values** into code, commits, docs, or chat output. Reference config by env var name only.
- Ask the user before installing new dependencies.

## Where things live

- `services/workers/` — the only real app. Python async lead-prospection workers.
- `apps/web/` — placeholder for the future Next.js frontend; currently **empty**. Don't assume it exists.
- No tests, lint config, typecheck config, CI, Makefile, or package.json exist yet. Don't invent commands.

## Run the worker

Always **cd into `services/workers/` first**. This is required: `src/config/settings.py` loads `.env` via a relative `env_file='../../.env'`, and the service modules import `from config.settings import settings`, which only resolves because `src/main.py` prepends `src/` to `sys.path`.

```bash
cd services/workers
source venv/bin/activate            # venv exists; deps in requirements.txt
python -m src.main                  # runs run_lead_enrichment_and_scoring(limit=5)
```

`__main__` runs enrichment+scoring only. `run_lead_collection(query, ...)` is a separate `async` function — invoke it from a script or REPL, not via `python -m src.main`.

Enrichment can also be run standalone for testing: `python -m src.services.technical_enrichment_service` (it has a `__main__` against `https://www.google.com`).

## Database / Alembic

Run alembic from `services/workers/` (so `prepend_sys_path = .` and `env.py`'s `from src...` imports resolve). `env.py` pulls the URL from `settings.DATABASE_URL`, so `sqlalchemy.url` in `alembic.ini` is intentionally unset — don't add it.

```bash
cd services/workers
alembic upgrade head
alembic revision --autogenerate -m "..."
```

- Never edit existing migrations — create a new one.
- Never drop columns in prod — mark deprecated first.

Docker provides Postgres + pgAdmin: `docker compose up -d` (db on :5432, pgAdmin on :5050). The `db` service has a healthcheck; pgAdmin depends on it.

## Conventions that matter (differ from defaults)

- **All async**: `httpx.AsyncClient`, no `requests`, no sync service funcs. (Note: `LeadStatus` enums in `models.py` use legacy `declarative_base` and `session.py` uses a sync `create_engine`/`SessionLocal` — async-not-yet-applied to the DB layer.)
- **SQLAlchemy filters**: use `&` / `|`, never Python `and` / `or`. (There's a known bug doing the wrong thing at `src/main.py:37` — `Lead.company_name == company_name and Lead.website == website_url` evaluates in Python, not SQL.)
- **No `print`** in services — use `logging`. (`main.py` currently uses `print`; treat as pending cleanup.)
- One `XService` class per file in `src/services/`. Services **do not import each other** — orchestration happens only in `src/main.py`. Services return `None` on failure, never raise to the caller.
- All config via `src/config/settings.py` (pydantic-settings). Never read `os.environ` directly in services.

## Known pending work (verify in `docs/context.md` before acting)

- `src/services/places_service.py`: `search_places` is sync (`httpx.Client`), but `main.py` awaits it — needs to become async.
- `TechnicalEnrichmentService` instantiates `httpx.AsyncClient` in `__init__` — should be created per-use / via `async with`.
- `scoring_service.py` (`AIScoringService`, Groq `llama-3.1-8b-instant`) is **not yet created**; `main.py` has a TODO at line 75. Scoring is not wired into `run_lead_enrichment_and_scoring`.
- `src/services/ai_service.py` and `src/tasks/lead_processing_task.py` exist but are empty placeholders.

## Scoring / business rules (cross-cutting)

Score 0–100; `>= 60` → `QUALIFICADO` (enters outreach), `< 60` → `DESQUALIFICADO`. Lead funnels: `NOVO → ANALISADO → QUALIFICADO/DESQUALIFICADO → CONTATADO → RESPONDIDO → REUNIAO_MARCADA` (or `PERDIDO`, which re-enters the queue after 90 days). Leads without a website stay `NOVO` and skip technical enrichment. All website analysis is **passive** — never probe, inject, test auth, or take non-passive actions (Lei 12.737/2012).
