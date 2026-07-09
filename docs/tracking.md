# Tracking — Gaps entre documentação e implementação

> Inventário completo do que está documentado, o que foi implementado
> e o que ainda falta. Atualize este arquivo conforme avança.

## Legenda

| Símbolo | Significado |
|---------|-------------|
| 🔴 Não iniciado | Documentado, zero código |
| 🟡 Parcial | Algum código existe, incompleto |
| ✅ Completo | Implementado e funcionando |
| ⏳ Em andamento | Sendo feito agora |
| 🔮 Futuro | Fase futura, sem prazo |

---

## 1. Infrastructure

| Item | Ref | Status |
|------|-----|--------|
| Docker: Postgres + pgAdmin | `docker-compose.yml` | ✅ |
| Workers Python (async) | `services/workers/` | ✅ |
| API REST FastAPI | `services/api/` | ✅ |
| Frontend Next.js 16 + shadcn/ui | `apps/web/` | ✅ |
| Auth JWT (NextAuth + FastAPI) | ambos | ✅ |
| CSP para produção (nonces/hashes) | `next.config` | 🔴 |
| Rate limiting em auth (slowapi) | `api/` | ✅ |
| Sonner toast library | `apps/web/` | ✅ |

## 2. Auth / Users

| Item | Ref | Status |
|------|-----|--------|
| Registro de usuário | `api/routes/auth.py` | ✅ |
| Login email/senha | `api/routes/auth.py` | ✅ |
| JWT token retornado como "token" | `api/routes/auth.py` | ✅ |
| NextAuth Credentials provider | `apps/web/auth.ts` | ✅ |
| Rotas protegidas (middleware) | `apps/web/middleware.ts` | ✅ |
| Esqueci minha senha | — | 🔴 |
| Página de configurações (trocar senha, editar perfil) | `/configuracoes` | 🔴 (rota existe, sem conteúdo) |

## 3. Campanhas / Wizard

| Item | Ref | Status |
|------|-----|--------|
| CRUD de campanhas (GET list, GET detail, POST create) | `api/routes/campaigns.py` | ✅ |
| Migration `analysis_profile` coluna em campaigns | migration 90f2b8f9d66e | ✅ |
| Campaign model com AnalysisProfile enum | `models.py` | ✅ |
| POST /api/campaigns aceita `analysis_profile` | `api/routes/campaigns.py` | ✅ |
| Frontend: lista de campanhas com lead_count e avg_score | `campanhas/page.tsx` | ✅ |
| Frontend: wizard 4 etapas | `campanhas/nova/page.tsx` | ✅ |
| Seletor de perfil (digital vs industrial) no wizard | `campanhas/nova/page.tsx` | ✅ |
| Botão "Me sugira segmentos" (IA) | `campanhas/nova/page.tsx` | 🔴 (botão existe, disabled) |
| Botão "Iniciar Coleta" no card da campanha | `CampaignList` | ✅ |
| Navegação para `/campanhas/[id]?start=true` | `CampaignList` | ✅ |
| Página `/pipeline` removida (unificada na campanha) | — | ✅ |

## 4. Coleta / Pipeline

| Item | Ref | Status |
|------|-----|--------|
| Google Places API (async) | `places_service.py` | ✅ |
| POST /api/pipeline/start (campaign_id obrigatório, query opcional) | `api/routes/pipeline.py` | ✅ |
| pipeline_worker lê campanha do DB, monta query de target_*, branch por analysis_profile | `pipeline_worker.py` | ✅ |
| WS /ws/pipeline/{job_id} — eventos em tempo real | `api/` | ✅ |
| Campaign inline: barra de progresso + log + sumário | `campaign-pipeline.tsx` | ✅ |
| Pipeline envia só { campaign_id, max_leads } (sem query livre) | `campaign-pipeline.tsx` | ✅ |
| Auto-start via `?start=true` | `campanhas/[id]/page.tsx` | ✅ |

## 5. Enriquecimento técnico

