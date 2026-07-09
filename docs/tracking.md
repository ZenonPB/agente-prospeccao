# Tracking — Gaps entre documentação e implementação

> Inventário de tudo que está documentado nos `.md` mas ainda não foi
> implementado. Atualize este arquivo conforme avança.

## Legenda

| Símbolo | Significado |
|---------|-------------|
| 🔴 Não iniciado | Documentado, zero código |
| 🟡 Parcial | Algum código existe, incompleto |
| ✅ Completo | Implementado e funcionando |
| ⏳ Em andamento | Sendo feito agora |
| 🔮 Futuro | Fase futura, sem prazo |

---

## 1. Core: analysis_profile (prox etapa)

| Item | Ref | Status |
|------|-----|--------|
| Migration `analysis_profile` coluna | tag: análise do perfil | ⏳ ETAPA 1 |
| Campaign model (workers) | models.py | ⏳ ETAPA 2a |
| POST /api/campaigns receber profile | api/routes/campaigns.py | ⏳ ETAPA 2b |
| pipeline_worker ler campaign + branch por profile | pipeline_worker.py | ⏳ ETAPA 2c |
| POST /api/pipeline/start só campaign_id | api/routes/pipeline.py | ⏳ ETAPA 2d |
| Wizard frontend: seletor de perfil (digital vs industrial) | campanhas/nova/page.tsx | ✅ ETAPA 3a |
| Remover query livre do pipeline frontend | campaign-pipeline.tsx | ✅ ETAPA 3b |

## 2. Scoring contextual (product-vision.md:126-130)

| Item | Ref | Status |
|------|-----|--------|
| Prompt de scoring usar dados da campanha (serviço-alvo, segmento) | scoring_service.py | 🔴 |
| Prompt diferente por analysis_profile | scoring_service.py | 🔴 |
| Prompt focado em negócio (sem análise de site) para business_opportunity | scoring_service.py | 🔴 |

## 3. Enriquecimento avançado (product-vision.md:79-92)

| Item | Ref | Status |
|------|-----|--------|
| Responsividade mobile (Playwright viewport) | technical_enrichment_service.py | 🔮 Fase 4 |
| Lighthouse score | technical_enrichment_service.py | 🔮 Fase 4 |
| SEO: meta tags, sitemap, robots.txt | technical_enrichment_service.py | 🔮 Fase 4 |
| Verificação de formulários | technical_enrichment_service.py | 🔮 Fase 4 |
| Política de privacidade / LGPD | technical_enrichment_service.py | 🔮 Fase 4 |
| Contatos Hunter.io + CNPJ | contact_enrichment_service.py | 🔮 Fase 3-4 |
| Tabela `contacts` | models.py | 🔮 Fase 4 |
| `contact_confidence` | models.py | 🔮 Fase 4 |

## 4. Outreach (product-vision.md — Etapa 4)

| Item | Ref | Status |
|------|-----|--------|
| `outreach_service.py` com IA (Llama 3.3 70B) | services/workers/ | 🔮 Fase 3 |
| Envio via Resend | services/workers/ | 🔮 Fase 3 |
| Sequência follow-up (dia 0, 3, 7, 14) | services/workers/ | 🔮 Fase 3 |
| Link Cal.com self-hosted | — | 🔮 Fase 3 |
| Throttle de envio | — | 🔮 Fase 3 |
| Opt-out obrigatório | — | 🔮 Fase 3 |
| Interface: botão "Gerar Pitch" | oportunidades/ | 🔮 Fase 3 |
| Interface: "Registrar contato" | oportunidades/ | 🔮 Fase 3 |

## 5. Funil de leads (business-rules.md)

| Item | Ref | Status |
|------|-----|--------|
| Status PERDIDO volta à fila em 90 dias | workers/ | 🔴 |
| Score recalculado com novos dados de enriquecimento | workers/ | 🔴 |
| Lead sem website pula enriquecimento | technical_enrichment_service.py | ✅ |
| Lead sem contato não entra em outreach automático | — | 🔮 Fase 3 |

## 6. Dashboard (interface.md)

| Item | Ref | Status |
|------|-----|--------|
| Funil visual com Recharts | funnel-chart.tsx | ✅ |
| Leads por campanha (gráfico) | dashboard/ | 🔴 |
| Score médio por segmento | dashboard/ | 🔴 |
| Atividade recente (7 dias) | dashboard/ | 🔴 |
| Seção "O que fazer agora" | dashboard/ | 🔴 |
| Notificações no header | header.tsx (badge hardcoded "3") | 🟡 |

## 7. Campanhas/Wizard (interface.md)

| Item | Ref | Status |
|------|-----|--------|
| Wizard 4 etapas | campanhas/nova/page.tsx | ✅ |
| Botão "Me sugira segmentos" (IA) | campanhas/nova/page.tsx | 🔴 (botão existe, disabled) |
| IA gerar descrição do serviço | campanhas/nova/page.tsx | 🔴 |
| Campos: target_service, segment, city, state | API + model | ✅ |
| Seletor de perfil (digital vs industrial) | campanhas/nova/page.tsx | ⏳ ETAPA 3a |

## 8. Auth / Config (context.md — Pendências)

| Item | Ref | Status |
|------|-----|--------|
| Esqueci minha senha | — | 🔴 |
| Página de configurações (trocar senha, editar perfil) | /configuracoes | 🔴 (rota existe, sem conteúdo) |
| CSP para produção (nonces/hashes) | next.config | 🔴 |
| Rate limiting em auth (slowapi instalado) | api/ | ✅ |

## 9. Aprendizado contínuo (product-vision.md — Fase 5)

| Item | Ref | Status |
|------|-----|--------|
| Tabela `conversions` | models.py | 🔮 Fase 5 |
| Recalibração automática do scoring com 10+ conversões | scoring_service.py | 🔮 Fase 5 |

## 10. Multi-tenant / Alphamec (product-vision.md — Fase 6)

| Item | Ref | Status |
|------|-----|--------|
| Campanhas por área/setor | — | 🔮 Fase 6 |
| Dashboard por membro | — | 🔮 Fase 6 |
| Ranking de consultores | — | 🔮 Fase 6 |
| Convidar/remover membros | — | 🔮 Fase 6 |
| Relatórios exportáveis | — | 🔮 Fase 6 |

---

## Próximo passo imediato

**ETAPA 1** — Migration `analysis_profile` na tabela campaigns.
