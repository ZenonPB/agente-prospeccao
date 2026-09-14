# Documentação do Agente de Prospecção

> **Fonte de verdade documental — atualizado em 2026-09-13.**
>
> Estado de código de referência: `main` após PR #171 (`a6f8f4e`) + trabalho em
> andamento no PR #172. O código, migrations e testes continuam tendo
> precedência quando um documento divergir deste índice.

## Como ler esta pasta

A documentação é dividida em três classes.

| Classe | Significado |
|---|---|
| **LIVE** | Reflete o estado atual e é atualizada em toda mudança de arquitetura/capability. |
| **RUNBOOK** | Procedimento operacional; só é válido se compatível com a arquitetura LIVE. |
| **ADR/DECISÃO** | Registro de decisão; histórico é preservado, novas decisões são acrescentadas. |

## Documentos LIVE

- `00-status-mapa.md` — matriz de capacidades e estado real.
- `architecture.md` — arquitetura atual e limites de responsabilidade.
- `context.md` — contexto funcional e técnico para agentes/engenheiros.
- `roadmap.md` — sequência restante para AlphaMec RC e evolução posterior.
- `roadmap-vendas.md` — roadmap do CRM/operação comercial.
- `consolidacao.md` — decisões de consolidação e fontes de verdade.
- `pendencias-pos-consolidacao.md` — backlog residual real, sem itens já encerrados.
- `offer-profile.md` — contrato e runtime de OfferProfile.
- `controlled-learning.md` — learning versionado, aprovação e rollback.
- `ai-feedback-loop.md` — feedback humano e fronteiras de aprendizado.
- `crm-360-gap-map.md` — lacunas entre CRM atual e CRM operacional completo.
- `business-rules.md` — regras comerciais estáveis.
- `coding-standards.md` — padrões de implementação.
- `agents.md` — instruções específicas para agentes no diretório `docs/`.

## RUNBOOKS

- `uat-runbook.md` — UAT multi-workspace + campanha real AlphaMec.
- `baseline-operacional.md` — baseline de produção e critérios de aceite.
- `plano-qualidade-e-bi.md` — validações de qualidade e BI.

## ADR / decisões

- `decisions.md` — índice e decisões transversais.
- `adr/` — ADRs individuais. ADR não deve ser reescrito para fingir que a
  decisão sempre foi diferente; mudanças novas recebem nova decisão/supersede.

## Histórico

Relatórios de fases, auditorias e registros de execução antigos foram removidos
desta pasta em 2026-09-14 por já estarem implementados e superados pelos
documentos LIVE acima. O histórico completo permanece no git
(`git log -- docs/` recupera qualquer versão anterior).

## Estado canônico em 2026-09-13

A plataforma já possui multi-workspace, Unified Data Network federada,
Company/Person canônicas, OfferProfile versionado, OfferMatcher, discovery,
pre-scoring, enrichment, scoring, oportunidades versionadas, decisão de
contato, sequences/workflows, tarefas, CRM sync/adapters, analytics,
controlled learning com publicação/rollback, feedback de utilidade, Kanban e
Opportunity 360 read-only.

No PR #172, a consolidação avança em duas frentes: (1) o pipeline inteiro passa
a consumir o **OfferProfile efetivamente publicado por workspace**, com
isolamento por `ContextVar`; (2) Company 360 e Person 360 read-only entram como
visões canônicas do CRM. Essas capacidades só devem ser marcadas como
`COMPLETE` após CI final verde no mesmo HEAD e merge.

## Próxima sequência de entrega

1. concluir e validar PR #172 (runtime OfferProfile + Company/Person 360 + docs);
2. Opportunity 360 editável: owner, estágio, valor, notas, tarefas e ações em
   contrato único, sem duplicar fontes de verdade;
3. importador histórico seguro da planilha AlphaMec com preview/mapping/dedupe;
4. Filter Context compartilhado + BI interativo;
5. consolidar feedback/coaching/calibração somente sobre OfferProfile efetivo;
6. Golden Path troféus/eventos/MEJ e UAT multi-workspace;
7. campanha AlphaMec real, observabilidade e hardening final.

## Regra de sincronização

Toda PR que altera modelo de domínio, endpoint público, pipeline, segurança,
tenancy ou estado de uma capability deve atualizar ao menos este índice e o
LIVE diretamente afetado. Documentos históricos não recebem status novo; o
status atual vai para os documentos LIVE.
