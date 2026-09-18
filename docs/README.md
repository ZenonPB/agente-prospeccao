# Documentação do Agente de Prospecção

> **Fonte de verdade documental — atualizado em 2026-09-18.**
>
> Baseline de referência: `main@446ca886f4a22addc672df9355ea59972bc86e2a` (merge da PR #207). Código, migrations e testes prevalecem quando houver divergência.

## Como ler esta pasta

| Classe | Significado |
|---|---|
| **LIVE** | Estado atual; deve acompanhar mudanças de arquitetura/capability. |
| **RUNBOOK** | Procedimento operacional compatível com os documentos LIVE. |
| **ADR/DECISÃO** | Decisão arquitetural; histórico não é reescrito. |
| **HISTÓRICO/AUDITORIA** | Evidência de um HEAD específico; não substitui o estado LIVE. |

## Leitura obrigatória para trabalho novo

1. `alphamec-1.0.md` — freeze, baseline e escopo restante da 1.0;
2. `00-status-mapa.md` — capability map;
3. `context.md` — contexto técnico/funcional;
4. `architecture.md` e `business-rules.md`;
5. `roadmap.md`;
6. para Data Engine: `data-engine-brasil.md`, `data-engine-brasil-pilot.md` e `data-engine-real-pilot-runbook.md`.

## Estado canônico

A fundação técnica está madura: multi-workspace, entidades canônicas, Vertentes/OfferProfile efetivo, discovery, Registry, entity resolution, enrichment, scoring/OfferMatcher, People/Contact, CRM, outcomes, BI e controlled learning já existem.

As PRs #203–#207 endureceram o Brazil Company Registry com staging/ativação, membership versionado, health/provenance, redução de write amplification e scope persistido. O Data Engine permanece **CODE COMPLETE / OPERATIONAL VALIDATION REQUIRED** até usar snapshot oficial real.

A 1.0 está em **feature freeze horizontal**. O caminho crítico é: Data Engine real → Evidence Contract → AI Commercial Analyst → persistência learning-ready → E2E real → hardening/deploy → operação AlphaMec.

## Documentos LIVE

- `alphamec-1.0.md` — baseline/freeze e Definition of Done da reta final;
- `00-status-mapa.md`;
- `architecture.md`;
- `context.md`;
- `roadmap.md`;
- `data-engine-brasil.md`;
- `offer-profile.md`;
- `controlled-learning.md`;
- `ai-feedback-loop.md`;
- `business-rules.md`;
- `coding-standards.md`;
- `decisions.md`.

## RUNBOOKS

- `data-engine-real-pilot-runbook.md` — procedimento exato para o primeiro snapshot real;
- `data-engine-brasil-pilot.md` — contrato do piloto;
- `uat-runbook.md`;
- `baseline-operacional.md`;
- `plano-qualidade-e-bi.md`.

## Regra de sincronização

Toda PR que altera domínio, endpoint, pipeline, segurança, tenancy, Data Engine ou estado de capability atualiza o LIVE diretamente afetado. Não marcar validação operacional com base apenas em fixtures/CI. Não iniciar nova frente horizontal enquanto o freeze da 1.0 estiver vigente, salvo P1/P2 ou decisão explícita.
