# Auditoria Geral do Sistema — Vistoria 2026-08-04

> Vistoria geral feita antes da entrega à empresa. Objetivo: mapear o que está
> sólido, o que quebra em uso real e o que precisa melhorar antes do go-live
> de prospecção. Método: grafo de conhecimento (graphify), leitura das
> 4 docs canônicas e exploração de código em 4 frentes (prontidão de produção,
> eficácia de prospecção, saúde do frontend e arquitetura/API) + verificação
> manual dos achados críticos.
>
> Versão visual (com diagramas before/after): `architecture-review-agente-prospeccao.html`
> (gerada em /tmp na data da vistoria — não versionada).
>
> Status: este documento lista **pendências**, use como checklist de entrega.
>
> **Correção em andamento na branch `fix/go-live-prep` (2026-08-04).** Estado:
> - ✅ 2.1, 2.2, 2.3 (bloqueadores) · 3.2 · 3.3 · 3.6 · 3.7 · 3.8
> - ✅ 4.1 · 4.2 · 4.3 · 4.4 (backend) · 4.5 · 4.6 · 4.7 · 4.8 · 4.10 · 4.9 (parcial)
> - ✅ 5.2 (parcial) · 5.3 · 5.4 · 5.5 · 5.1 (módulo `provider_client` criado e
>   adotado em scoring/technical)
> - ⏳ 3.1 (feito no frontend; revisar) · 3.4 (Dockerfiles/compose/README/CSP feitos;
>   falta teste de build de imagem) · 3.5 (pytest + CI + backup criados; falta rodar
>   CI real) · 4.9 (falta paginação nas listas)
> - ✅ **Eixo 3 (2026-08-04)**: 4.4 (UI de notas/próxima ação/WhatsApp no lead),
>   kanban NOVO+QUALIFICADO, painel "Ações de hoje", ações em massa + export CSV,
>   botão WhatsApp wa.me. Detalhes em `docs/context.md`.
>
> - ✅ **Migrations validadas em Postgres real (2026-08-04)**: ao subir o ambiente
>   sem root, a migration `a5b6c7d8e9f0` (go-live 4.3, backfill de
>   `normalized_domain`) falhava com `UndefinedColumn: created_at` (coluna fora
>   do subselect do `DISTINCT ON`). Corrigida in-place (adicionar `created_at` ao
>   select interno) — nunca tinha sido aplicada em banco real. `alembic upgrade
>   head` e o seed de 9 templates agora rodam de ponta a ponta.

---

## 1. Estado geral

O roadmap 1.1–3.8 está entregue e a plataforma tem uma base sólida:

- Coleta multi-fonte (Places, CSV, CNAE), enriquecimento adaptativo, scoring
  contextual explicável (templates + router + geração sob demanda).
- Multi-tenant com isolamento cross-tenant validado; papéis de venda
  (CONSULTOR/ANALYST/MANAGER); trilha de atividades; atribuição de leads.
- BI org-scoped (6 endpoints), exportação PDF (weasyprint), pitch one-pager,
  cadência de follow-up com opt-out LGPD, playbooks por vertical, BYOK.
- Frontend completo em Next.js 16 (build OK, `tsc --noEmit` OK).

Porém a vistoria encontrou **3 bloqueadores** que quebram em uso real e um
grupo de pendências de prontidão para produção (sem deploy, sem testes
automatizados, sem backup) que precisam ser fechadas antes do go-live.

---

## 2. BLOQUEADORES — corrigir antes de qualquer outra coisa

### 2.1 Importação CSV e coleta CNAE quebram em runtime

O modelo `Lead` **não tem** as colunas `name`, `cnpj` nem `address` (só
`company_name`; o CNPJ vive em `CompanyRecord`). As duas rotas de aquisição
B2B mais importantes referenciam essas colunas e crasham na primeira linha:

- `services/api/src/services/csv_import_service.py:96,150-156`
  (`db.query(Lead.website, Lead.cnpj, Lead.place_id)` → `AttributeError`;
  `Lead(name=..., address=..., cnpj=...)` → `TypeError`).
- `services/api/src/pipeline_worker.py:134-156` (mesmo crash no ramo `cnae`).

Fix proposto: migration nova adicionando `leads.name`, `leads.cnpj` (unique
por org) e `leads.address`; ajustar os dois arquivos; rodar smoke test dos
dois fluxos de ponta a ponta.

### 2.2 requirements.txt incompletos — instalação nova não sobe

- `services/api/requirements.txt:1-7` **omite** `slowapi`, `bcrypt`, `PyJWT`,
  `httpx`, `email-validator`, `python-multipart` (FastAPI não importa sem ele)
  e `cryptography` — todos importados em runtime. Instalação limpa falha no boot.
