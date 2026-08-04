# agente-prospeccao — Context

> Leia este arquivo primeiro. Ele indica o que ler em seguida.

## Leitura obrigatória antes de qualquer tarefa

1. `docs/architecture.md` — estrutura do sistema, stack, serviços
2. `docs/business-rules.md` — regras de negócio, pipeline, status dos leads
3. `docs/interface.md` — requisitos da interface web (UX, fluxos, telas)
4. `docs/roadmap-combined.md` — **roadmap único e visão**: multi-vertical sem hardcode + inteligência comercial (BI, consultores, PDF, pitch, fontes, custos)

## Consulte antes de modificar

- `docs/decisions.md` — decisões técnicas tomadas e motivos
- `docs/coding-standards.md` — padrões obrigatórios de código
- `docs/agents.md` — regras específicas para agentes de IA

## Estado atual (atualizar a cada sessão)

### Fase 1 — Workers (Backend) ✅ Pronta

- `places_service.py` — coleta via Google Places API (async)
- `technical_enrichment_service.py` — análise passiva de sites (async)
  - `_detect_cms` agora usa HTML já baixado (sem nova requisição) + detecção ampliada de stack
  - `_check_seo` verifica title/meta description/h1 + menção a LGPD
  - `performance` interpreta `load_time_ms` (rápido/aceitável/lento/muito lento)
- `scoring_service.py` — qualificação via Groq (llama-3.1-8b-instant)
  - Prompt conhece contexto da campanha (`target_service` + `target_segment`)
  - LLM gera `pitch_angle` (gancho de abordagem) e `suggested_subject` (assunto de e-mail)
  - `primary_need` inclui LGPD
  - `qualification_reason` vira argumento de venda
- `enrichment_orchestrator.py` — repassa contexto da campanha ao scoring e persiste `pitch_angle`/`suggested_subject`
- `models.py` — `Lead.pitch_angle` (Text) e `Lead.suggested_subject` (String 255) adicionados (migration `1fb286c0715b`)
- `main.py` — `run_enrichment_and_scoring` integrado com scoring
- AsyncClient refactorado para pattern per-use

### Fase 1.5 — API REST + WebSocket ✅ Pronta (2026-07-10)

- `services/api/` — FastAPI com endpoints REST + WebSocket
- `GET /api/leads` — lista com filtros (status, campaign, search, min_score)
- `GET /api/leads/stats` — estatísticas agregadas
- `GET /api/leads/{id}` — detalhe do lead (inclui `pitch_angle` e `suggested_subject`)
- `GET /api/campaigns` — lista com lead_count e avg_score
- `GET /api/campaigns/{id}` — detalhe da campanha
- `GET /api/metrics` — métricas do dashboard + funnel
- `POST /api/pipeline/start` — inicia pipeline em background, retorna job_id
- `POST /api/leads/{id}/generate-messages` — gera sequência de outreach via Groq Llama 3.3 70B
  - Busca lead + campanha (context_service/segment) + contatos
  - Retorna subject, body_opening, followup_1/2, closing, whatsapp_short, rationale
- `POST /api/auth/forgot-password` — gera token de reset e envia email (ou loga no console)
- `POST /api/auth/reset-password` — redefinie senha com token válido
- `POST /api/auth/change-password` — altera senha do usuário autenticado
- `PATCH /api/auth/profile` — atualiza nome do perfil
- `pipeline_worker.py` — repassa `campaign.target_service/segment` ao scoring ao chamar `process_single_lead`
- `WS /ws/pipeline/{job_id}` — streaming de eventos em tempo real
- Reutiliza models e session dos workers
- CORS configurado para frontend
- Email service (stdlib smtplib) com fallback para console em desenvolvimento
- Migration `d5e6f7a8b9c0` — `reset_token` + `reset_token_expires` em users

### Fase 2 — Frontend Web ✅ Concluído (2026-07-10)

