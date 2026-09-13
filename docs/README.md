# Documentação do Agente de Prospecção

> **Fonte de verdade documental — atualizado em 2026-09-13.**
>
> Estado de código de referência: `main` após PR #171 (`a6f8f4e`) + trabalho em
> andamento no PR #172. O código, migrations e testes continuam tendo
> precedência quando um snapshot histórico divergir deste índice.

## Como ler esta pasta

A documentação agora é dividida em quatro classes para evitar que documentos
de fases antigas sejam confundidos com o estado atual.

| Classe | Significado |
|---|---|
| **LIVE** | Deve refletir o estado atual e ser atualizada em toda mudança de arquitetura/capability. |
| **RUNBOOK** | Procedimento operacional; só é válido se compatível com a arquitetura LIVE. |
| **ADR/DECISÃO** | Registro de decisão; histórico é preservado, novas decisões são acrescentadas. |
| **SNAPSHOT HISTÓRICO** | Evidência de uma fase anterior. Não é fonte de verdade para status atual. |

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

## SNAPSHOTS HISTÓRICOS

Os arquivos abaixo permanecem no repositório por rastreabilidade, mas **não
representam o status atual**. Quando houver conflito, use os documentos LIVE.

- `phase-1-8-9-completion.md`
- `phase-2-company-people-search.md`
- `phase-3-4-data-intelligence.md`
- `phase-3-4-hardening-followups.md`
- `phase-5-6-offer-excellence-continuous-agent.md`
- `phase-7-8-engagement-workflows.md`
- `hardening-phases-1-6.md`
- `fix-scoring-saas-platforms.md`
- `hunter-provider.md`
- `auditoria-frontend.md`
- `alphamec-registro.md`
- `vertentes-offerprofile-consolidation.md` — snapshot da auditoria que levou à
  consolidação; riscos ainda abertos devem ser copiados para o roadmap LIVE.

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
