# Mapa de status — fonte de verdade operacional

> **LIVE · atualizado em 2026-09-18.** Baseline: `main@446ca886f4a22addc672df9355ea59972bc86e2a`.
> Legenda: ✅ entregue tecnicamente · 🟠 validação operacional/evidência real pendente · ⬜ fora do caminho crítico/pendente.

| Capability | Estado | Limite atual |
|---|---:|---|
| Multi-workspace + RBAC/tenant isolation | ✅ | UAT adversarial e gates existentes; manter regressões. |
| Company/Person/Lead/Opportunity canônicos | ✅ | Não criar entidades paralelas. |
| Vertente / OfferProfile efetivo | ✅ | Catálogo + overlay tenant-scoped, publicação/rollback controlados. |
| Discovery federation / planner / budget | ✅ | Paid opt-in; free-first. |
| Brazil Company Registry | 🟠 | Código hardened até PR #207; falta snapshot oficial real. |
| Registry staging/activation/membership/scope | ✅ | COMPLETED != ACTIVE; scope filtrado persistido. |
| Registry performance real nacional | 🟠 | Bench sintético existe; distribuição real ainda não validada. |
| Registry → cnae_discovery | 🟠 | Código opt-in/fallback/shadow; validar no piloto real. |
| Public Web Intelligence | 🟠 | Código seguro/passivo; cobertura real depende de sites reais. |
| Entity resolution | 🟠 | Contrato/testes existem; falsos merges reais precisam de amostra. |
| Pre-scoring / scoring / OfferMatcher | ✅ | Inteligência técnica existe; eficácia comercial depende de outcomes. |
| Commercial Dimensions | 🟠 | Shadow; promoção proibida sem evidência real. |
| Evidence/provenance | 🟠 | Fundação existe; consolidar contrato ponta a ponta antes do Analyst. |
| AI Commercial Analyst | ⬜ | Evolução planejada da inteligência existente; não criar segundo motor. |
| People & Contact Intelligence | 🟠 | Validado tecnicamente; validar identidade/routability/cobertura real. |
| CRM / tasks / sequences / Kanban / 360 | ✅ | Sistema operacional tecnicamente entregue. |
| BI / Filter Context / coaching | ✅ | Eficácia depende de dados/outcomes reais. |
| Outcomes + feedback | ✅ | Captura existe; attribution real precisa ser preservada. |
| Controlled learning | ✅ | Human-in-the-loop; não há learning comercial confiável sem amostra real. |
| Learning-ready persistence 1.0 | 🟠 | Auditar versionamento de análise/evidência/model/policy no Golden Path. |
| Real E2E AlphaMec | 🟠 | Depende de dados reais e depois autorização comercial. |
| Production readiness técnico | ✅ | CI/rehearsal não substituem smoke/deploy real. |
| Deploy/operação AlphaMec | 🟠 | etapa final após E2E/hardening. |
| BigQuery/remote discovery produtivo | ⬜ | Deferred; avaliar somente após gold standard do Registry. |
| Omnichannel/Relationship/Autopilot avançados | ⬜ | Pós-1.0. |

## Estado do release

A arquitetura-base não é mais o gargalo. O release está em **feature freeze horizontal**. O principal gap é converter capacidade técnica em um Golden Path operacional comprovado.

Primeiro gate externo: piloto real do Data Engine em Araraquara. Até lá, usar `CODE COMPLETE / OPERATIONAL VALIDATION REQUIRED`, nunca “validado em produção”.

## Primeiro piloto

Landing Pages → clínicas de psicologia → Araraquara/SP → CNAE 8650-0/03 → ativas. Snapshot oficial, import scoped, zero outreach, zero paid providers, Commercial Dimensions shadow.

Critério final do piloto: exatamente um de `PILOT DATA PIPELINE VALIDATED`, `PILOT NEEDS FIXES` ou `PILOT BLOCKED`.
