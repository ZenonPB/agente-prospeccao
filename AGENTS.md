# AGENTS.md

Compact guidance for OpenCode sessions working in this repo. Read alongside `docs/` (see _Start here_).

## Start here

**Always read the knowledge graph first** (`graphify-out/graph.json` + `graphify-out/GRAPH_REPORT.md`) before any task — it provides the full project architecture, component relationships, and data flow in a structured format, saving significant tokens vs re-scanning the entire codebase. The graph has 758 nodes, 1554 edges, and 57 communities covering all layers (workers, API, frontend). Interactive HTML at `graphify-out/graph.html`.

`docs/context.md` is the canonical "live state" doc — read it first and **update it at the end of every session** (sections _Estado atual_ and _Próximo passo imediato_). Then read `docs/architecture.md` and `docs/business-rules.md`. For _why_ something is the way it is, consult `docs/decisions.md` before proposing changes. All docs are in Portuguese.

`docs/agents.md` has detailed agent rules (do's/don'ts). `apps/web/AGENTS.md` has Next.js-specific rules.

## Environment & secrets

- `.env` is **gitignored**; never commit `.env` / `.env.*` / API keys. **Never echo or paste secret values** into code, commits, docs, or chat output. Reference config by env var name only.
- Ask the user before installing new dependencies.
- Required vars: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_URL`, `PGADMIN_EMAIL`, `PGADMIN_PASSWORD`, `GROQ_API_KEY`, `GOOGLE_API_KEY`. API also needs `JWT_SECRET`. SMTP vars are optional. See `.env.example`.

## Where things live

- `services/workers/` — Python async lead-prospection workers (Fase 1 ✅).
- `services/api/` — FastAPI REST layer (Fase 1.5 ✅). Re-exports workers' models as single source of truth; imports worker services for pipeline execution.
- `apps/web/` — Next.js 16 + React 19 frontend (Fase 2 🟡 em andamento).
- `docs/` — documentação do projeto.

## Run the worker

Always **cd into `services/workers/` first**. This is required: `src/config/settings.py` loads `.env` via a relative `env_file='../../.env'`, and `src/main.py` prepends `src/` to `sys.path` for module resolution.

```bash
cd services/workers
python -m src.main                  # runs run_lead_enrichment_and_scoring(limit=5)
```

`__main__` runs enrichment+scoring only. `run_lead_collection(query, ...)` is a separate `async` function — invoke it from a script or REPL, not via `python -m src.main`.

**Note:** `playwright` is a dependency (used for technical enrichment). On Linux, you may need `playwright install chromium`.

## Run the API

```bash
cd services/api
python -m uvicorn main:app --host 0.0.0.0 --port 8000
# Swagger docs: http://localhost:8000/docs
```

Reuses worker models via re-export (`src/db/models.py` imports from workers). Pipeline streaming via WebSocket at `/ws/pipeline/{job_id}` with `?token=` auth.

## Run the frontend

```bash
cd apps/web
npm run dev                          # http://localhost:3001
npm run build
npm run lint                         # eslint (Next.js 16 config)
```

Requires `.env` with `JWT_SECRET` and `NEXT_PUBLIC_API_URL`. Uses shadcn/ui (`base-nova` style) with `@base-ui/react` (not Radix) — use `render` prop instead of `asChild`.

## Database / Alembic

Docker provides Postgres + pgAdmin: `docker compose up -d` (db on :5432, pgAdmin on :5050).

Run alembic from `services/workers/`. `migrations/env.py` pulls the URL from `settings.DATABASE_URL`.

```bash
cd services/workers
alembic upgrade head
alembic revision --autogenerate -m "..."
```

- Never edit existing migrations — create a new one.
- Never drop columns in prod — mark deprecated first.

### Seeds

```bash
cd services/workers
python -m src.seeds.scoring_templates    # populates campaign_scoring_templates (6 templates)
```

## Conventions that matter

- **All async** in workers: `httpx.AsyncClient`, no `requests`, no sync service funcs.
- **SQLAlchemy filters**: use `&` / `|`, never Python `and` / `or`.
- **No `print`** in services — use `logging`.
- One `XService` class per file in `services/workers/src/services/`. Individual services **do not import each other** — orchestration lives in `enrichment_orchestrator.py` (called by both `main.py` and `pipeline_worker.py`).
- All config via `src/config/settings.py` (pydantic-settings). Never read `os.environ` directly in services.
- Comments in **Portuguese**, minimal, only where necessary.
- Git commits follow conventional commits (`feat:`, `fix:`, `chore:`, `docs:`).

## Scoring / business rules

Score 0–100; `>= 60` → `QUALIFICADO` (enters outreach), `< 60` → `DESQUALIFICADO`. Lead funnels: `NOVO → ANALISADO → QUALIFICADO/DESQUALIFICADO → CONTATADO → RESPONDIDO → REUNIAO_MARCADA` (or `PERDIDO`, which re-enters the queue after 90 days). Leads without a website stay `NOVO` and skip technical enrichment. Scoring is **contextual per campaign** using `campaign_scoring_templates` — see `docs/business-rules.md`. All website analysis is **passive** — never probe, inject, test auth, or take non-passive actions (Lei 12.737/2012).