**Unificação campanhas/pipeline:**
- `/campanhas/[id]` — detalhe da campanha com pipeline inline, botão "Iniciar Coleta", tabela de leads
- `CampaignList` — cards com link para detalhe + botão "Iniciar Coleta"
- Sidebar: "Buscas" → "Campanhas"; "Acompanhamento" removido
- Página `/pipeline` removida

**Auth completo:**
- Setup Next.js 16 + React 19 + TypeScript
- shadcn/ui configurado (21+ componentes)
- NextAuth.js com Credentials provider (email/senha + JWT)
- Login + Registro + Esqueci senha + Resetar senha
- Link "Esqueci minha senha?" na página de login
- Páginas: `/esqueci-senha` (form email → token enviado) e `/resetar-senha` (token URL → nova senha)
- Backend FastAPI com auth (registro + login + bcrypt + JWT, forgot/reset/change/profile)
- Todas as rotas da API protegidas por autenticação JWT

**Páginas do app:**
- `/dashboard` — métricas interativas + gráficos (Recharts + TanStack Query)
- `/campanhas` — lista + wizard 4 etapas (criação) + detalhe com pipeline inline
- `/oportunidades` — lista de leads + detalhe com abas (Dados gerais, Evidências, Análise do site, Contatos, Ações)
  - Botão "Gerar mensagem personalizada" com modal de Tabs e cópia integrada
- `/vendas` — kanban com drag-and-drop (6 colunas do funil)
- `/configuracoes` — perfil (editar nome), aparência (temas claro/escuro/alpha), segurança (trocar senha)

**Pipeline / Reanálise:**
- Pipeline monitor com WebSocket streaming
- `POST /api/campaigns/{id}/reanalyze` — reanalisa leads existentes sobrescrevendo scoring legado
- Botão "Reanalisar leads" no `CampaignPipeline`
- `load_scoring_template` com match por `target_service` e `target_segment`

**Kanban / PATCH status:**
- `POST /api/leads/{id}/status` — endpoint PATCH para atualizar status
- `LeadStatus` enum expandido: `REUNIAO_FEITA` e `PROPOSTA_ENVIADA`
- `GET /api/leads?status=` aceita múltiplos valores separados por vírgula
- KanbanBoard: drag-and-drop chama PATCH + toast de confirmação (sonner)
- Botão "Registrar contato realizado" no detalhe do lead

**Scoring explicabilidade (Fase 2):**
- `score_factors[]` (±), `evidence[]` (severidade), `priority` (HOT/WARM/COLD), `executive_summary`
- Frontend: EvidenceCard com fatores +/− coloridos, prioridade com badge
- Migration `c4a1f2e8b9d0` + tabela `campaign_scoring_templates`
- 6 templates seedados: Desenvolvimento de Sites, SEO/Marketing Digital, Eng. Mecânica, Automação Industrial, Consultoria Empresarial, Genérico

**Gerar mensagens de outreach:**
- `apps/web/src/types/index.ts` — `OutreachMessages` interface
- `apps/web/src/lib/api.ts` — `leadsApi.generateMessages` + `authApi` completo
- `apps/web/src/hooks/use-api.ts` — `useGenerateMessages` (useMutation sem invalidate)
- Modal Dialog com Tabs (E-mail, Follow-ups, WhatsApp) e botões de cópia

**Segurança / CSP:**
- `middleware.ts` (renomeado de proxy.ts) — proteção de rotas + CSP por ambiente
  - Dev: `'unsafe-eval'` + `'unsafe-inline'` para HMR
  - Prod: `'strict-dynamic'` + nonces, mais restrito
  - Rotas públicas: /login, /register, /esqueci-senha, /resetar-senha, /api/auth

**Sugestão de segmentos por IA (wizard de campanha):**
- `services/workers/src/services/segment_suggestion_service.py` — Groq Llama 3.3 70B
  - `SegmentSuggestionService.suggest(profile, current_segment?, exclude?)` → dict
  - Prompt conhece o perfil (`web_presence` / `business_opportunity`) e variação por
    `temperature=0.9` + lista `exclude[]` para evitar repetição imediata
  - Fallback determinístico offline (`FALLBACKS` por perfil) quando Groq falha
  - Retorna: `segment`, `rationale`, `subniches[]`, `hook`, `cities_hint[]`
