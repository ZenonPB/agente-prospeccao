# CRM 360 — mapa de gaps após a primeira leitura de oportunidade

> Estado desta fatia: composição **read-only** sobre dados já existentes. Nenhuma
> nova entidade comercial foi criada apenas para preencher a interface.

## O que já existe e foi reutilizado

| Capacidade | Fonte atual | Estado na visão 360 |
|---|---|---|
| Oportunidade por oferta | `lead_opportunities` | score, versão, sinais, evidências e breakdown consolidados |
| Empresa | `Company` + fallback dos campos do `Lead` | resumo cadastral/localização/site |
| Pessoa/decisor | `Person` canônica + `Contact` | decisor principal e contatos disponíveis |
| Dono da carteira | `Lead.assigned_to_id` | exibido com data de atribuição |
| Funil/forecast | campos comerciais do `Lead` | status, etapa de negociação, valor, previsão e motivo de perda |
| Próxima ação | `next_best_action_decisions` + fallback `Lead.next_action_at` | recomendação persistida quando existe |
| Tarefas | `commercial_tasks` | lista operacional, org-scoped |
| Atividades | `lead_activities` | trilha histórica já auditável |
| Feedback de qualidade | `lead_usefulness_feedbacks` | útil/não útil + motivo + autor |
| Outcomes | `commercial_outcomes` | somente outcomes atribuídos à oportunidade consultada |
| Sequências | `sequence_enrollments` / `sequence_executions` | contexto de execução, sem expor payload sensível |
| Workflows | `workflow_runs` | histórico resumido, sem expor contexto/payload interno |
| Timeline | derivada das fontes acima | contrato comum, sem tabela duplicada |

## Contrato de timeline

A timeline é derivada em leitura e normalizada para:

```text
type
occurred_at
actor
title
description
source_entity
metadata
```

Ordenação: mais recente primeiro; empates são resolvidos por `type` e
`source_entity`, tornando a resposta determinística.

A timeline não cria eventos sintéticos para preencher lacunas. O único fallback
permitido nesta fatia é transformar `Lead.next_action_at`, quando já persistido,
em uma próxima ação agendada.

## Company 360 — o que ainda falta

A entidade `Company` já consolida a identidade entre campanhas, mas a experiência
360 completa ainda precisa de:

- página própria da empresa, independente de um lead;
- lista consolidada de todas as pessoas e oportunidades da empresa;
- timeline da conta atravessando campanhas sem duplicação;
- notas estruturadas por conta;
- tags e segmentação operacional;
- owner da conta separado, caso o produto decida diferenciar de owner do lead;
- merge/revisão de identidade como fluxo de usuário para candidatos fuzzy;
- visão de saúde/freshness dos principais atributos;
- histórico de alterações relevantes com auditoria universal.

## Person 360 — o que ainda falta

A `Person` canônica e o histórico de emprego já existem. Para a operação de CRM
ficar completa ainda faltam:

- página própria da pessoa;
- oportunidades e atividades relacionadas em uma única visão;
- contatos/verificações com histórico e provenance apresentados de modo claro;
- owner/responsável de relacionamento quando necessário;
- notas e tarefas diretamente vinculadas à pessoa fora de uma sequência;
- merge/revisão de identidades duplicadas;
- indicação explícita de qual dado é atual, vencido ou precisa de revisão.

## Opportunity 360 editável — o que ainda falta

Esta fatia deliberadamente não cria edição nova. A próxima evolução do domínio
deve decidir, antes de adicionar tabelas, como separar `Lead` de oportunidade
comercial operacional. Hoje vários campos de negócio ainda vivem no `Lead`.

Pendências:

- edição de owner, estágio, valor, forecast e próxima ação a partir da própria 360;
- estágio comercial verdadeiramente por oportunidade quando um mesmo lead tiver
  mais de uma oferta simultânea;
- notas como entidade append-only/auditável, em vez de somente `Lead.notes`;
- tarefas manuais CRUD além das tarefas materializadas por sequences/workflows;
- busca/filtros globais por oportunidade;
- bulk actions preservando atribuição correta à oferta;
- permissões granulares de edição por papel;
- audit trail universal para todas as mutações.

## Propostas e contratos

Não foi encontrada uma entidade canônica `Proposal` nem uma entidade canônica
`Contract` no domínio atual. Existem campos de negociação no `Lead`, incluindo
`negotiation_stage`, `contract_outcome`, `value`, `expected_close_date` e outcomes
comerciais atribuídos.

Portanto, esta fatia **não fabrica** propostas ou contratos a partir desses
campos. Antes de implementar o ciclo completo, definir contratos de domínio para:

```text
Opportunity
├── Proposal (0..N)
└── Contract (0..N ou 0..1, conforme regra comercial aprovada)
```

com versionamento de proposta, valor, validade, status, autor, timestamps,
anexos/referências e auditabilidade. A decisão deve ser guiada pela planilha
real da AlphaMec e pelo importador histórico para evitar modelar um CRM teórico.

## Isolamento e desempenho desta fatia

- lookup raiz exige `(opportunity_id, organization_id)`;
- o `Lead` relacionado é novamente validado por `organization_id` e pelo escopo
  de carteira do membro;
- entidades que possuem `organization_id` também recebem filtro explícito;
- entidades legadas sem `organization_id` só são acessadas depois de validar o
  `lead_id` dentro do workspace;
- outcomes são filtrados pelo `lead_opportunity_id`, evitando misturar ofertas;
- usuários/atores são carregados em lote;
- número de queries é limitado por fonte, não pela quantidade de tarefas,
  atividades ou contatos.

## Próxima fatia recomendada

Antes de introduzir `Proposal`/`Contract`, a próxima fatia de CRM deve fechar a
**Company 360 read-only + Person 360 read-only**, reutilizando o mesmo princípio
de composição. Em paralelo, a Fase A ainda possui o risco já documentado de
registry global de `OfferProfile` em partes do pipeline; esse risco precisa ser
fechado antes da calibração/learning final.