| Item | Ref | Status |
|------|-----|--------|
| Análise passiva de site (SSL, HTTPS, responsive, CMS, Lighthouse, SEO) | `technical_enrichment_service.py` | ✅ |
| Nunca probe, inject, teste auth (Lei 12.737/2012) | serviço passivo | ✅ |
| Lead sem website pula enriquecimento | `technical_enrichment_service.py` | ✅ |
| `_detect_cms` usa HTML já baixado (sem nova requisição HTTP) | `technical_enrichment_service.py` | ✅ |
| Detecção ampliada de CMS/stack (WordPress, Joomla, Next.js, Nuxt, Drupal, Webflow, Wix, Shopify, Squarespace, Google Sites, Elementor, Divi, PHP, ASP.NET, Express, nginx) | `technical_enrichment_service.py` | ✅ |
| `_check_seo` (title, meta description, h1, comprimento title) | `technical_enrichment_service.py` | ✅ |
| Menção a LGPD/política de privacidade no HTML | `technical_enrichment_service.py` | ✅ |
| Interpretação de velocidade (rápido/aceitável/lento/muito lento) em `performance` | `technical_enrichment_service.py` | ✅ |
| HTML baixado uma única vez em `_get_headers_and_status` | `technical_enrichment_service.py` | ✅ |
| Responsividade mobile (Playwright viewport) | — | 🔮 |
| Verificação de formulários | — | 🔮 |

## 6. Scoring / Qualificação

| Item | Ref | Status |
|------|-----|--------|
| Score 0-100 com Groq (llama-3.1-8b-instant) | `scoring_service.py` | ✅ |
| Score >= 60 → QUALIFICADO, < 60 → DESQUALIFICADO | `scoring_service.py` | ✅ |
| Prompt diferente por analysis_profile | `scoring_service.py` | ✅ |
| Prompt focado em negócio (sem análise de site) para business_opportunity | `scoring_service.py` | ✅ |
| Prompt de scoring usa dados da campanha (serviço-alvo, segmento) dinamicamente | `scoring_service.py` + `enrichment_orchestrator.py` | ✅ |
| `primary_need` inclui LGPD | `scoring_service.py` | ✅ |
| LLM gera `pitch_angle` (gancho de abordagem) | `scoring_service.py` | ✅ |
| LLM gera `suggested_subject` (assunto de e-mail) | `scoring_service.py` | ✅ |
| `qualification_reason` vira argumento de venda (conecta ao serviço-alvo) | `scoring_service.py` | ✅ |
| `pipeline_worker` repassa `campaign.target_service/segment` ao scoring | `pipeline_worker.py` | ✅ |
| Score recalibrado com histórico de conversões | — | 🔴 (Fase 5) |

## 7. Funil de leads / Status

| Item | Ref | Status |
|------|-----|--------|
| LeadStatus: NOVO, ANALISADO, QUALIFICADO, DESQUALIFICADO, CONTATADO, RESPONDIDO, REUNIAO_MARCADA, REUNIAO_FEITA, PROPOSTA_ENVIADA, PERDIDO | `models.py` + migration | ✅ |
| PATCH /api/leads/{id}/status (valida enum, retorna lead) | `api/routes/leads.py` | ✅ |
| GET /api/leads?status= aceita múltiplos valores separados por vírgula | `api/routes/leads.py` | ✅ |
| Botão "Registrar contato realizado" → CONTATADO + redirect /vendas | `oportunidades/[id]/page.tsx` | ✅ |
| Status PERDIDO volta à fila em 90 dias | — | 🔴 |
| Lead sem contato não entra em outreach automático | — | 🔮 |

## 8. Kanban (Vendas)

| Item | Ref | Status |
|------|-----|--------|
| 5 colunas: Mensagem enviada, Respondeu, Reunião marcada, Reunião realizada, Proposta enviada | `kanban-board.tsx` | ✅ |
| Filtra leads do funil (só CONTATADO→PROPOSTA_ENVIADA) | `kanban-board.tsx` | ✅ |
| Drag-and-drop chama PATCH /api/leads/{id}/status | `kanban-board.tsx` | ✅ |
| Toast de confirmação ao mover (sonner) | `kanban-board.tsx` | ✅ |
| Skeleton loading + error state | `kanban-board.tsx` | ✅ |

## 9. Detalhe do Lead (Oportunidades)

