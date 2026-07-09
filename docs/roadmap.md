# Roadmap

## Fases do Projeto

### Fase 1 — Workers (Backend) ✅ Concluída

| Componente | Status | Arquivo |
|---|---|---|
| Coleta de leads (Google Places) | ✅ | `places_service.py` |
| Enriquecimento técnico de sites | ✅ | `technical_enrichment_service.py` |
| Scoring via IA (Groq) | ✅ | `scoring_service.py` |
| Modelos de dados | ✅ | `models.py` |
| Pipeline principal | ✅ | `main.py` |
| Migrações Alembic | ✅ | `alembic/` |

### Fase 1.5 — API REST + WebSocket ✅ Concluída

| Componente | Status | Arquivo |
|---|---|---|
| FastAPI setup | ✅ | `services/api/main.py` |
| GET /api/leads | ✅ | `routes/leads.py` |
| GET /api/leads/stats | ✅ | `routes/leads.py` |
| GET /api/campaigns | ✅ | `routes/campaigns.py` |
| GET /api/metrics | ✅ | `routes/metrics.py` |
| POST /api/pipeline/start | ✅ | `routes/pipeline.py` |
| WS /ws/pipeline/{job_id} | ✅ | `routes/pipeline.py` |
| Pipeline worker (eventos) | ✅ | `pipeline_worker.py` |
| Migration city nullable | ✅ | `6db61055` |
| CORS configurado | ✅ | `main.py` |

### Fase 2 — Frontend Web 🟡 Em andamento

| Componente | Status | Detalhes |
|---|---|---|
| Setup Next.js + TypeScript | ✅ | Next.js 16, React 19 |
| shadcn/ui | ✅ | 20+ componentes |
| Autenticação (NextAuth + Credentials) | ✅ | Email/senha com JWT |
| Dashboard | ✅ | Métricas, gráficos interativos |
| Buscas (Campanhas) | ✅ | Lista + wizard 4 etapas |
| Oportunidades | ✅ | Lista + detalhe com abas |
| Acompanhamento (Pipeline) | ✅ | Monitor tempo real com WebSocket |
| Negociações (Vendas) | ✅ | Kanban com drag-and-drop |
| **Conectar frontend à API** | ✅ | Mock data removido, hooks criados |
| **Autenticação funcional** | ✅ | Login + registro com email/senha |
| **Pipeline WebSocket** | ✅ | Streaming em tempo real |
| **API protegida por JWT** | ✅ | Todas as rotas com autenticação |
| **API auth endpoints** | ✅ | POST /api/auth/register + /login |
| **Bugfixes** | ✅ | 404, POST campaigns, enrichment, type mismatches |

### Fase 3 — Services Avançados 🔮 Futuro

| Componente | Status | Detalhes |
|---|---|---|
| Enriquecimento de contatos | ⏳ | Hunter.io + WHOIS + CNPJ |
| Outreach automatizado | ⏳ | IA para mensagens + Resend |
| Follow-up automático | ⏳ | Sequência dia 3, 7, 14 |
| Integração Cal.com | ⏳ | Agendamento de reuniões |

### Fase 4 — Multi-tenant 🔮 Distante

| Componente | Status |
|---|---|
| Por área/setor | ⏳ |
| Por membro | ⏳ |
| Gestão administrativa | ⏳ |

## Prioridades Próximas

1. **Testar build do frontend** — `npm run build` sem erros
2. **Testar fluxo completo** — cadastro → login → criar campanha → pipeline
3. **Gerar secrets reais** — NEXTAUTH_SECRET, JWT_SECRET

## TODOs futuros

- **Notificações**: implementar sistema de notificações no header (alerta de leads novos, respostas, follow-ups)
- **IA: descrição do serviço**: botão na criação de campanha para IA gerar descrição aleatória
- **IA: "Me sugira segmentos"**: botão no passo 2 da campanha para IA sugerir segmentos com base no serviço
- **Recurso: esqueci minha senha** — recuperação de acesso por email
- **Página de configurações**: trocar senha, editar perfil FUNCIONAL
- **Atividade recente real**: criar endpoint de atividade/log no backend

## Segurança & Qualidade de Código — Status ✅ Resolvido (2026-07-09)

Todas as 11 issues identificadas na revisão foram corrigidas:

| # | Problema | Status | Correção |
|---|---|---|---|
| 1 | `JWT_SECRET` com fallback inseguro | ✅ | Movido para pydantic-settings; `security.py` usa `settings.JWT_SECRET` |
| 2 | `JWT_SECRET` via `os.getenv` | ✅ | Agora lido via `settings.JWT_SECRET` (pydantic-settings) |
| 3 | WebSocket sem autenticação | ✅ | Token JWT exigido como query param `?token=`; validado via `decode_access_token` |
| 4 | Sem rate limiting em auth | ✅ | `slowapi` instalado; register 5/min, login 10/min |
| 5 | `getSession()` em toda request | ✅ | Token cacheado em memória; `setAccessToken()` chamado pós-login/register |
| 6 | Duplicação enrich+scoring | ✅ | Extraído para `enrichment_orchestrator.process_single_lead()` |
| 7 | `import os` não utilizado | ❌ Falso positivo | `os` é usado em `sys.path.insert` (linha 8); import mantido |
| 8 | `active_campaigns` sem type | 🔵 | Campo extra existe na resposta mas type não captura; não quebra nada |
| 9 | CSP com URLs OAuth obsoletas | ✅ | Removidos `accounts.google.com` e `github.com` do CSP |
| 10 | Type casting frágil | ✅ | Interface `SessionWithToken` + cast `as { accessToken?: string }` |
| 11 | JWT em sessão client-side | ⚠️ | Risco aceito para MVP; mitigado por CSP e HTTPS |

### 🔵 Observações adicionais

- Workers **não** tinham os problemas originalmente suspeitados: `TechnicalEnrichmentService` já usava `httpx.AsyncClient` e `scoring_service.py` usava `settings.GROQ_API_KEY` via pydantic-settings (não `os.environ`).
- Sessões de banco nos workers são fechadas em `finally` ✅.
- `active_campaigns` no metrics (issue #8): campo existe na resposta da API mas o tipo `DashboardMetrics` no frontend não o inclui. O campo é simplesmente ignorado — não causa erro. Pode ser adicionado ao type futuramente se necessário.

## Decisões Pendentes

- Frontend ↔ Backend: REST para CRUD + WebSocket para tempo real (decidido ✅)
- Deploy: Vercel (frontend) + Railway/Fly.io (API + workers)?
- Modelo de rate limiting: middleware FastAPI vs nginx/gateway externo?
- JWT_SECRET deve ser adicionado ao `settings.py` da API como campo pydantic?
