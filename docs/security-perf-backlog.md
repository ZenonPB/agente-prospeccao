# Backlog de Segurança e Performance

Auditoria completa realizada em 2026-08-31. Este arquivo rastreia os itens
pendentes — os CRITICALs já foram corrigidos no branch
`feat/security-perf-highs` e mergeados.

---

## Concluídos

- [x] **Open Redirect** no tracking — validação de URL contra IPs privados
  (`tracking.py`)
- [x] **Timing attack** no webhook secret — `hmac.compare_digest`
  (`webhooks.py`)
- [x] **lead_stats N+1** → GROUP BY (`leads.py`)
- [x] **metrics N+1** → GROUP BY (`metrics.py`)
- [x] **get_lead_duplicates N+1** → batch contacts (`leads.py`)
- [x] **Pool de conexões** não configurado → `pool_size=3, max_overflow=5,
  pool_pre_ping=True` (`session.py`)
- [x] **SMTP timeout** 30s → 10s (`email_service.py`)
- [x] **WeasyPrint síncrono** → `asyncio.to_thread` (`analytics.py`)
- [x] **9 índices novos** — migration `f8e9d0c1b2a3`
- [x] **CRM selection de abas** — SheetJS + criação de nova aba

---

## HIGH — Segurança (próximo lote)

### H-S1: Desabilitar Swagger/OpenAPI em produção
- **Arquivo:** `services/api/main.py` (~linha 200)
- **Problema:** `/docs` expõe schema completo da API sem autenticação.
- **Fix:** `FastAPI(..., docs_url=None, redoc_url=None, openapi_url=None)`
  quando `ENVIRONMENT == "production"`.
- **Esforço:** 3 linhas.

### H-S2: Restringir CORS methods e headers
- **Arquivo:** `services/api/main.py` (~linha 218)
- **Problema:** `allow_methods=["*"]` + `allow_headers=["*"]` expanded
  attack surface.
- **Fix:** `allow_methods=["GET","POST","PATCH","DELETE","OPTIONS"]` +
  `allow_headers=["Authorization","Content-Type","X-Organization-Id"]`.
- **Esforço:** 2 linhas.

### H-S3: Limite de tamanho no upload CRM
- **Arquivo:** `services/api/src/routes/crm.py` (~linha 72)
- **Problema:** `file.read()` sem limite —DoS por memória.
- **Fix:** Validar `file.size` antes de ler (máx 10MB) + validar magic
  bytes `PK\x03\x04` (xlsx/zip).
- **Esforço:** ~10 linhas.

### H-S4: Redatar email no invite check
- **Arquivo:** `services/api/src/routes/invites.py` (~linha 231)
- **Problema:** `GET /api/invites/check` retorna email completo sem auth.
- **Fix:** Retornar `u***@dominio.com` para chamadas não autenticadas.
- **Esforço:** ~5 linhas.

### H-S5: Rate limit no webhook import
- **Arquivo:** `services/api/src/routes/webhooks.py` (~linha 73)
- **Problema:** `POST /api/webhooks/import` sem rate limit — flooding
  de leads se secret vazar.
- **Fix:** `@limiter.limit("10/minute")` no endpoint.
- **Esforço:** 1 linha.

---

## MEDIUM — Segurança

### M-S1: Security headers middleware
- **Arquivo:** `services/api/main.py`
- **Problema:** Sem HSTS, X-Frame-Options, CSP, X-Content-Type-Options.
- **Fix:** Middleware customizado que injeta headers de segurança.
- **Esforço:** ~20 linhas.

### M-S2: HTTPS enforcement
- **Arquivo:** `services/api/main.py`
- **Problema:** Sem redirect HTTP→HTTPS nem HSTS.
- **Fix:** Middleware de redirect + header HSTS.
- **Esforço:** ~15 linhas.

### M-S3: CORS origins hardcoded com localhost
- **Arquivo:** `services/api/src/config/settings.py` (~linha 53)
- **Problema:** Default inclui `localhost:3000/3001` que pode vazar em prod.
- **Fix:** Assertion no startup quando `ENVIRONMENT=production` rejeita
  origins com localhost.
- **Esforço:** ~5 linhas.

### M-S4: JWT sem claims `iss`/`aud`
- **Arquivo:** `services/api/src/auth/security.py` (~linha 29)
- **Problema:** Tokens reutilizáveis entre ambientes/serviços.
- **Fix:** Adicionar `iss` e `aud` na criação e validação.
- **Esforço:** ~10 linhas.

