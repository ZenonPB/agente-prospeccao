# Consolidação do domínio e das fontes de verdade

> **LIVE · atualizado em 2026-09-13.** Este documento substitui mapas antigos
> de duplicação já resolvidos. Snapshots históricos continuam no repositório e
> estão classificados em `docs/README.md`.

## Objetivo

Evitar dois sistemas concorrentes para a mesma responsabilidade. Toda nova
feature deve primeiro localizar a fonte canônica existente e compor sobre ela.

## Entidades canônicas

| Conceito | Fonte de verdade |
|---|---|
| Workspace | `Organization` |
| Usuário no workspace | `OrganizationMember` |
| Conta | `Company` |
| Identificadores/aliases da conta | `CompanyAlias` |
| Pessoa/decisor | `Person` |
| Contexto de prospecção/venda | `Lead` |
| Oferta aplicável | `LeadOpportunityRow` |
| Histórico da avaliação | `LeadOpportunitySnapshot` |
| Tarefa | `CommercialTask` |
| Atividade/auditoria comercial | `LeadActivity` |
| Sequência | `SequenceTemplate/Enrollment/Execution` |
| Workflow | `WorkflowDefinition/Run` |
| Outcome | `CommercialOutcomeRow` |
| Feedback de utilidade | `LeadUsefulnessFeedback` |
| Feedback de score | `ScoringFeedback` |
| Configuração inteligente da oferta | `OfferProfile` / `OfferProfileVersion` |

## Company / Person / Lead

Não são duplicatas:

- Company = identidade durável da organização prospectada;
- Person = identidade durável de um contato/decisor;
- Lead = relação/contexto comercial em campanha/carteira.

Dados descobertos em Lead devem convergir para Company/Person quando a
identidade é suficientemente segura, mas Lead continua necessário para status,
owner, valor, campanha e workflow comercial.

## OfferProfile x CampaignScoringTemplate

A decisão de consolidação é:

**Pertence ao OfferProfile:** ICP, sinais, pesos, thresholds, exclusions,
providers/budgets, enrichment strategy, people discovery, buyer persona,
intent/timing, critérios de qualificação e learning versionado.

**Pode permanecer operacionalmente separado:** cadência e playbook quando
representarem política operacional e não uma segunda definição de ICP/scoring.

`CampaignScoringTemplate` permanece por compatibilidade, mas não deve evoluir
como segundo motor de learning concorrente. O mapa histórico detalhado está em
`vertentes-offerprofile-consolidation.md`.

## Runtime de OfferProfile

O catálogo base é fallback; uma publicação ativa por workspace é overlay.
No PR #172, o job liga o registry efetivo por `ContextVar`, fazendo consumidores
legados usarem a mesma configuração durante discovery, enrichment e scoring sem
estado global compartilhado.

## Timeline

Não existe uma tabela “timeline” apenas para apresentação. As telas 360
normalizam eventos reais vindos de Activity, Task, Outcome, Sequence, Workflow,
feedback e decisões existentes. O contrato de apresentação pode unificar:

`type / occurred_at / actor / title / description / source_entity / metadata`

mas o dado continua pertencendo à entidade fonte.

## CRM externo x CRM interno

Adapters Pipedrive/HubSpot/Salesforce não são fonte de verdade primária do
produto. O domínio interno é canônico e sync precisa ser:

- org-scoped;
- idempotente;
- conservador;
- auditável;
- tolerante a falha externa;
- sem apagar silenciosamente dados internos.

## Learning

Há um único caminho seguro de mudança de configuração:

`evidência → comparação → proposta → aprovação → publicação versionada → rollback`.

Feedback ou outcome sozinho não altera produção. O registry publicado no
workspace precisa ser o mesmo consumido pelo pipeline.

## Proposal / Contract / Note

Ainda não são entidades canônicas independentes. Não criar por estética de CRM.
Se UAT provar ciclo de vida próprio, modelar com requisitos explícitos antes do
CRUD.

## Regras para novas mudanças

Antes de criar tabela/serviço:

1. qual conceito de domínio ela representa?
2. já existe fonte canônica?
3. pode ser derivado em leitura?
4. precisa histórico próprio ou apenas Activity?
5. qual o escopo de tenant?
6. como será idempotente?
7. como será auditável?
8. qual teste prova ausência de vazamento/N+1?

Se essas respostas não justificarem nova persistência, reutilize o domínio.