- `POST /api/campaigns/suggest-segment` — endpoint autenticado (JWT)
  - Body: `{ profile, current_segment?, exclude? }` — `profile` válido via Pydantic
  - Rota declarada antes de `/{campaign_id}` para evitar conflito de path matching
- `apps/web/src/lib/api.ts` — `campaignsApi.suggestSegment`
- `apps/web/src/hooks/use-api.ts` — `useSuggestSegment` + tipo `SegmentSuggestion`
- Wizard `/campanhas/nova` (step 2): botão "Me sugira segmentos" ativo
  - Card de resultado com segmento (preenche input), rationale, hook em itálico,
    subnichos clicáveis como Badges, cidades com densidade via `cities_hint`
  - Botão "Gerar outro" no canto do card — repete chamada com `exclude` atualizado

### Fase 3 — Services Avançados (Futura)

- `contact_enrichment_service.py` — Hunter.io + WHOIS + CNPJ
-        `outreach_service.py` — mensagens IA + envio via Resend ✅ (agora em uso pelo endpoint generate-messages)
   - **Quality overhaul das mensagens (2026-07-14)** — `outreach_service.py`:
     SYSTEM_PROMPT reescrito como copywriter sênior com regras anti-generic-AI
     (primeira frase factual direta, sem "notei que"/"ao analisar", sem jargão
     como "soluções"/"sinergia", sem frases-IA"diante disso"/"vale destacar"),
     CTA específico com horário proposto ("terça 10h ou quarta 14h"),
     contagens mínimas: body 200-280, followup_1 120-160, followup_2 140-180,
     closing 70-100 palavras. `max_tokens=3200` no payload Groq. Schema JSON
     atualizado. Bugfix do rodapé LGPD ("B2P" → "B2B"). INSTRUÇÕES do
     `build_prompt` agora guiam saudação em linha separada + observação
     factual imediata.
- Integração Cal.com para agendamento

### Fase A — Multi-tenant e Isolamento (P0) ✅ Concluído (2026-08-01)

**Models (workers):**
- `Organization` (workspace com `slug` único) + `OrganizationMember` (owner/admin/member)
  + `Invite` (convite por e-mail com token)
- `Campaign.organization_id` (NOT NULL) e `Lead.organization_id` (NOT NULL)
- `Lead.place_id` unique global → composta `uq_leads_org_place_id (organization_id, place_id)`
- `Job.organization_id` (nullable, jobs legados sem campanha)

**Migration `9a7b6c5d4e3f2`:**
- Cria `organizations`, `organization_members`, `invites`
- Enum `organization_role` (owner/admin/member)
- Backfill: uma org pessoal por usuário existente + membership owner + propagação
  para campanhas/leads/jobs
- Índices em `organization_id` (campaigns/leads/members)

**API (isolamento cross-tenant):**
- `org_service.py`: `create_personal_organization` (registro), `unique_slug`, `user_organization`
- `auth/dependencies.py`: `get_user_organization` — dependency que resolve a org do usuário
- `leads.py`, `campaigns.py`, `metrics.py`: toda listagem/detalhe/mutate filtra por org
- `pipeline.py`: job cria com `organization_id`; campanha validada como da org;
  WebSocket valida que o job pertence à org do usuário (403)
- `auth.py` register: cria org pessoal no onboarding
- `pipeline_worker.py`: leads coletados herdam org da campanha; filtro de leads por org

**Testado E2E:** registro de 2 usuários → orgs separadas; mesmo `place_id` em orgs
diferentes persiste; duplicata na mesma org rejeitada; A não vê lead/campanha de B (404).

### Fase X1 — Atribuição de leads + trilha (item 1.1 do roadmap) ✅ (2026-08-01)

