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
- AsyncClient refactorado para pattern per-use

### Fase 1.5 — API REST + WebSocket ✅ Pronta

- `services/api/` — FastAPI com endpoints REST + WebSocket
- `GET /api/leads` — lista com filtros (status, campaign, search, min_score)
- `GET /api/leads/stats` — estatísticas agregadas
- `GET /api/leads/{id}` — detalhe do lead
- `GET /api/campaigns` — lista com lead_count e avg_score
- `GET /api/campaigns/{id}` — detalhe da campanha
- `GET /api/metrics` — métricas do dashboard + funnel
- `POST /api/pipeline/start` — inicia pipeline em background, retorna job_id
- `WS /ws/pipeline/{job_id}` — streaming de eventos em tempo real
- `pipeline_worker.py` — adapta lógica dos workers para yield eventos
- Reutiliza models e session dos workers
- CORS configurado para frontend
- Migration `6db61055` — city nullable na tabela leads

### Fase 2 — Frontend Web 🟡 Em andamento (parcial) / ✅ Unificação concluída

**Anteriormente:** páginas `/campanhas` (lista + wizard) e `/pipeline` (monitor WebSocket) eram desconectadas — não havia botão "Iniciar coleta" na campanha nem contexto de campanha no pipeline.

**Unificação realizada (2026-07-09):**
- `/campanhas/[id]` — nova página de detalhe da campanha que integra:
  - Informações da campanha (serviço, segmento, local, status)
  - `CampaignPipeline` inline — WebSocket ao vivo com barra de progresso e log
  - Botão "Iniciar Coleta" com auto-start via `?start=true`
  - Tabela de leads da campanha ao finalizar
  - Link "Ver Oportunidades" após coleta concluída
- `CampaignList` — cada card agora tem:
  - Nome clicável (link para `/campanhas/[id]`)
  - Botão "Iniciar Coleta" que navega para `/campanhas/[id]?start=true`
- Sidebar: "Buscas" → "Campanhas"; "Acompanhamento" removido
- Página `/pipeline` removida (rota não existe mais)
- Componente `CampaignPipeline` criado em `components/campanhas/`

**Outros concluídos:**
- Setup Next.js 16 + React 19 + TypeScript
- shadcn/ui configurado (21+ componentes, incluindo Skeleton)
- NextAuth.js com Credentials provider (email/senha + JWT)
- Backend FastAPI com auth (registro + login + bcrypt + JWT)
- Todas as rotas da API protegidas por autenticação JWT
- Recharts, TanStack Query, Zustand
- Estrutura de rotas completa:
  - `/login` — login com email/senha
  - `/register` — cadastro de novo usuário
  - `/dashboard` — métricas interativas + gráficos
  - `/campanhas` — lista + wizard 4 etapas + detalhe com pipeline inline
  - `/oportunidades` — lista de leads + detalhe com abas
  - `/vendas` — kanban com drag-and-drop
- UX: termos amigáveis, botões responsivos, filtros interativos
- Frontend conectado à API REST (mock data removido)
- Pipeline monitor com WebSocket streaming (integrado nas campanhas)
- Kanban board com dados reais
- Bugfixes: POST /api/campaigns implementado, enrichment no GET /api/leads/{id}, 404 corrigidos, type mismatches corrigidos
- SQLAlchemy 2 (DeclarativeBase) em vez do legado

**Substituição de loading/erro por skeleton (2026-07-09):**
- `Skeleton` component criado em `components/ui/skeleton.tsx`
- `MetricsGrid` — 4 cards skeleton + cards de erro vermelhos
- `FunnelChart` — barras horizontais skeleton + estado de erro
- `CampaignList` — 3 cards skeleton + estado de erro
- `LeadList` — 6 cards skeleton + botão "Tentar novamente" no erro
- `KanbanBoard` — 5 colunas skeleton + botão "Tentar novamente" no erro

**Kanban / PATCH status (2026-07-09):**
- `POST /api/leads/{id}/status` — novo endpoint PATCH para atualizar status do lead
- `LeadStatus` enum expandido: `REUNIAO_FEITA` e `PROPOSTA_ENVIADA` adicionados (+ migration)
- `GET /api/leads?status=` agora aceita múltiplos valores separados por vírgula (ex: `CONTATADO,RESPONDIDO`)
- KanbanBoard: filtra leads do funil de vendas (exclui NOVO, ANALISADO, QUALIFICADO, DESQUALIFICADO)
- KanbanBoard: drag-and-drop chama `PATCH /api/leads/{id}/status` + toast de confirmação
- Botão "Registrar contato realizado" no detail do lead chama API e redireciona para `/vendas`
- `sonner` instalado para toasts

**Pendente:**
- Testar fluxo completo: cadastro → login → criar campanha → iniciar coleta → pipeline inline → oportunidades
- Adicionar funcionalidade de "esqueci minha senha"
- Adicionar página de configurações (trocar senha, editar perfil)
- Revisar CSP para produção (nonces/hashes em vez de unsafe-eval/inline)

### Fase 3 — Services Avançados (Futura)

- `contact_enrichment_service.py` — Hunter.io + WHOIS + CNPJ
- `outreach_service.py` — mensagens IA + envio via Resend
- Integração Cal.com para agendamento

### Próximo passo imediato
1. ~~Unificar páginas /campanhas e /pipeline~~ ✅
2. Testar fluxo completo: cadastro → login → criar campanha → iniciar coleta → pipeline inline → oportunidades
3. Adicionar "esqueci minha senha"
4. Adicionar página de configurações (trocar senha, editar perfil)
5. Revisar CSP para produção

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
# http://localhost:3000
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
