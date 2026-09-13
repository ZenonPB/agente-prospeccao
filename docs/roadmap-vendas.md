# Roadmap de vendas / CRM

> **LIVE · atualizado em 2026-09-13.** Este roadmap trata do produto comercial.
> A sequência geral está em `roadmap.md` e o gap detalhado em
> `crm-360-gap-map.md`.

## Norte

Substituir a planilha da AlphaMec por um CRM interno que concentre conta,
pessoa, oportunidade, atividades, tarefas, ownership, estágio, valor, outcomes
e histórico — sem duplicar o domínio existente.

## Entregue

- Kanban comercial;
- owner e carteira;
- estágios/status e motivo de perda;
- valor e previsão;
- atividades auditáveis;
- tarefas via `CommercialTask`;
- cadências/sequences e workflows;
- Next Best Action;
- feedback de utilidade e score feedback;
- outcomes/conversões atribuídos;
- CRM adapters/sync;
- Opportunity 360 read-only.

## Em validação — PR #172

### Company 360 read-only

Conta consolidada com pessoas, leads/contextos, oportunidades, aliases,
tarefas, outcomes e timeline. Gestores veem a Company canônica mesmo se ainda
não houver Lead; CONSULTOR não usa a tela para inferir carteira alheia.

### Person 360 read-only

Pessoa consolidada com empresa, identidade/verificação/roteabilidade,
oportunidades relacionadas, tarefas, outcomes e timeline.

## Próxima fatia — Opportunity 360 editável

A tela 360 deve virar centro de operação da oportunidade reutilizando:

- `Lead.assigned_to_id` para owner;
- `Lead.status` / `negotiation_stage` para estágio;
- `Lead.value` e `expected_close_date`;
- `Lead.next_action_at`;
- `Lead.lost_reason`;
- `CommercialTask` para tarefas;
- `LeadActivity` para trilha;
- `Lead.notes` enquanto nota simples for suficiente.

As mutações devem ser org-scoped, validar membership/carteira, registrar
atividade quando relevante e invalidar caches React Query corretos.

## Importador histórico

Depois da edição 360, migrar a planilha sem torná-la uma nova fonte de verdade.
Fluxo:

1. upload;
2. preview sem escrita;
3. mapping de colunas;
4. validação;
5. normalização;
6. dedupe Company/Person/Lead;
7. confirmação;
8. import transacional/idempotente;
9. relatório por linha;
10. auditoria/provenance.

## Operação de lista

Necessidades para validar no UAT:
- global search Company/Person/Opportunity;
- filtros por owner/status/oferta/campanha/região/score/tarefa;
- seleção múltipla;
- atribuição em massa;
- mudança de estágio em massa apenas onde seguro;
- exportação CSV auditável;
- tags se o uso real justificar.

## BI do time comercial

Com Filter Context compartilhado:
- pipeline por estágio;
- conversão e ticket;
- aging/tempo por estágio;
- forecast simples e explicável;
- tarefas vencidas/próximas ações;
- utilidade de leads e motivos negativos;
- Precision@K/oferta/versão;
- performance de provider/origem;
- resultados por owner/campanha/segmento.

## Coaching

Filas acionáveis, não “insights” genéricos:
- sem próxima ação;
- tarefa vencida;
- oportunidade parada;
- reunião sem follow-up;
- proposta sem retorno;
- decisor ainda não acionável;
- lead útil com baixa prioridade ou lead não útil recorrente de uma mesma origem.

## Proposal / Contract

Deferidos até UAT provar necessidade de entidade própria. Não criar CRUD
especulativo. Caso necessário, modelar ciclo de vida, versionamento, arquivos,
aprovação e auditoria antes da UI.

## Definition of Done do CRM AlphaMec

O CRM substitui a planilha quando um usuário consegue executar toda a rotina
com segurança, sem recorrer à planilha para estado corrente, e quando import,
export, busca, ownership, pipeline, tarefas, histórico e BI são auditáveis e
tenant-safe.