- `Lead.assigned_to_id` (FK users) + `Lead.assigned_at` — dono do lead (consultor)
- Tabela `lead_activities` + enum `lead_activity_action` (CREATED/ASSIGNED/UNASSIGNED/
  STATUS_CHANGED/MESSAGE_GENERATED/CONTACTED/RESPONDED/MEETING_SCHEDULED/CONVERTED)
- `Conversion.user_id` + `Conversion.assigned_to_id` (quem fechou / quem trabalhava)
- `lead_activity_service.py`: `log_activity()` / `log_status_change()` — gravação central
- `PATCH /api/leads/{id}/assign` — atribui/desatribui (valida membro da mesma org, 403
  se não pertencer); grava ASSIGNED/UNASSIGNED
- `PATCH /api/leads/{id}/status` agora grava STATUS_CHANGED com status anterior
- `POST /api/leads/{id}/generate-messages` grava MESSAGE_GENERATED
- Detalhe do lead (`_lead_detail`) expõe `assigned_to` + `activities[]` (trilha)
- Migration `6b3c2a1d9e8f4`

**Testado E2E:** atribuir consultor da mesma org OK; atribuir usuário de outra org → 403;
mudança de status grava trilha (from/to corretos); trilha aparece no detalhe.

### Fase 1.2/1.3 — Router + geração de template sob demanda ✅ (2026-08-01)

- `template_router.py`: `route_scoring_template()` — exact → fuzzy (token overlap) →
  LLM (Groq 8B) → `GENERATE_NEW`/Genérico; cache em memória (256, chave=texto+labels)
- `template_generation_service.py`: `TemplateGenerationService.generate()` — Groq 70B
  cria `positive/negative/context_signals` + flags + `extra_instructions` no schema do
  seed; persiste com `is_generated=True` + `organization_id`; reutiliza por label; fallback Genérico
- `campaign_scoring_templates.is_generated` + `organization_id` (migration `7d4e5f6a8b9c0`)
- `pipeline_worker.py`: consome `GENERATE_NEW` → gera e vincula o template à campanha

**Testado:** router classifica "engenharia mecânica" → Eng. Mecânica; "auditoria contábil"
→ Consultoria; geração cria 7 sinais positivos p/ "landing pages para clínicas de psicologia".

### Fase 1.4 — Campanha por linguagem natural ✅ (2026-08-01)

- `campaign_brief_service.py`: `CampaignBriefService.interpret()` — Groq 70B parseia
  brief PT-BR → `name`, `target_service`, `target_segment`, `target_city`,
  `target_state`, `analysis_profile`, `places_query`, `scoring_template_label`,
  `rationale`; validação Pydantic + erro 502 claro em falha (sem fallback inventado)
- `POST /api/campaigns/from-brief` — devolve a sugestão SEM criar; resolve o template
  mais próximo via router (exact/fuzzy/LLM) para o review card
- `campaigns.places_query` (migration `8a1b2c3d4e5f6`) — query otimizada p/ Places;
  pipeline a usa quando presente (senão monta de target_segment/city/state)
- Frontend `/campanhas/nova`: toggle **Wizard | Agente**; modo agente = textarea +
  "Gerar campanha" → review card editável → "Criar" ou "Criar e iniciar coleta"
- Corrigido erro TS pré-existente (interface `OutreachMessages` duplicada em api.ts)

**Testado E2E:** brief "landing pages p/ clínicas de psicologia em Araraquara" →
campos corretos + template "SEO / Marketing Digital" (MATCHED); campanha criada
com `places_query`; pipeline coletou 3 leads de psicologia em Araraquara e
qualificou 2 (score 62/64) usando a query do agente.

### Fase 1.5 — CRUD de templates + vínculo no wizard ✅ (2026-08-01)

- `GET/POST/PATCH /api/scoring-templates` (novo route): globais (org NULL) + da org;
  `scope=all|global|org`, `include_inactive`, `search`; POST cria com `is_generated=False`
  na org do usuário; PATCH edita sinais/flags/instruções/`is_active` (usado na
  revisão humana do item 1.5.4); isolamento por org validado (404 para outra org)
