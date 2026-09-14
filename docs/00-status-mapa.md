# Mapa de status — fonte de verdade operacional

> **LIVE · atualizado em 2026-09-14.** Código/migrations/testes prevalecem.
> Leia também `docs/README.md` e `docs/roadmap.md`.

Legenda: ✅ completo no escopo técnico atual · 🟠 depende de evidência externa/produção · ⬜ pendente.

| Capability | Estado | Evidência / limite atual |
|---|---:|---|
| Multi-workspace + membership | ✅ | organization_id, org switcher, escopo de carteira, testes cross-tenant. |
| Secrets/quotas por workspace | ✅ | providers externos opt-in e resolução por organização. |
| Company canônica + aliases | ✅ | `companies`, `company_aliases`, resolução CNPJ/domínio/aliases. |
| Person canônica | ✅ | `persons`, confidence, verification, routability e vínculo à Company. |
| Discovery federado | ✅ | Places/CNAE/PNCP + adapters/registry/planner e métricas. |
| People discovery federado | ✅ | providers opt-in, role fit, gates de identidade/buyer role. |
| Event discovery | ✅ | eventos normalizados, contexto declarativo, matching, timing/expiração e ação recomendada. |
| Event Intelligence | ✅ | regras fora do core, contexto MEJ/esportivo/fallback, séries recorrentes, demanda inferida e persistência PostgreSQL. |
| Pre-scoring | ✅ | config declarativa, auditoria de descartes e provenance. |
| Enrichment waterfall | ✅ | steps/estratégia/custo/gates declarativos. |
| OfferProfile base | ✅ | catálogo validado + ofertas AlphaMec. |
| Prospecting Intelligence / Golden Paths | ✅ | landing page, sistemas web, engenharia e troféus com quality gates, UNKNOWN≠FALSE, benchmark de regressão e gate CI. |
| Golden Path troféus/eventos/MEJ | ✅ | contexto MEJ/esportivo declarativo, timing comercial, oferta específica, idempotência e E2E PostgreSQL; conversão real ainda depende de campanha. |
| OfferProfile versionado por workspace | ✅ | publicação controlada, single-active e rollback exato. |
| OfferProfile efetivo no pipeline inteiro | ✅ | registry efetivo tenant-safe por job; discovery/enrichment/scoring consomem overlay da organização. |
| OfferMatcher + snapshots | ✅ | matcher-v2, score breakdown, quality gates e histórico append-only. |
| Opportunity attribution | ✅ | conversion/outcome ligados à oportunidade/versão/snapshot. |
| Next Best Action | ✅ | decisão persistida + roteabilidade + tarefas. |
| Sequences | ✅ | templates/versionamento/enrollment/execution. |
| Workflows | ✅ | definições/runs auditáveis; sem segundo caminho oculto de envio. |
| Kanban comercial | ✅ | estágios, owner e operações existentes. |
| Feedback útil/não útil | ✅ | motivo fechado, org-scoped, auditável. |
| Score feedback | ✅ | feedback numérico humano e trilha. |
| Controlled learning | ✅ | outcomes atribuídos → calibração → replay histórico → comparação conclusiva → aprovação humana → snapshot candidato persistido → publicação explícita → rollback. |
| Learning + Coaching — Bloco C | ✅ | gates de amostra/atribuição, geração conservadora de candidato, precision/recall no replay, publicação fail-closed do snapshot aprovado, coaching por consultor com evidência e gate PostgreSQL real. |
| CRM adapters/sync | ✅ | Pipedrive/HubSpot/Salesforce, idempotência e certificação read-only quando há credenciais. |
| Opportunity 360 read-only | ✅ | tenant-safe, timeline e query-count testado em PostgreSQL. |
| Company 360 | ✅ | leitura + edição canônica allowlist, concorrência otimista, auditoria e UI. |
| Person 360 | ✅ | leitura + edição/validação humana, concorrência otimista, auditoria e UI. |
| Opportunity 360 editável | ✅ | comandos canônicos, RBAC, tarefas idempotentes/race-safe, editor web e suíte PostgreSQL no CI. |
| Importador histórico AlphaMec | ✅ | lifecycle CSV/XLSX com preview/mapping/dry-run, dedupe conservador, contexto comercial histórico, confirmação idempotente, relatório por linha e E2E PostgreSQL. |
| Sales Operating System — Bloco B | ✅ | Central comercial, fila diária, busca global, carteira operacional, saved views, tags/arquivamento, bulk de estágio/campanha/sequência/tarefas, export auditável e RBAC/tenant isolation. |
| Filter Context compartilhado | ✅ | contrato único URL/API para período, campanha, consultor, oferta/versão, canal, status, score, outcome, atribuição, busca, segmento, cidade/UF e estágio de negociação. |
| BI interativo final | ✅ | analytics/export usam o mesmo Filter Context; filtros server-side/restauráveis, saved views e cross-filter sobre as dimensões comerciais principais. |
| Coaching comercial | ✅ | dashboard por time/consultor, SLA, timing de primeiro contato e reunião→proposta; toda recomendação carrega evidência e é rotulada como associação, não causalidade. |
| UAT multi-workspace — D1 | ✅ | cenário adversarial AlphaMec × Vendas Samuel e Zenon no PostgreSQL real, mesmo usuário em papéis distintos, UUID cross-tenant conhecido, dados espelhados e registry efetivo isolado. |
| Production readiness — D2 | ✅ | retry/backoff/circuit-breaker/cache tenant-first/redaction, verifier fail-closed, migrations idempotentes e backup→restore ensaiado na CI; health isolado não é tratado como prova de provider. |
| Campaign release + medição — D3 | ✅ | matriz das principais ofertas, DRY_RUN/REHEARSAL, LIVE_AUTHORIZED fail-closed, teto de custo/contatos e funil observacional canônico com attribution/calibration readiness. |
| AlphaMec 1.0 — Bloco E | ✅ | navegação simplificada, ajuda orientada ao fluxo real, tutorial robusto pausável/retomável, API 1.0 e diagnóstico manual seguro de Google/Groq/Hunter sem exposição de segredos. |
| Campanhas externas AlphaMec com outcomes reais | 🟠 | dependem de contatos, consentimento/base aplicável, credenciais/provider habilitado no workspace e autorização humana em produção; CI não fabrica conversão. |

