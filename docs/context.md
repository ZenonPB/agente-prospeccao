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
- `scoring_service.py` — qualificação via Groq (llama-3.1-8b-instant)
- `models.py` — todos os modelos, migration rodada com `raw_technical_data`
- `main.py` — `run_enrichment_and_scoring` integrado com scoring
- Filtro de duplicata corrigido (usa `&` SQLAlchemy)
- AsyncClient refactorado para pattern per-use (não mais no `__init__`)

### Fase 2 — Frontend Web 🟡 Em andamento

**Concluído:**
- Setup Next.js 16 + React 19 + TypeScript
- shadcn/ui configurado (20+ componentes)
- NextAuth.js (Google/GitHub OAuth)
- Recharts (gráficos), TanStack Query, Zustand
- Estrutura de rotas completa:
  - `/login` — OAuth login
  - `/dashboard` — visão geral com métricas interativas
  - `/campanhas` — lista + wizard 4 etapas
  - `/oportunidades` — lista de leads + detalhe com abas
  - `/pipeline` — monitor em tempo real
  - `/vendas` — kanban com drag-and-drop
- UX melhorada: termos amigáveis, botões responsivos, filtros interativos (estilo Power BI)
- Drag-and-drop no Kanban (@hello-pangea/dnd)

**Pendente:**
- Conectar frontend à API dos workers (backend)
- Autenticação funcional (credenciais OAuth no `.env`)
- Dados reais em vez de mock data
- Responsividade mobile completa

### Fase 3 — Services Avançados (Futura)

- `contact_enrichment_service.py` — Hunter.io + WHOIS + CNPJ
- `outreach_service.py` — mensagens IA + envio via Resend
- Integração Cal.com para agendamento

### Pendências conhecidas
- Nenhuma pendência crítica na Fase 1

### Próximo passo imediato
1. Conectar frontend ao backend (API routes ou WebSocket)
2. Implementar autenticação funcional
3. Substituir mock data por dados reais da API

## Commits Recentes

| Hash | Descrição |
|------|-----------|
| `460b88b` | fix: revert to "leads" terminology |
| `77ebeec` | feat: UX improvements, drag-and-drop, friendly language |
| `d85bef2` | feat: complete route structure and page components |
| `d73d290` | docs: add interface web vision document |
| `c5e0932` | feat: setup Next.js with shadcn/ui, recharts, next-auth |
| `bffc0b0` | fix: refactor AsyncClient to per-use pattern |

## Como rodar

**Workers (backend):**
```bash
cd services/workers
source venv/bin/activate
python -m src.main
```

**Frontend:**
```bash
cd apps/web
npm run dev
# Acessa http://localhost:3000
```
