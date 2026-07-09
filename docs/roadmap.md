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

### Fase 2 — Frontend Web 🟡 Em andamento

| Componente | Status | Detalhes |
|---|---|---|
| Setup Next.js + TypeScript | ✅ | Next.js 16, React 19 |
| shadcn/ui | ✅ | 20+ componentes |
| Autenticação (NextAuth) | ✅ | Google/GitHub OAuth configurado |
| Dashboard | ✅ | Métricas, gráficos interativos, ações rápidas |
| Buscas (Campanhas) | ✅ | Lista + wizard 4 etapas |
| Oportunidades | ✅ | Lista de leads + detalhe com abas |
| Acompanhamento (Pipeline) | ✅ | Monitor tempo real |
| Negociações (Vendas) | ✅ | Kanban com drag-and-drop |
| Conexão com backend | ⏳ | Próximo passo |
| Dados reais | ⏳ | Substituir mock data |

### Fase 3 — Services Avançados 🔮 Futuro

| Componente | Status | Detalhes |
|---|---|---|
| Enriquecimento de contatos | ⏳ | Hunter.io + WHOIS + CNPJ |
| Outreach automatizado | ⏳ | IA para mensagens + Resend |
| Follow-up automático | ⏳ | Sequência dia 3, 7, 14 |
| Integração Cal.com | ⏳ | Agendamento de reuniões |

### Fase 4 — Multi-tenant 🔮 Distante

| Componente | Status | Detalhes |
|---|---|---|
| Por área/setor | ⏳ | Dashboard agregado |
| Por membro | ⏳ | Perfil individual, ranking |
| Gestão administrativa | ⏳ | Convites, permissões, relatórios |

## Prioridades Próximas

1. **Conectar frontend ao backend** — API routes ou WebSocket para dados reais
2. **Autenticação funcional** — Configurar credenciais OAuth no `.env`
3. **Substituir mock data** — Buscar dados dos workers via API
4. **Testes end-to-end** — Fluxo completo: login → busca → enriquecimento → oportunidade

## Decisões Pendentes

- Comunicar frontend ↔ backend: REST API simples ou WebSocket para tempo real?
- Onde rodar os workers: mesmo servidor, Docker Compose, ou cloud?
- Estratégia de deploy: Vercel (frontend) + Railway/Fly.io (workers)?