## Limites do estado atual

- O benchmark do Bloco A é **sintético e de regressão**. Ele protege roteamento, evidência, genericidade e confiança, mas não prova conversão comercial.
- O Bloco B está tecnicamente fechado como sistema operacional de vendas.
- O Bloco C está tecnicamente fechado: calibração, replay, aprovação, publicação, rollback e coaching possuem gates automatizados. Os thresholds são proteções de produto; sua eficácia comercial depende de amostra real.
- O Bloco D fecha tecnicamente o UAT multi-workspace, o production rehearsal e o contrato seguro para campanhas controladas. O rehearsal usa PostgreSQL real e nunca é apresentado como contato comercial real.
- O Bloco E fecha a experiência 1.0: simplifica a linguagem, orienta o fluxo operacional, permite pausar/retomar o tutorial e oferece teste manual das conexões sem persistir ou devolver chaves em claro.
- `precision@K`, resposta, reunião, proposta, contrato e receita **de mercado** só podem ser afirmados após campanhas externas autorizadas com outcomes atribuídos.
- Contexto de evento e estimativas derivadas permanecem `INFERENCE`; ausência de evidência permanece `UNKNOWN`.
- Backup/restore da CI prova o procedimento técnico em PostgreSQL efêmero; retenção, criptografia at-rest e restauração do backup real continuam responsabilidade do ambiente de produção.

## Release técnico AlphaMec 1.0

A/B/C/D/E possuem gates automatizados. O merge da 1.0 exige, no mesmo HEAD, Web lint/TypeScript/build, compileall + pytest `-W error`, migrations/seed/verifiers, backup→restore, todos os E2E PostgreSQL anteriores e o gate de provider diagnostics. Após o merge, a mesma CI deve passar novamente na `main`.

Segredos reais usados localmente permanecem fora do Git e da CI. O diagnóstico ao vivo consome o `.env` ou secret store do ambiente em que a aplicação roda; os testes automatizados usam doubles/placeholders e verificam explicitamente que nenhum segredo chega à resposta.

## Próxima fase — evidência operacional real

1. Autorizar explicitamente uma amostra controlada por oferta no workspace AlphaMec.
2. Habilitar somente os providers necessários, com quota e teto de custo.
3. Usar `Testar conexões` no ambiente real antes de liberar a operação.
4. Rodar campanhas externas com provenance/correlation/outcome attribution.
5. Aguardar volume suficiente para `calibration_ready` e usar o Bloco C para replay e aprovação humana de qualquer mudança.
6. Registrar performance e incidentes do ambiente real sem reclassificar ausência de evidência como sucesso.