### M-S5: Reset token não invalidado no change_password
- **Arquivo:** `services/api/src/routes/auth.py` (~linha 170)
- **Problema:** Token de reset permanece válido após troca de senha.
- **Fix:** Adicionar `current_user.reset_token = None` +
  `current_user.reset_token_expires = None`.
- **Esforço:** 2 linhas.

### M-S6: Health check vaza environment
- **Arquivo:** `services/api/main.py` (~linha 265)
- **Problema:** `/health` retorna `ENVIRONMENT` para qualquer caller.
- **Fix:** Remover campo `environment` da resposta.
- **Esforço:** 1 linha.

### M-S7: Inbound email cross-org match
- **Arquivo:** `services/api/src/services/inbound_email_service.py`
  (~linha 95)
- **Problema:** Match de leads por email cruza organizações.
- **Fix:** Escopar query por organization_id (via domínio do remetente
  ou header do webhook).
- **Esforço:** ~15 linhas.

### M-S8: Sem account lockout no login
- **Arquivo:** `services/api/src/routes/auth.py` (~linha 102)
- **Problema:** Rate limit 10/min/IP não impede distributed brute-force.
- **Fix:** Lockout após N tentativas falhas (5 = 15min) + log de tentativas.
- **Esforço:** ~30 linhas.

---

## HIGH — Performance (restantes)

### H-P1: Analytics `overview()` faz 15+ queries
- **Arquivo:** `services/api/src/services/analytics_service.py`
  (~linha 158)
- **Problema:** 10 COUNTs separados + subqueries de score band.
- **Fix:** Consolidar em 2-3 GROUP BY queries + CASE WHEN para score
  bands.
- **Esforço:** ~40 linhas.

### H-P2: Lead list lazy load de company/person (N+1)
- **Arquivo:** `services/api/src/routes/leads.py` (~linha 323)
- **Problema:** Acessa `lead.company.company_name` e
  `lead.primary_person.name` sem eager loading — 50 leads = 100 queries.
- **Fix:** Adicionar `joinedload(Lead.company),
  joinedload(Lead.primary_person)` na query.
- **Esforço:** 2 linhas.

### H-P3: CSV import carrega todos os leads para dedup
- **Arquivo:** `services/api/src/services/csv_import_service.py`
  (~linha 198)
- **Problema:** Carrega ALL leads da org em memória para dedup.
- **Fix:** Usar colunas específicas (website, normalized_domain, cnpj,
  place_id) ou query-targeted.
- **Esforço:** ~15 linhas.

### H-P4: Webhook outbound cria httpx.Client por request
- **Arquivo:** `services/api/src/services/webhook_outbound_service.py`
  (~linha 72)
- **Problema:** Cada retry instancia novo client (4x por webhook).
- **Fix:** Client singleton com connection pooling.
- **Esforço:** ~10 linhas.

---

## MEDIUM — Performance (restantes)

### M-P1: `_follow_up_dict` queries individuais por tracking token
- **Arquivo:** `services/api/src/routes/leads.py` (~linha 1220)
- **Problema:** 4 follow-ups = 4 queries extras por cadence view.
- **Fix:** Batch prefetch de tracking tokens antes do loop.
- **Esforço:** ~15 linhas.

### M-P2: `send_step` re-query Lead e Organization
- **Arquivo:** `services/api/src/services/cadence_service.py`
  (~linha 168, 204)
- **Problema:** Queries redundantes quando objetos já disponíveis.
- **Fix:** Usar `follow_up.lead` relationship e passar `org` como
  parâmetro.
- **Esforço:** ~10 linhas.

### M-P3: Campaign export N+1 em contacts
- **Arquivo:** `services/api/src/routes/campaigns.py` (~linha 616)
- **Problema:** Lazy load de `lead.contacts` em loop.
- **Fix:** `joinedload(Lead.contacts)` ou batch query.
- **Esforço:** ~5 linhas.

### M-P4: Large JSONB payloads no lead detail
- **Arquivo:** `services/api/src/routes/leads.py` (~linha 189)
- **Problema:** `raw_technical_data`, `score_factors`, `evidence` em
  toda resposta de detail.
- **Fix:** Lazy-load via query param `?include=raw_data`.
- **Esforço:** ~20 linhas.
