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
| Autenticação (NextAuth) | ✅ | Google/GitHub OAuth |
| Dashboard | ✅ | Métricas, gráficos interativos |
| Buscas (Campanhas) | ✅ | Lista + wizard 4 etapas |
| Oportunidades | ✅ | Lista + detalhe com abas |
| Acompanhamento (Pipeline) | ✅ | Monitor tempo real com WebSocket |
| Negociações (Vendas) | ✅ | Kanban com drag-and-drop |
| **Conectar frontend à API** | ✅ | Mock data removido, hooks criados |
| **Autenticação funcional** | ✅ | NextAuth configurado |
| **Pipeline WebSocket** | ✅ | Streaming em tempo real |
| **Credenciais OAuth** | ⏳ | **Pendente** |

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

1. **Configurar OAuth** — preencher `.env.local` com credenciais Google/GitHub
2. **Commit e PR** — submeter todas as mudanças
3. **Testes end-to-end** — fluxo completo de coleta → pipeline → dashboard

## Decisões Pendentes

- Frontend ↔ Backend: REST para CRUD + WebSocket para tempo real (decidido ✅)
- Deploy: Vercel (frontend) + Railway/Fly.io (API + workers)?
