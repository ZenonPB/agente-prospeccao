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

### Fase 1.5 — API REST ✅ Concluída

| Componente | Status | Arquivo |
|---|---|---|
| FastAPI setup | ✅ | `services/api/main.py` |
| GET /api/leads | ✅ | `routes/leads.py` |
| GET /api/leads/stats | ✅ | `routes/leads.py` |
| GET /api/campaigns | ✅ | `routes/campaigns.py` |
| GET /api/metrics | ✅ | `routes/metrics.py` |
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
| Acompanhamento (Pipeline) | ✅ | Monitor tempo real |
| Negociações (Vendas) | ✅ | Kanban com drag-and-drop |
| **Conectar frontend à API** | ⏳ | **Próximo passo** |
| WebSocket pipeline tempo real | ⏳ | Fase 1.5 + frontend |

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

1. **WebSocket `/ws/pipeline`** — eventos em tempo real do worker para o frontend
2. **Conectar frontend à API** — substituir mock data por chamadas reais
3. **Autenticação funcional** — configurar OAuth no `.env`
4. **Testes end-to-end** — fluxo completo

## Decisões Pendentes

- Frontend ↔ Backend: REST para CRUD + WebSocket para tempo real (decidido ✅)
- Deploy: Vercel (frontend) + Railway/Fly.io (API + workers)?