- `PATCH /api/campaigns/{id}` — vincula/desvincula `scoring_template_id` (valida
  org ou global); pipeline já consome via `explicit_template_id`
- Frontend: `template-selector.tsx` no passo 4 do wizard — escolhe template,
  edita sinais (positive/negative/context + weight), flags (técnica/cadastrais),
  instruções; badge "Gerado por IA — revisar" para `is_generated` (1.5.4);
  "Salvar alterações no template" (PATCH) e vínculo automático ao criar campanha

**Testado E2E:** lista globais (9 seeds); criar template local (org scoping);
PATCH sinais/flags; vincular template à campanha; outra org → 404 + scope=org vazio.

### Fase 2.1 — Papéis de venda 🟡 em andamento (2026-08-01)

- `OrganizationMember.sales_role` — enum `CONSULTOR`/`ANALYST`/`MANAGER`
  (default CONSULTOR), **por organização** (migration `b2c3d4e5f6a7b`, aplicada)
- `SalesRole` exportado no re-export da API; pesos: CONSULTOR=0, ANALYST=1, MANAGER=2
- Dependencies novas (`auth/dependencies.py`):
  - `get_user_membership()` — membership da org ativa (403 se não membro)
  - `require_sales_role(min)` (fábrica) + `require_analyst()` + `require_manager()`
  - `require_org_admin()` — owner/admin (gestão de membros)
  - owner/admin equivalem a MANAGER para leitura/BI independente do papel de venda
- `src/services/org_service.py`: `is_full_access(member)` (ANALYST/MANAGER/owner/admin)
  + `consultant_lead_scope(member, query)` — CONSULTOR vê só leads dele OU não atribuídos
- `routes/orgs.py` (novo): `GET /api/orgs/{id}/members` (MANAGER+)
  + `PATCH /api/orgs/{id}/members/{user_id}` (owner/admin) → define `sales_role`
- `routes/leads.py`: escopo por papel em `list`, `stats`, `get`, `status`, `assign`,
  `generate-messages` (CONSULTOR → 403 em lead de outro consultor; auto-atribuição de
  lead não atribuído permitida)
- Registrado em `main.py`

**Testado E2E:** CONSULTOR vê 3 (2 seus + 1 não atribuído) e é bloqueado (403)
em lead do ANALYST; ANALYST vê todos (4); owner promove/rebaixa membro
(CONSULTOR↔MANAGER); CONSULTOR não lista membros (403) nem muda papel (403).

**Pendente 2.1:** ~~frontend (badge de papel, gestão na tela de membros), testes
automáticos, revisão de `require_org_admin` para ADMIN (hoje ADMIN já passa).~~
**Frontend entregue (2026-08-02)** — badge de papel de venda, página `/configuracoes/membros`
(gestão de papéis por owner/admin), kanban com self-assign + badge de atribuição, badge no
perfil, sidebar "Equipe", `GET /api/orgs/me` e `assigned_to_name` no lead. PR #25 aberto.

### Fase 2.2 — APIs de BI ✅ (2026-08-02)

- `src/services/analytics_service.py` (novo) — `AnalyticsService` org-scoped (filtra
  por `organization_id` em todas as queries; nada vaza entre tenants)
- `routes/analytics.py` (novo) — 6 endpoints **ANALYST/MANAGER-only**
  (owner/admin passam); CONSULTOR → 403:
  - `GET /api/analytics/overview` — KPIs, funil, conversão/reunião/resposta, leads por faixa de score
  - `GET /api/analytics/consultants` — por consultor: atribuídos, contatados, reuniões, propostas, convertidos, conversão %
  - `GET /api/analytics/leads-ranking` — top leads (`sort_by=score|converted|created`, filtro campanha/período)
  - `GET /api/analytics/geo` — agregação por cidade e UF (count, avg_score, convertidos) p/ heatmap + mapa
  - `GET /api/analytics/campaigns` — leads, qualificados, contatados, reuniões, conversão, receita
  - `GET /api/analytics/timeline` — evolução temporal `group_by=day|week` (novos, reuniões, fechados)