- `services/workers/requirements.txt` também omite `cryptography` (Fernet do
  `secret_service.py:22` → BYOK do item 3.5 quebra no import).
- Sobras: `playwright` (nunca importado, pesado) e psycopg duplicado
  (`psycopg2-binary` + `psycopg-binary`).

Fix proposto: completar e **pinar** (==) os dois requirements; remover sobras;
validar com `pip install -r requirements.txt` em ambiente limpo.

### 2.3 auto_send_email dispara a cadência inteira de uma vez

`routes/leads.py:719-723` — quando a org tem `auto_send_email`, um loop envia
**todas** as etapas PENDING imediatamente (dia 0, 3, 7 e 14 no mesmo instante),
porque `send_step` (`cadence_service.py:97-159`) nunca verifica
`scheduled_at`. Isso queima a entregabilidade do domínio e viola a regra de
negócio dia 0/3/7/14.

Fix proposto: remover o loop imediato e depender só de `run_due` (que já
filtra `scheduled_at <= now`), ou fazer `send_step` respeitar `scheduled_at`.

---

## 3. ALTA prioridade (antes do go-live)

| # | Pendência | Onde | O que fazer |
|---|---|---|---|
| 3.1 | Kanban não abre o lead; botões mortos | `kanban-board.tsx:217-355` (cards sem link); `oportunidades/[id]/page.tsx:139-142` ("Enviar mensagem" sem onClick); `campaign-list.tsx:110-131` (menu Pausar/Duplicar/Arquivar inertes) | Ligar card do kanban a `/oportunidades/[id]`; implementar ou remover botões mortos |
| 3.2 | Sem tratamento de bounce | `cadence_service.py:131-134,173-204` | Contador `attempts`; 5xx → CANCELLED + suppression; 4xx/rede → retry; dev-mode `send_email` não pode retornar `True` (polui o funil) |
| 3.3 | Sem rastreio de resposta/STOP | `models.py:379-380` (nunca escritos); `analytics_service.py:159` | Webhook inbound (ex. Postmark) → `RESPONDIDO` + parse de STOP → `opt_out`; tracking de abertura/click |
| 3.4 | Sem deploy: compose só sobe Postgres; sem proxy/TLS; CSP de prod bloqueia API/WS | `docker-compose.yml:1-33`; `README.md` (vazio); `next.config.ts` (vazio); `middleware.ts:66` (`connect-src 'self' https://*.groq.com`) | Dockerfiles + compose (api/workers/web); nginx/caddy com TLS; `output:'standalone'`; add API origin + `wss:` ao CSP; `docs/ops.md` |
| 3.5 | Sem testes, sem CI, sem backup, sem observabilidade | repo-wide | pytest (conftest Postgres); CI (lint + tsc + build + `alembic upgrade head`); cron pg_dump + restauração; Sentry + `/health` com DB ping; nunca logar corpo de e-mail |
| 3.6 | E-mail heurístico (confiança 40) pode ser enviado | `contact_enrichment_service.py:255-269,401-408`; `cnpj_service.py:78-85` | Marcar heuristic como `unverified`; validar MX; gate no envio automático; confidence por canal como teto do agregado |
| 3.7 | Falha no erro-shape do frontend | `apps/web/src/lib/api.ts:68-70` (lê `error.message`; API devolve `{detail}`) | Parsing de `detail` no client (ou handler global `{message}`) |
| 3.8 | WebSocket com JWT em query string | `routes/pipeline.py:138-153`; `api.ts:543-547` | Token na 1ª mensagem WS ou header `Sec-WebSocket-Protocol` |

---

## 4. MÉDIA prioridade (fortes melhorias de prospecção)

