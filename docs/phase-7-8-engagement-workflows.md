# Engagement e workflows comerciais

Este ciclo evolui a cadência existente para um motor de engagement mais genérico e auditável e entrega a fundação operacional da automação comercial seguinte, sem criar um segundo caminho de envio automático de e-mail.

## Entregue neste ciclo

### Sequence Engine v2

- templates versionados e tenant-aware;
- etapas `EMAIL`, `CALL`, `LINKEDIN`, `WHATSAPP`, `RESEARCH`, `WAIT` e `CONDITION`;
- inscrições por lead/pessoa e execuções persistidas por etapa;
- chave de idempotência por inscrição/etapa;
- scheduler que apenas materializa tarefas e avança waits/condições;
- etapas externas viram `CommercialTask` para execução humana;
- reply inbound pausa inscrições ativas e unsubscribe encerra a sequência;
- a cadência de e-mail existente continua sendo o único caminho de SMTP automático, preservando verificação, opt-out, bounce handling e gates de entregabilidade já consolidados;
- página `/sequences` com builder, tarefas, workflows e histórico, incluindo estados de loading/erro/vazio e controles acessíveis.

### Next Best Action

- decisões persistidas em `next_best_action_decisions`;
- fingerprint para evitar duplicar a mesma decisão sobre o mesmo estado;
- `action`, `why`, `confidence`, `evidence`, `deadline` e `offer_key` persistidos;
- reaproveitamento do `NextBestActionService` determinístico já existente, sem novo modelo opaco de decisão.

### Workflow Engine

- contrato `TRIGGER -> CONDITIONS -> ACTIONS`;
- triggers allowlisted para lead criado/avaliado, intent, evento, contato, e-mail verificado, reply, reunião, ganho, dado desatualizado e saved-search match;
- condições allowlisted por oferta, score, intent, tamanho, persona, contactability, localização, provider, canal e lead;
- ações controladas para tarefa, matrícula em sequência, alerta, enrichment, rerank, webhook e intenção de sync CRM;
- execuções persistidas com chave única `organization + workflow + event_key`;
- webhook reutiliza a infraestrutura outbound já endurecida contra destinos inseguros;
- histórico de runs e desativação de workflows pela API/UI.

### CRM integration boundary

- `CRMAdapter` async e versionado em `services/workers/src/services/crm_adapters.py`;
- envelope canônico para `company`, `person`, `opportunity`, `commercial_outcome`, `owner` e `activity`;
- registry fail-closed para Pipedrive, HubSpot e Salesforce;
- nenhum provider é marcado como configurado sem adapter concreto, segredo e UAT reais;
- a ação `CRM_SYNC` do Workflow Engine gera uma tarefa explícita enquanto não existir adapter configurado, em vez de fingir sincronização.

## Persistência

A migration `9f1a3c5e7b8d` adiciona:

- `sequence_templates`;
- `sequence_enrollments`;
- `sequence_executions`;
- `commercial_tasks`;
- `next_best_action_decisions`;
- `workflow_definitions`;
- `workflow_runs`.

O verificador de migrations cobre tabelas, colunas, FKs, índices e unicidades essenciais do novo domínio.

## Limites intencionais deste ciclo

A Fase 7 fica coberta no núcleo operacional, mas não declara timing aprendido nem envio autônomo multicanal. `EMAIL`, LinkedIn e WhatsApp no Sequence Engine v2 são tarefas humanas; o e-mail automático continua no `cadence_service` legado endurecido.

A Fase 8 fica **parcial**: o Workflow Engine e o contrato de adapters estão operacionais, mas Pipedrive/HubSpot/Salesforce, sync bidirecional, CRM enrichment e produtores automáticos para todos os triggers ainda exigem implementação/credenciais específicas. Meeting e bounce continuam tratados nos fluxos existentes; a ligação automática desses eventos a todas as inscrições v2 permanece como hardening futuro.

## Critério de conclusão

O ciclo só pode ser mergeado quando o HEAD final passar por backend, migrations em PostgreSQL real, E2E crítico, lint, TypeScript e build de produção. UAT de providers/CRMs externos depende das credenciais reais do ambiente e não será declarado como concluído sem essa evidência.