- Filtro de período `from`/`to` (YYYY-MM-DD) em todos os endpoints
- Registrado em `main.py`

**Testado E2E** (banco temporário Postgres + TestClient): dados reais (funil, faixas,
consultor com 1 conversão, geo cidade/UF com convertidos, receita R$5.000, timeline e
filtro período) corretos; **ANALYST → 200 em todos; CONSULTOR → 403 em todos**.

### Fase 2.3 — Exportação PDF ✅ (2026-08-02)

- `src/services/pdf_report_service.py` (novo) — `build_report_pdf()`: agrega via
  `AnalyticsService` (org-scoped) e renderiza **WeasyPrint** (HTML→PDF) com branding:
  visão executiva (KPIs + taxas), funil, por campanha, por consultor, top leads, geo,
  evolução temporal (gráfico CSS)
- **Dependência nova aprovada**: `weasyprint` (requirements da API) + runtime
  GTK/Pango no Windows (`GTK3-Runtime Win64`) com `os.add_dll_directory()` automático;
  em Linux basta o pacote de sistema do Pango
- Cache em memória do HTML agregado (TTL 5min) — item 2.3.4
- `GET /api/analytics/export/pdf?from=&to=` — **ANALYST/MANAGER-only**; retorna
  `application/pdf` com `Content-Disposition: attachment`; 503 se WeasyPrint ausente
- Registrado em `routes/analytics.py` (path fixo, sem conflito)

**Testado E2E** (banco temporário): PDF gerado (`%PDF-1.7`, 29KB, seções presentes);
**ANALYST → 200 + application/pdf**; **CONSULTOR → 403**; PDF com período OK.

### Fase 2.4 — Frontend relatórios/kanban/mapa ✅ (2026-08-02)

- **Dependência nova aprovada**: `leaflet` + `react-leaflet@5` (React 19) + `@types/leaflet`
- **`/relatorios`** (nova rota, guard MANAGER/ANALYST/owner/admin — CONSULTOR vê acesso restrito):
  - KPIs executivos (leads, qualificados, contatados, reuniões, convertidos, receita)
  - Funil, taxas (conversão/resposta/reunião), faixas de score
  - **Mapa de oportunidades** (Leaflet): círculos por UF, cor = score médio, tamanho = nº leads,
    tooltip com convertidos — centroides estáticos (sem API de geocodificação; offline/LGPD)
  - Desempenho por consultor + campanhas + melhores oportunidades
  - Evolução temporal (Recharts: barras novos/reuniões + linha de fechados)
  - Filtro de período (presets 30/90 dias/Tudo + datas) e botão **Exportar PDF** (download)
- **Kanban `/vendas`**: menu "Atribuir para" (owner/admin/MANAGER) com lista de membros +
  desatribuir; CONSULTOR mantém "Atribuir a mim" (item 2.1)
- **Detalhe do lead**: nova aba **Atividades** — trilha (quem fez o quê, quando, transições)
- Sidebar: item "Relatórios" (visível apenas para ANALYST/MANAGER/owner/admin)
- `analyticsApi` + hooks `useAnalytics*` no client

**Build**: `npm run build` OK (rota `/relatorios`); lint sem erros novos (4 erros são
pré-existentes em `campaign-pipeline.tsx`/`funnel-chart.tsx`); dev server responde.

### Fase 2.5 — Pitch one-pager + site audit ✅ (2026-08-02)

- `src/services/pitch_service.py` (novo) — `build_pitch_one_pager()` e `build_site_audit()`:
  consolida identidade (CNPJ/porte/CNAE), contexto da campanha, qualificação (score, dores,
  necessidade), pitch (gancho, assunto), fatores +/−, evidências, contato principal e auditoria do site
  (SSL, CMS, velocidade, segurança, SEO, LGPD, caminhos expostos)
