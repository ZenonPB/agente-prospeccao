# AGENTS.md

Compact guidance for OpenCode sessions working in this repo. Read alongside `docs/` (see _Start here_). All project docs are in Portuguese.

## Start here

- **Use the knowledge graph first** (`graphify-out/graph.json`, gitignored — build it with `graphify extract . --code-only && graphify cluster-only . --no-label` if missing). Query it instead of grepping files: `graphify query "<question>"`, `graphify path "A" "B"`, `graphify explain "X"` (CLI installed via `python -m venv /tmp/opencode/graphify-venv && .../bin/pip install graphifyy`). Fall back to `docs/` when the graph is stale or absent.
- `docs/context.md` is the canonical "live state" doc — read it first and **update it at the end of every session** (_Estado atual_ and _Próximo passo imediato_).
- Then `docs/architecture.md` and `docs/business-rules.md`. For _why_ something is the way it is, consult `docs/decisions.md` before proposing changes.
- Load specialized skills with the `skill` tool before writing code: `frontend-design` & `vercel-react-best-practices` for `apps/web` work.
- `apps/web/AGENTS.md` carries package-specific rules — check it before editing that package.

## Environment & secrets

- `.env` (repo root) is **gitignored** and shared by both Python services via a CWD-relative `env_file='../../.env'`. Never commit or echo secret values — reference config by env var name only.
- `JWT_SECRET` is a required field in `services/api/src/config/settings.py` — the API won't start without it. It is documented in `.env.example`; generate with `openssl rand -hex 32`.
- Ask the user before installing new dependencies.

## Where things live

- `services/workers/` — Python async lead-prospection workers (Google Places collection, passive website enrichment, Groq scoring). Owns the single source of truth for DB models (`src/database/models.py`) and all Alembic migrations.
- `services/api/` — FastAPI REST API serving the web frontend (JWT auth, campaigns, leads, cadence scheduler, PDF). Re-exports worker models via `src/db/models.py` — no separate model definitions.
- `apps/web/` — Next.js 16 + React 19 frontend (shadcn/ui on `@base-ui/react`).
- `docs/` — project documentation (Portuguese).

## Run the API

```bash
cd services/api            # required: ../../.env resolves to repo root
uvicorn main:app --reload --port 8000   # http://localhost:8000/docs
```

- venv is gitignored — create it first if missing: `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`.
- Starts a background cadence scheduler (poll `CADENCE_POLL_SECONDS`, default 60s) that auto-sends due follow-ups for orgs with `auto_send_email` opt-in.
- CORS allows `http://localhost:3000` and `http://localhost:3001`.

## Run the workers

Must run from `services/workers/` for the same reason (relative `env_file='../../.env'`; `migrations/env.py` also imports `from src.config.settings import settings`).

```bash
cd services/workers
source venv/bin/activate              # gitignored — create with `python -m venv venv` if missing
python -m src.main                    # runs run_lead_enrichment_and_scoring(limit=5)
```

- `__main__` runs enrichment+scoring only. `run_lead_collection(query, ...)` is a separate `async` function — call it from a script or REPL, not via `python -m src.main`.
- Seed default scoring templates: `python -m src.seeds.scoring_templates` (idempotent).

## Run the frontend

```bash
cd apps/web
npm run dev                            # http://localhost:3001
```

- `NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000` in `src/lib/api.ts` — set it in `apps/web/.env.local` only if the API runs elsewhere.

## Database / Alembic

Run alembic from `services/workers/` (env.py pulls the URL from `settings.DATABASE_URL`).

```bash
cd services/workers
alembic upgrade head
alembic revision --autogenerate -m "..."
```

- Never edit existing migrations — create a new one.
- Never drop columns in prod — mark deprecated first.
- Docker provides Postgres + pgAdmin: `docker compose up -d` (db :5432, pgAdmin :5050). Both services expect `DATABASE_URL` from the root `.env`.

## Windows sem Docker (alternativa ao compose)

- `scripts/setup.ps1` (ou duplo clique em `scripts/setup.cmd`): setup completo e
  idempotente — usa um PostgreSQL já existente na porta 5432 ou baixa um
  **embarcado** (zonky), cria venvs, `.env`/`.env.local`, banco, migrations e seed.
- `scripts/dev.ps1 start|stop|status|restart` (ou `scripts/dev.cmd`): sobe
  Postgres/API/Web. Mesmas regras de `.env` e venvs dos comandos acima.

## Tests & verification

- Root-level `tests/` (pytest, unit-only, no DB needed). Install deps with `pip install -r requirements-dev.txt` (root) then run **from repo root**: `python -m pytest tests -q`. Neither service venv includes pytest by default.
- `tests/conftest.py` injects dummy env vars before imports and fixes `sys.path`: `services.*`, `database.*`, `config.*` → `services/workers/src`; `src.*` → API. This mapping mirrors runtime, so don't move it.
- CI (`.github/workflows/ci.yml`) is the verification order: web `npm run lint` → `npx tsc --noEmit` → `npm run build`; backend `python -m compileall -q services/api services/workers` + `python -m pytest tests -q`; migrations job runs `alembic upgrade head` + seed smoke against Postgres.
- For one-off Python verification not covered by tests, run the service directly (see run commands above).

## Conventions that matter

- **All async** in workers: `httpx.AsyncClient`, no `requests`, no sync service funcs.
- **SQLAlchemy filters**: use `&` / `|`, never Python `and` / `or`.
- **No `print`** in services — use `logging`.
- One `XService` class per file in `src/services/`. Cross-service imports are the exception, not the rule: `enrichment_orchestrator.py` wires `technical_enrichment_service` + `scoring_service`, and `contact_enrichment_service` lazily imports `cnpj_service`. Put new orchestration there or in `main.py`, not in sibling services.
- All config via `src/config/settings.py` (pydantic-settings). Never read `os.environ` directly in services.
- Frontend uses shadcn/ui with `@base-ui/react` (not Radix) — use the `render` prop instead of `asChild`.

## Scoring / business rules

Score 0–100; `>= 60` → `QUALIFICADO` (enters outreach), `< 60` → `DESQUALIFICADO`. Lead funnels: `NOVO → ANALISADO → QUALIFICADO/DESQUALIFICADO → CONTATADO → RESPONDIDO → REUNIAO_MARCADA → REUNIAO_FEITA → PROPOSTA_ENVIADA` (or `PERDIDO`). Leads **without a website skip technical enrichment but are still scored** via the business path (for web-presence campaigns they are the public-alvo — never disqualified just for lacking a site); on Groq failure they stay `NOVO` to be reprocessed. ⚠️ The rule "`PERDIDO` re-enters the queue after 90 days" is **documented but not yet implemented** (pending). All website analysis is **passive** — never probe, inject, test auth, or take non-passive actions (Lei 12.737/2012).