| Item | Ref | Status |
|------|-----|--------|
| GET /api/leads/{id} com enrichment | `api/routes/leads.py` | ✅ |
| GET /api/leads/{id} retorna `pitch_angle` e `suggested_subject` | `api/routes/leads.py` | ✅ |
| Abas: Dados gerais, Análise do site, Contatos, Ações | `oportunidades/[id]/page.tsx` | ✅ |
| Botão "Gerar mensagem personalizada" | `oportunidades/[id]/page.tsx` | 🔴 (apenas UI, sem API) |
| Botão "Registrar contato realizado" → API + redirect | `oportunidades/[id]/page.tsx` | ✅ |
| Exibir `pitch_angle` e `suggested_subject` na tela de detalhe | `oportunidades/[id]/page.tsx` | 🔴 (API expõe, UI ainda não mostra) |
| Busca por contatos de decisores (Hunter.io + CNPJ) | — | 🔮 |
| Tabela `contacts` + `contact_confidence` | — | 🔮 |

## 10. Dashboard

| Item | Ref | Status |
|------|-----|--------|
| GET /api/metrics (total, funnel, response_rate) | `api/routes/metrics.py` | ✅ |
| Funil visual com Recharts | `funnel-chart.tsx` | ✅ |
| Skeleton loading + error state | `MetricsGrid`, `FunnelChart` | ✅ |
| Leads por campanha (gráfico) | `dashboard/` | 🔴 |
| Score médio por segmento | `dashboard/` | 🔴 |
| Atividade recente (7 dias) | `dashboard/` | 🔴 |
| Seção "O que fazer agora" | `dashboard/` | 🔴 |
| Notificações no header | `header.tsx` (badge hardcoded "3") | 🟡 |

## 11. Leads (Lista)

| Item | Ref | Status |
|------|-----|--------|
| GET /api/leads com filtros (status, campaign, search, min_score, limit, offset) | `api/routes/leads.py` | ✅ |
| GET /api/leads/stats | `api/routes/leads.py` | ✅ |
| Lista de oportunidades com skeleton + error state | `LeadList` | ✅ |

## 12. Outreach / Contato (Futuro — Fase 3)

| Item | Ref | Status |
|------|-----|--------|
| `outreach_service.py` com IA (Llama 3.3 70B) | — | 🔮 |
| Envio via Resend | — | 🔮 |
| Sequência follow-up (dia 0, 3, 7, 14) | — | 🔮 |
| Link Cal.com self-hosted | — | 🔮 |
| Throttle de envio | — | 🔮 |
| Opt-out obrigatório | — | 🔮 |
| Botão "Gerar Pitch" na interface | `oportunidades/` | 🔮 |

## 13. Aprendizado contínuo (Futuro — Fase 5)

| Item | Ref | Status |
|------|-----|--------|
| Tabela `conversions` | `models.py` (existe) | 🟡 (model existe, sem uso) |
| Recalibração automática do scoring com 10+ conversões | — | 🔮 |

## 14. Multi-tenant / Alphamec (Futuro — Fase 6)

| Item | Ref | Status |
|------|-----|--------|
| Campanhas por área/setor | — | 🔮 |
| Dashboard por membro | — | 🔮 |
| Ranking de consultores | — | 🔮 |
| Convidar/remover membros | — | 🔮 |
| Relatórios exportáveis | — | 🔮 |

---

## Pendências imediatas (prioritárias)

1. Testar fluxo completo: cadastro → login → criar campanha → iniciar coleta → pipeline inline → oportunidades (com scoring contextual + pitch_angle/suggested_subject)
2. Exibir `pitch_angle` e `suggested_subject` na tela de detalhe do lead (`oportunidades/[id]/page.tsx`) — dados já expostos pela API
3. Botão "Me sugira segmentos" (IA) no wizard — precisa de endpoint + prompt
4. Esqueci minha senha
5. Página de configurações (trocar senha, editar perfil)
6. Lead status PERDIDO voltar à fila em 90 dias (agendador)
7. Rodar migration `1fb286c0715b` em ambientes que ainda não têm `pitch_angle`/`suggested_subject`
8. Dashboard: leads por campanha, score médio por segmento, atividade recente, "o que fazer agora"
9. Notificações no header (conectar à API real)
10. CSP para produção (nonces/hashes)