- `GET /api/leads/{id}/pitch` (endpoint novo no `routes/leads.py`): retorna o pitch one-pager
  estruturado para o vendedor/consultor
- `pdf_report_service.py`: inclui dossiê das 3 melhores oportunidades no PDF do relatório executivo
- Frontend:
  - Rota `/oportunidades/[id]`: nova aba **Pitch One-Pager** (`LeadPitchTab`) com cards de pitch,
    identidade cadastral, contato principal, fatores de qualificação, evidências e auditoria do site
  - `leadsApi.getPitch` e hook `useLeadPitch`
  - Interfaces `PitchOnePager`, `SiteAudit`, `SiteAuditSection` em `types/index.ts`

### Fase A4/A5 — Org switcher + sistema de convites ✅ (2026-08-04)

**Backend:**
- `src/services/invite_service.py` (novo) — `create_invite`, `accept_invite`, `list_pending_invites`, `revoke_invite`
- `POST /api/orgs/{id}/invites` — cria convite (owner/admin only), gera token único com expiração 7 dias
- `GET /api/orgs/{id}/invites` — lista convites pendentes (owner/admin only)
- `POST /api/invites/accept` — aceita convite por token (valida e-mail do usuário autenticado)
- `DELETE /api/orgs/{id}/invites/{id}` — revoga convite pendente
- `GET /api/orgs/my-organizations` — lista todas as organizações do usuário (para org switcher)
- Migration `c3d4e5f6a7b8c` — adiciona `invited_by_id` (FK users) e `sales_role` (enum) à tabela `invites`
- Modelo `Invite` atualizado com relationship `invited_by`

**Frontend:**
- `OrgSwitcher` component — dropdown no sidebar para trocar entre organizações (localStorage com versão `org_storage_v1`)
- `InvitesManager` component — criar/listar/revogar convites (dialog + cards + confirmação AlertDialog + validação de e-mail)
- Rota `/aceitar-convite?token=...` — página pública para aceitar convites (com guard contra requisições duplicadas + acessibilidade aria-live)
- Integrado em `/configuracoes/membros` — seção de convites acima da lista de membros + feedback visual per-member no PATCH role
- API client: `orgsApi.listMyOrganizations`, `invitesApi.{create,list,accept,revoke}`
- Hooks: `useMyOrganizations`, `useInvites`, `useCreateInvite`, `useAcceptInvite`, `useRevokeInvite`
- Types: `OrganizationListItem`, `Invite`
- Middleware: `/aceitar-convite` adicionado como rota pública + CSP aprimorada com `frame-ancestors 'none'` e tile servers no `img-src`
- **Revisão com Skills (`frontend-design` & `vercel-react-best-practices`)**:
  - `OrgSwitcher`: memoização com `useMemo`/`useCallback`, versionamento de schema no localStorage, rótulos de papéis traduzidos (PT-BR), acessibilidade `aria-expanded` e `aria-label`.
  - `InvitesManager`: `AlertDialog` para confirmação de revogação, `render` prop do Base UI, validação de e-mail antes do envio, `aria-hidden` em ícones decorativos.
  - `MembrosPage`: feedback de alteração de papel (`isSuccess`) escopado por usuário individual.
  - `AcceptInvitePage`: ref para prevenir mutação duplicada no React 19 / StrictMode, `aria-live="polite"` no feedback de carregamento.
  - Instruções para agentes atualizadas em `AGENTS.md` e `docs/agents.md`.

**Testado:** migration aplicada, API roda sem erros, org switcher mostra orgs, página de convites renderiza.

### Fase 3.1 — Importação de Leads por CSV ✅ (2026-08-04)

