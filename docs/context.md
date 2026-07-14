# agente-prospeccao — Context

> Leia este arquivo primeiro. Ele indica o que ler em seguida.

## Leitura obrigatória antes de qualquer tarefa

1. `docs/architecture.md` — estrutura do sistema, stack, serviços
2. `docs/business-rules.md` — regras de negócio, pipeline, status dos leads
3. `docs/interface.md` — requisitos da interface web (UX, fluxos, telas)

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
- `outreach_service.py` — mensagens IA + envio via Resend ✅ (agora em uso pelo endpoint generate-messages)
- Integração Cal.com para agendamento

### Próximo passo imediato

1. Testar fluxo completo: cadastro → login → criar campanha (com sugestão de segmento pelo botão "Me sugira segmentos") → iniciar coleta → pipeline inline → oportunidades
2. UI futura: gerenciar templates de scoring (CRUD de `campaign_scoring_templates`) e vincular à campanha no wizard
3. Testar reanálise das campanhas "Petshop" e "Farmácias" (têm score legado 60)

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
