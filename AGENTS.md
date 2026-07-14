# AGENTS.md

Compact guidance for OpenCode sessions working in this repo. Read alongside `docs/` (see _Start here_).

## Start here

`docs/context.md` is the canonical "live state" doc — read it first and **update it at the end of every session** (sections _Estado atual_ and _Próximo passo imediato_). Then read `docs/architecture.md` and `docs/business-rules.md`. For _why_ something is the way it is, consult `docs/decisions.md` before proposing changes. All docs are in Portuguese.

## Environment & secrets

- `.env` is **gitignored**; never commit `.env` / `.env.*` / API keys. **Never echo or paste secret values** into code, commits, docs, or chat output. Reference config by env var name only.
- Ask the user before installing new dependencies.

## Where things live

- `services/workers/` — Python async lead-prospection workers (Fase 1 ✅).
- `apps/web/` — Next.js frontend (Fase 2 🟡 em andamento).
- `docs/` — documentação do projeto (context, architecture, business-rules, interface, decisions).

## Run the worker

Always **cd into `services/workers/` first**. This is required: `src/config/settings.py` loads `.env` via a relative `env_file='../../.env'`, and the service modules import `from config.settings import settings`, which only resolves because `src/main.py` prepends `src/` to `sys.path`.

```bash
cd services/workers
source venv/bin/activate
python -m src.main                  # runs run_lead_enrichment_and_scoring(limit=5)
```

`__main__` runs enrichment+scoring only. `run_lead_collection(query, ...)` is a separate `async` function — invoke it from a script or REPL, not via `python -m src.main`.

## Run the frontend

```bash
cd apps/web
npm run dev                          # http://localhost:3001
```

Requires `.env` with JWT_SECRET and `NEXT_PUBLIC_API_URL` for API to work.

## Database / Alembic

Run alembic from `services/workers/`. `env.py` pulls the URL from `settings.DATABASE_URL`.

```bash
cd services/workers
alembic upgrade head
alembic revision --autogenerate -m "..."
```

- Never edit existing migrations — create a new one.
- Never drop columns in prod — mark deprecated first.

Docker provides Postgres + pgAdmin: `docker compose up -d` (db on :5432, pgAdmin on :5050).

## Conventions that matter

- **All async** in workers: `httpx.AsyncClient`, no `requests`, no sync service funcs.
- **SQLAlchemy filters**: use `&` / `|`, never Python `and` / `or`.
- **No `print`** in services — use `logging`.
- One `XService` class per file in `src/services/`. Services **do not import each other** — orchestration happens only in `src/main.py`.
- All config via `src/config/settings.py` (pydantic-settings). Never read `os.environ` directly in services.
- Frontend uses shadcn/ui (base-nova style) — uses `@base-ui/react`, not Radix. Use `render` prop instead of `asChild`.

## Scoring / business rules

Score 0–100; `>= 60` → `QUALIFICADO` (enters outreach), `< 60` → `DESQUALIFICADO`. Lead funnels: `NOVO → ANALISADO → QUALIFICADO/DESQUALIFICADO → CONTATADO → RESPONDIDO → REUNIAO_MARCADA` (or `PERDIDO`, which re-enters the queue after 90 days). Leads without a website stay `NOVO` and skip technical enrichment. All website analysis is **passive** — never probe, inject, test auth, or take non-passive actions (Lei 12.737/2012).