**Backend:**
- `services/api/src/services/csv_import_service.py` (novo) — `CsvImportService.parse_and_import()`:
  - Suporte a delimitadores `,` e `;`
  - Mapeamento flexível de colunas (Nome/Empresa, Site/Website, Telefone, Cidade, Estado/UF, CNPJ, Endereço, Categoria)
  - Validação linha a linha + higienização de URLs e CNPJs
  - Deduplicação por `(organization_id, website/cnpj/place_id)`
  - Geração de `place_id` sintético determinístico (`csv_<hash>`)
  - Retorna relatório estruturado (`total_rows`, `imported_count`, `duplicate_count`, `error_count`, `errors[]`)
- `POST /api/campaigns/{id}/import` — endpoint multipart/form-data com suporte a codificações UTF-8 e Latin-1

**Frontend:**
- `CsvImportModal` component — modal interativo para seleção de arquivos .csv, exibição de regras de colunas, progresso e relatório detalhado pós-importação.
- Integrado na página de detalhe da campanha `/campanhas/[id]` com botão "Importar CSV" no topo.
- `campaignsApi.importCsv` + hook `useImportCsv` com invalidação do cache de campanhas e leads.

### Fase 3.2 — Descoberta de Empresas por CNAE / Receita ✅ (2026-08-04)

**Backend:**
- `services/workers/src/services/cnae_discovery_service.py` (novo) — `CnaeDiscoveryService`:
  - Integração resiliente multi-provedor (BrasilAPI + Minha Receita + CNPJá Open API com rate-limit automático de 5 req/min)
  - Normalização de CNAE e CNPJ
  - Busca de dados cadastrais detalhados
- `pipeline_worker.py`: suporte estendido a `source="cnae"`, permitindo coleta de leads diretamente da Receita Federal
- `POST /api/campaigns/{id}/collect-cnae` — endpoint autenticado para disparar o job de coleta CNAE/CNPJ em background

**Frontend:**
- `CnaeDiscoveryModal` component — modal para inserção de código de CNAE (ex: `2869100`), lista de CNPJs e limite de leads
- Integrado na página da campanha `/campanhas/[id]` com botão "Buscar por CNAE"
- `campaignsApi.collectCnae` + hook `useCollectCnae`

### Fase 3.3 — Enriquecimento Adaptativo ✅ (2026-08-04)

**Backend:**
- `enrichment_orchestrator.py`: seleciona steps condicionalmente (`requires_technical_report` e `requires_business_data` do template) — não faz scraping/requisições HTTP em sites se o template da campanha indicar que auditoria técnica é irrelevante.
- `pipeline_worker.py`: emissão de logs e eventos WebSocket em tempo real para cada step ("Pulpando auditoria técnica de site", "Consultando dados cadastrais/CNAE", "Score contextual").

### Próximo passo imediato

1. **Fase 3 — Ampliar fontes e fechar o loop:**
   - **Item 3.4 — Hunter / e-mail de decisor** (`feat/hunter-enrichment`).
   - **Item 3.5 — BYOK e cotas por org** (`feat/org-byok`).
2. Validar nas campanhas reais (Petshop / Farmácias) a qualidade das mensagens
   geradas com o novo prompt — abrir uma oportunidade real pelo endpoint
   `generate-messages` e revisar o `body_opening`.

## Como rodar

**Workers (backend):**
```bash
cd services/workers
source venv/bin/activate
python -m src.main
```

**API REST:**
```bash
cd services/api
source venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8000
# Docs: http://localhost:8000/docs
```

**Frontend:**
```bash
cd apps/web
npm run dev
# http://localhost:3001
```

## Commits Recentes

| Hash | Descrição |
|------|-----------|
| `12a1946` | feat(web): connect frontend to real API with auth |
| `8030d07` | feat(api): create FastAPI with REST endpoints |
| `460b88b` | fix(web): revert to "leads" terminology |
| `77ebeec` | feat(web): UX improvements, drag-and-drop |
| `d85bef2` | feat(web): complete route structure |
| `c5e0932` | feat(web): setup Next.js with shadcn/ui |
| `12a1946` | feat(web): connect frontend to real API with auth |
| `8030d07` | feat(api): create FastAPI with REST endpoints |
| *(current)* | feat(web): unify campanhas and pipeline pages |