| # | Pendência | Onde | O que fazer |
|---|---|---|---|
| 4.1 | E-mail sem threading headers; remetente compartilhado | `email_service.py:20-35,69-87`; `settings.py:22-28` | Remetente por org; `Message-ID`/`In-Reply-To`/`References`; throttle outbound |
| 4.2 | Leads sem site descartados sem score nem CNPJ | `enrichment_orchestrator.py:123-125,165-176`; `cnpj_service.py:10-12` | `score_business_lead` + lookup CNPJ por nome, ou manter NOVO e expor contagem |
| 4.3 | Dedupe inconsistente entre as 3 fontes | `pipeline_worker.py:184-188`; `csv_import_service.py:35-43,96-102` | Coluna canônica `normalized_domain` + unique por org, dedupe único |
| 4.4 | Campos de vendas que faltam | `models.py:289-345` | `lead.whatsapp`, `lead.notes`, `next_action_at`, `last_contacted_at`, `lead.cnpj` |
| 4.5 | Abuso: CSV sem cap, `max_leads` sem bound, rate limit só em auth | `campaigns.py:435`; `pipeline.py:29`; `middleware/rate_limit.py:4` | Cap 10MB + max linhas CSV; `Field(1, ge=1, le=200)`; `@limiter.limit` nos endpoints de custo |
| 4.6 | Evidência LLM não verificada contra fatos | `scoring_service.py:78,276-340`; `outreach_service.py:141-145` | Descartar evidência `source == "inferência LLM"` sem grounding; validar `evidence_ref` |
| 4.7 | LGPD: CPFs/faixa etária persistidos crus; sem retenção/exclusão | `cnpj_service.py:102-108,167`; `routes/leads.py` | Não persistir CPF/faixa_etária por default (mascarar); `DELETE /leads/{id}` + política de retenção |
| 4.8 | `_check_sensitive_paths` é varredura ativa (contradiz "100% passivo") | `technical_enrichment_service.py:16-24,268-280` | Remover ou atrás de opt-in explícito da org; documentar risco residual |
| 4.9 | Frontend: busca por tecla sem debounce; sem paginação; CSP de prod não validada | `lead-list.tsx:97-130`; `middleware.ts:42-72` | Debounce 300ms; paginação nas listas; re-testar CSP em build real |
| 4.10 | Lint da web com 5 erros (2 não documentados) | `campaign-pipeline.tsx:66`; `funnel-chart.tsx:105,114,178`; `org-switcher.tsx:62` | Corrigir hooks rules + hoist `CustomTooltip` + lazy-init do estado |

---

## 5. Arquitetura (aprofundar depois da entrega)

| # | Pendência | Onde | O que fazer |
|---|---|---|---|
| 5.1 | Provedores externos duplicados (12 clientes httpx, 5 blocos Groq/JSON, 19 `sys.path`, 2 `Settings`) | todos os `services/*` | Módulo profundo `provider_client` (fábrica de client, retry/backoff, rate-limit, parse JSON, cotas BYOK); `pip install -e` para eliminar sys.path |
| 5.2 | Coleta duplicada (2× `run_lead_collection`) | `workers/src/main.py:24-77` vs `api/src/pipeline_worker.py:162-221` | Um único `run_lead_collection` |
| 5.3 | Trabalho síncrono no loop async | `api/main.py:39` (SMTP); rotas `async def` com SQLAlchemy sync; `import` de CSV sync | `asyncio.to_thread`; CSV em executor |
| 5.4 | N+1 em listas | `leads.py:103,199`; `campaigns.py:93-97`; `analytics_service.py:108-147` | `selectinload`/`GROUP BY`; índice composto `(organization_id, status, qualification_score)` |
| 5.5 | Código morto / duplicado | `enrichment_orchestrator.py:33-79` (`load_scoring_template` sem chamadas); `ai_service.py` e `tasks/lead_processing_task.py` (0 bytes) | Deletar |
| 5.6 | Evidência de marca d'água | `docs/context.md` (estado atual) | Manter atualizado |

---

## 6. Pontos fortes a preservar

- Isolamento multi-tenant em todas as queries de analytics/PDF (`analytics_service.py`, `pdf_report_service.py`).
- `opt_out` LGPD aplicado em todos os caminhos de envio (`cadence_service.py:109-112,162-170,190`).
- Rodapé LGPD forçado mesmo se a LLM esquecer (`outreach_service.py:246-251`).
- Contenção de exceção por lead no pipeline e por follow-up no `run_due` — um lead ruim não derruba o batch.
- `SecretService` (Fernet) bem-fatorado — padrão a replicar.
- TanStack Query consistente no frontend; tipos tipados em toda a `api.ts`.

---

## 7. Recomendação de sequência

1. **Bloqueadores (2.1–2.3)** — CSV/CNAE + requirements + rajada de cadência.
2. **Prontidão mínima (3.4, 3.5)** — deploy + testes de smoke + backup antes do go-live.
3. **Eficácia (3.1–3.3, 3.6)** — kanban clicável, bounce, inbound STOP, gate de e-mail.
4. **Aprofundamento (5.x)** — `provider_client` e redução de N+1 quando o volume crescer.

> Regra de ouro: **nada de novo antes dos bloqueadores**. Duas das três vias de
> aquisição estão quebradas e o envio automático está perigoso — qualquer
> campanha real criada hoje topa com um desses problemas.
