# Implementation Plan: AlphaMec Production Ready

## Overview

Quatro blocos executados em ordem: (1) invariantes de segurança e dado, com teste
red→green por invariante; (2) Golden Path da AlphaMec; (3) UAT real com registro e
decisão do provider de eventos; (4) BI mínimo de operação. O Bloco 4 pode ser
executado em paralelo ao Bloco 3, exceto as tarefas marcadas como OPCIONAL, que
dependem do resultado do UAT.

Restrições verificadas no repositório antes deste plano:

- `hypothesis` **não** está em `requirements-dev.txt` (que hoje traz apenas
  `pytest==9.1.1` mais os requirements dos dois serviços). Adicionar a dependência
  exige confirmação humana (tarefa 1.2).
- `apps/web` **não tem** suíte de teste de componente: `package.json` não declara
  script `test` nem vitest/jest. Toda tarefa de "teste de componente" deste plano
  declara a alternativa usada e **não** introduz framework novo sem confirmação.
- As migrations ficam em `services/workers/migrations/versions/` (não em
  `alembic/versions/`, como o design escreveu).

## Tasks

### Bloco 1 — Segurança e invariantes

- [x] 1. Preparação de execução e decisões de ferramenta
  - [x] 1.1 Confirmar a branch de trabalho
    - Rodar `git rev-parse --abbrev-ref HEAD`; se não for `feat/alphamec-production-ready`, criar a branch a partir de `main @ 27d2925` com `git checkout -b feat/alphamec-production-ready 27d2925`
    - Rodar `git status --short` e registrar que a árvore está limpa antes de começar
    - _Requirements: 23.5_

  - [x] 1.2 Decidir a ferramenta de property-based testing — EXIGE CONFIRMAÇÃO HUMANA
    - Confirmado que `hypothesis` não está em `requirements-dev.txt` nem nos requirements dos serviços
    - Perguntar ao humano se `hypothesis` pode ser adicionada pinada em `requirements-dev.txt`; não instalar nada antes da resposta
    - Se aprovado: adicionar a linha pinada e usar Hypothesis nas tarefas de propriedade
    - Se não aprovado: usar geradores determinísticos próprios (`random.Random(seed)` com seed fixa e ≥100 iterações por propriedade, em helper de `tests/`), sem dependência nova
    - Registrar a decisão em `docs/alphamec-registro.md`
    - _Requirements: 21.2_

  - [x] 1.3 Criar o registro de execução da spec
    - Criar `docs/alphamec-registro.md` com as seções: decisões de ferramenta, evidência red→green por invariante, contagens prévias de migration, Pontos_De_Parada, findings classificados, decisão do provider de eventos, gates executados
    - Declarar na seção de ferramenta que `apps/web` não possui runner de teste: a verificação de componente será feita por (a) módulo puro em TypeScript coberto pelo runner nativo `node --test`, quando o Node do ambiente carregar TS diretamente, (b) teste de contrato estático em `tests/` lendo o arquivo-fonte do componente, e (c) browser QA com evidência anexada — sem introduzir framework de teste novo sem confirmação humana
    - _Requirements: 16.4, 21.1_

- [ ] 2. Invariante: tenant determinístico no inbound de e-mail
  - [x] 2.1 Escrever o teste que reproduz o vazamento cross-tenant (deve FALHAR antes da correção)
    - Criar `tests/test_inbound_tenant_isolation.py` com duas organizações, cada uma com um lead do mesmo endereço de remetente
    - Assertar que o inbound autenticado para a organização A afeta somente o lead de A e que zero `Message` é criada no lead de B
    - Assertar `401` e zero persistência para credencial ausente/inválida, e `matched=false` com zero persistência quando não há lead na organização resolvida
    - Rodar `python -m pytest tests/test_inbound_tenant_isolation.py -q` e registrar a falha (red) em `docs/alphamec-registro.md` antes de qualquer correção
    - _Requirements: 1.6, 2.4, 21.1_
    - _Properties: P1, P2, P3_

  - [x] 2.2 Adicionar `Organization.inbound_token_hash` ao modelo único
    - Em `services/workers/src/database/models.py`, adicionar a coluna `inbound_token_hash` (`String(64)`, nullable) com índice único
    - Não remover nem alterar coluna existente; confirmar que `services/api/src/db/models.py` continua apenas reexportando
    - _Requirements: 8.1, 8.2, 22.6_

  - [x] 2.3 Criar o serviço de token de inbound
    - Criar `services/api/src/services/inbound_token_service.py` com `hash_inbound_token`, `generate_inbound_token` e `resolve_organization_by_token`, conforme o design (lookup por igualdade sobre o hash, limite de tamanho do token, retorno de no máximo uma organização)
    - Usar `logging`, nunca `print`
    - _Requirements: 1.1_
    - _Properties: P1_

  - [ ] 2.4 Confinar `process_inbound_email` à organização resolvida
    - Em `services/api/src/services/inbound_email_service.py`, tornar `organization_id` parâmetro obrigatório e trocar `Lead.organization_id.isnot(None)` por `Lead.organization_id == organization_id`
    - Adicionar a guarda defensiva que faz rollback e retorna `matched=False` se `lead.organization_id` divergir do parâmetro
    - Manter o retorno `matched=False` antes de qualquer `db.add`, sem commit
    - _Requirements: 1.3, 1.4, 1.5, 2.1, 2.2, 2.3_
    - _Properties: P1, P2, P3_

  - [ ] 2.5 Publicar as rotas por token e endurecer as rotas legadas
    - Em `services/api/src/routes/webhooks.py`, criar `POST /api/webhooks/email/inbound/{token}` e `POST /api/webhooks/import/{token}` resolvendo a organização pelo token antes de qualquer consulta de domínio, com `401` e frase fixa quando não resolver
    - Fazer as rotas sem token exigirem `X-Webhook-Secret` **e** `X-Organization-Id`, respondendo `401` sem persistência quando a organização não for resolvível; marcar como depreciadas na docstring e na descrição OpenAPI
    - Rodar `python -m pytest tests/test_inbound_tenant_isolation.py tests/test_webhook_import.py -q` e registrar o green
    - _Requirements: 1.1, 1.2, 1.5_
    - _Properties: P1, P3_

  - [ ] 2.6 Criar o script de geração do token de inbound por organização
    - Criar `services/workers/src/scripts/gerar_inbound_token.py` que recebe o identificador da organização, gera o par (token em claro, hash), grava só o hash e imprime o token em claro uma única vez na saída do comando
    - Não persistir o token em claro em nenhum arquivo nem log
    - _Requirements: 1.1, 13.1_

  - [ ] 2.7 Escrever as propriedades de isolamento do inbound
    - Criar `tests/test_inbound_tenant_properties.py` com a ferramenta decidida em 1.2, ≥100 iterações por propriedade
    - **Property 1: Inbound confinado à organização** — o lead afetado tem `organization_id == O` ou nenhum lead é afetado
    - **Property 2: Escrita confinada à organização** — `Message`, `LeadActivity`, `FollowUp` e `Notification` criados pertencem ao lead da organização resolvida
    - **Property 3: Ausência de efeito sem correspondência** — contagens de todas as tabelas envolvidas inalteradas
    - Marcar como skip automático sem `E2E_DATABASE_URL`, no mesmo padrão de `tests/e2e_outreach_cycle.py`
    - _Requirements: 1.6, 2.4_
    - _Properties: P1, P2, P3_

- [ ] 3. Invariante: falha fechada em job e WebSocket
  - [x] 3.1 Escrever o teste que reproduz o job órfão autorizado (deve FALHAR antes da correção)
    - Criar `tests/test_job_ws_fail_closed.py` com stub de WebSocket cobrindo: `Job.organization_id` nulo, job de outra organização e job inexistente
    - Assertar `close(code=403)` nos três casos e igualdade exata da tupla (código, razão) entre inexistente e de outra organização
    - Assertar zero mensagens de progresso emitidas
    - Rodar o arquivo e registrar a falha (red) em `docs/alphamec-registro.md`
    - _Requirements: 3.6, 21.1_
    - _Properties: P4, P5_

  - [x] 3.2 Tornar a autorização do WebSocket fail-closed
    - Em `services/api/src/routes/pipeline.py`, trocar a guarda por `job is None or job.organization_id is None or str(job.organization_id) != str(org.id)`, com o mesmo `close(code=403, reason=...)` nos três casos
    - Rodar `python -m pytest tests/test_job_ws_fail_closed.py -q` e registrar o green
    - _Requirements: 3.1, 3.2, 3.3_
    - _Properties: P4, P5_

  - [ ] 3.3 Cobrir a criação de job e a listagem HTTP com escopo de organização
    - Criar `tests/test_job_org_scope.py` assertando `organization_id is not None` nos quatro pontos de criação (`routes/pipeline.py`, reanálise e coletas CNAE/PNCP em `routes/campaigns.py`)
    - Assertar que `GET /api/pipeline/jobs` não retorna job com `organization_id` nulo nem job de outra organização
    - _Requirements: 3.4, 3.5_
    - _Properties: P4, P6_

  - [ ] 3.4 Escrever as propriedades de autorização de job
    - Criar `tests/test_job_ws_properties.py` com a ferramenta decidida em 1.2
    - **Property 4: Falha fechada de job** — bicondicional sobre matriz gerada de jobs × usuários
    - **Property 5: Indistinguibilidade da recusa** — tuplas (código, razão) idênticas
    - _Requirements: 3.6_
    - _Properties: P4, P5_

- [ ] 4. Invariante: estados terminais fora da cadência
  - [x] 4.1 Escrever os testes que reproduzem o envio para lead terminal (devem FALHAR antes da correção)
    - Criar `tests/test_cadence_terminal_status.py` com SMTP stubado: `send_step` para lead `PERDIDO` e para lead `DESQUALIFICADO`, e `run_due` com população mista
    - Assertar zero e-mail enviado, zero `Message` criada, etapa marcada `SKIPPED` com motivo registrado, e conjunto de `run_due` disjunto dos follow-ups de leads terminais
    - Assertar `FollowUp` `PENDING` igual a zero após a transição terminal
    - Rodar o arquivo e registrar a falha (red) em `docs/alphamec-registro.md`
    - _Requirements: 4.5, 21.1_
    - _Properties: P7, P8, P9_

  - [x] 4.2 Bloquear a cadência em estado terminal nos três pontos
    - Em `services/api/src/services/cadence_service.py`: definir `TERMINAL_STATUSES`, adicionar a guarda em `send_step` logo após o early-return de `SENT` (antes de resolver destinatário ou enviar), com `SKIPPED` e `log_event("cadence_skipped", reason="terminal_status", ...)`
    - Adicionar `& (~Lead.status.in_(TERMINAL_STATUSES))` ao filtro de `run_due`, usando operadores SQLAlchemy (`&`, `~`)
    - Criar `cancel_pending_for_terminal(db, lead, reason)` sem commit próprio, ao lado de `mark_opt_out`, cancelando todo `FollowUp` `PENDING`
    - Rodar `python -m pytest tests/test_cadence_terminal_status.py tests/test_cadence_run_due.py tests/test_cadence_close.py -q` e registrar o green
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
    - _Properties: P7, P8, P9_

  - [ ] 4.3 Escrever as propriedades de estado terminal
    - Criar `tests/test_cadence_terminal_properties.py` com a ferramenta decidida em 1.2
    - **Property 7: Estado terminal absorve a cadência** — zero `Message` com `sent_at > t`
    - **Property 8: Seleção de vencidos exclui terminais** — disjunção do conjunto de `run_due`
    - **Property 9: Sem pendências após terminal** — `PENDING` igual a zero por qualquer caminho de transição
    - _Requirements: 4.5_
    - _Properties: P7, P8, P9_

- [ ] 5. Invariante: motivo obrigatório em PERDIDO
  - [x] 5.1 Escrever o teste que reproduz PERDIDO sem motivo (deve FALHAR antes da correção)
    - Criar `tests/test_lead_lost_reason_required.py` com `TestClient`: `PATCH /api/leads/{id}/status` com `status=PERDIDO` e sem `lost_reason`
    - Assertar `422`, `Lead.status` e `Lead.lost_reason` inalterados, e ausência de `LeadActivity` nova
    - Assertar que `PERDIDO` grava `LeadActivity` de ação `LOST` com o motivo e que `DESQUALIFICADO` grava trilha distinta
    - Rodar o arquivo e registrar a falha (red) em `docs/alphamec-registro.md`
    - _Requirements: 5.5, 21.1_
    - _Properties: P10, P11, P13_

  - [ ] 5.2 Exigir o motivo no schema de atualização de status
    - Em `services/api/src/routes/leads.py`, adicionar `model_validator(mode="after")` em `UpdateLeadStatusRequest` que rejeita `status=PERDIDO` com `lost_reason` nulo
    - Confirmar que a rejeição ocorre antes de qualquer acesso ao banco
    - _Requirements: 5.1_
    - _Properties: P11_

  - [ ] 5.3 Criar o ponto único de transição de status e ligar os consumidores
    - Criar `services/api/src/services/lead_status_service.py` com `transition_lead_status`, conforme o design: motivo obrigatório em `PERDIDO`, trilha `LOST` com motivo, trilha `STATUS_CHANGED` para `DESQUALIFICADO`, chamada de `cancel_pending_for_terminal` em estado terminal, `db.flush()` sem commit
    - Em `services/api/src/routes/leads.py`, fazer `PATCH /{lead_id}/status`, `POST /{lead_id}/mark-lost` e `POST /{lead_id}/mark-disqualified` usarem essa função, mantendo `_record_commercial_outcome` no chamador com a mesma chave de evento
    - Rodar `python -m pytest tests/test_lead_lost_reason_required.py tests/test_requeue_lost.py tests/test_conversion_idempotent.py -q` e registrar o green
    - _Requirements: 5.2, 5.3, 5.4, 4.3_
    - _Properties: P10, P13, P17_

  - [ ] 5.4 Escrever as propriedades de perda e trilha
    - Criar `tests/test_lead_status_properties.py` com a ferramenta decidida em 1.2
    - **Property 10: Perda implica motivo** — sobre sequências de requisições aceitas geradas
    - **Property 11: Rejeição preserva estado**
    - **Property 13: Perda e desqualificação não colapsam**
    - **Property 17: Idempotência de outcome** — repetição da mesma chave de evento não aumenta outcomes
    - _Requirements: 5.5_
    - _Properties: P10, P11, P13, P17_

- [ ] 6. Invariante: ação em lote sem bypass do motivo
  - [x] 6.1 Escrever o teste de contrato que reprova o caminho fraco (deve FALHAR antes da correção)
    - Criar `tests/test_bulk_lost_contract.py` lendo `apps/web/src/components/oportunidades/lead-list.tsx` como texto e assertando que a ação em lote de `PERDIDO` usa `markLost` e não `updateStatus`
    - Assertar a presença do diálogo de motivo antes do disparo e do resumo com contagem de sucessos e de falhas
    - Rodar o arquivo e registrar a falha (red) em `docs/alphamec-registro.md`
    - _Requirements: 6.1, 6.2, 21.1_
    - _Properties: P12_

  - [ ] 6.2 Exigir motivo na ação em lote do Painel_Oportunidades
    - Em `apps/web/src/components/oportunidades/lead-list.tsx`, fazer `bulkStatus('PERDIDO')` abrir o diálogo de motivo e retornar sem emitir requisição; confirmar o motivo dispara `markLost` por lead
    - Reaproveitar `useMarkLost` e `LOST_REASON_OPTIONS` de `hooks/use-api.ts` e o seletor de motivo do `OutcomeDialog`; usar a prop `render` do Base UI, nunca `asChild`
    - Cancelar fecha o diálogo com zero requisições; o resumo mostra sucessos e falhas; o toast de sucesso só sai após resposta bem-sucedida da API
    - Rodar `python -m pytest tests/test_bulk_lost_contract.py -q` e registrar o green
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
    - _Properties: P12_

  - [ ] 6.3 Verificar a equivalência lote ↔ individual
    - Estender `tests/test_bulk_lost_contract.py` com a verificação estática de que o lote usa exatamente o mesmo endpoint da marcação individual
    - **Property 12: Lote equivale a individual** — verificada pela alternativa declarada em 1.3 (contrato estático + browser QA), já que `apps/web` não tem runner de componente
    - _Requirements: 6.2, 6.4_
    - _Properties: P12_

- [ ] 7. Invariante: conversão única sob concorrência
  - [x] 7.1 Escrever o teste de concorrência que reproduz a duplicata (deve FALHAR antes da correção)
    - Criar `tests/test_conversion_unique_concurrency.py` com `E2E_DATABASE_URL` e skip automático sem banco, disparando n transações paralelas de conversão para o mesmo `lead_id` + `offer_key`, incluindo o caso `offer_key` nulo
    - Assertar contagem final de `Conversion` igual a 1, exatamente uma resposta de sucesso, demais `409`, e corpo sem nome de constraint, de tabela ou texto de exceção do banco
    - Rodar o arquivo e registrar a falha (red) em `docs/alphamec-registro.md`
    - _Requirements: 7.5, 21.1_
    - _Properties: P14, P15, P16_

  - [ ] 7.2 Declarar o índice único de expressão no modelo
    - Em `services/workers/src/database/models.py`, adicionar a `Conversion.__table_args__` o índice `uq_conversions_lead_offer` sobre `(lead_id, coalesce(offer_key, 'unknown'))` com `unique=True`, preservando `ix_conversions_lead_id`
    - Não remover nem alterar campo existente de `Conversion`
    - _Requirements: 7.3, 8.1, 8.2, 22.6_
    - _Properties: P14_

  - [ ] 7.3 Alinhar o check com a constraint e converter a violação em 409
    - Em `services/api/src/routes/leads.py`, mudar `find_duplicate_conversion` para filtrar por `lead_id` + `coalesce(offer_key, 'unknown')`, mantendo `lead_opportunity_id` na assinatura mas fora do filtro
    - Envolver `db.add`/`db.flush` de `register_conversion` em `try/except IntegrityError` com `db.rollback()`, log do erro completo e `HTTPException(409)` com frase de domínio fixa
    - Rodar `python -m pytest tests/test_conversion_idempotent.py tests/test_conversion_attribution.py -q` e registrar o resultado
    - _Requirements: 7.1, 7.2, 7.4_
    - _Properties: P14, P15, P16_

  - [ ] 7.4 Escrever as propriedades de conversão única
    - Criar `tests/test_conversion_unique_properties.py` com a ferramenta decidida em 1.2
    - **Property 14: Conversão única** — para qualquer n ≥ 1, sequencial ou concorrente, contagem final igual a 1
    - **Property 15: Exatamente um sucesso** — distribuição de status HTTP para n ≥ 2
    - **Property 16: Sem vazamento de erro de banco** — inspeção do corpo da resposta
    - _Requirements: 7.5_
    - _Properties: P14, P15, P16_

- [ ] 8. Migrations aditivas e gateadas
  - [ ] 8.1 Criar a revisão m1 — `organizations.inbound_token_hash`
    - Criar a revisão em `services/workers/migrations/versions/` adicionando a coluna `String(64)` nullable e o índice único, encadeada na cabeça atual
    - Não editar nenhuma migration existente; rodar `alembic heads` (CWD `services/workers`) e confirmar uma única cabeça
    - _Requirements: 8.1, 8.2, 8.5_

  - [ ] 8.2 Contagem prévia do CHECK de `lost_reason` — PARAR se houver conflito
    - Executar `SELECT count(*) FROM leads WHERE status = 'PERDIDO' AND lost_reason IS NULL;` e registrar o número em `docs/alphamec-registro.md`
    - Resultado `0` → liberar o `VALIDATE CONSTRAINT` da m2
    - Resultado `> 0` → **PARAR**, registrar Ponto_De_Parada com a contagem e as linhas em conflito e aguardar aprovação humana; não fazer backfill, não apagar linha, não remover a constraint
    - _Requirements: 8.4_

  - [ ] 8.3 Criar a revisão m2 — CHECK `ck_leads_lost_reason_required`
    - Criar a revisão adicionando `CHECK (status <> 'PERDIDO' OR lost_reason IS NOT NULL) NOT VALID`, encadeada na m1
    - Executar `ALTER TABLE leads VALIDATE CONSTRAINT ck_leads_lost_reason_required` somente se 8.2 devolveu zero; caso contrário deixar a constraint `NOT VALID` e manter o Ponto_De_Parada aberto
    - _Requirements: 8.1, 8.3, 8.4_
    - _Properties: P10_

  - [ ] 8.4 Contagem prévia de duplicatas em `conversions` — PARAR se houver conflito
    - Executar `SELECT lead_id, coalesce(offer_key,'unknown') AS ofr, count(*) FROM conversions GROUP BY 1,2 HAVING count(*) > 1;` e registrar o resultado em `docs/alphamec-registro.md`
    - Vazio → liberar a criação do índice na m3
    - Não vazio → **PARAR**, registrar Ponto_De_Parada com as linhas em conflito e aguardar decisão humana; não deduplicar, não apagar conversão
    - _Requirements: 8.4_

  - [ ] 8.5 Criar a revisão m3 — índice único `uq_conversions_lead_offer`
    - Criar a revisão com `CREATE UNIQUE INDEX uq_conversions_lead_offer ON conversions (lead_id, coalesce(offer_key, 'unknown'))`, encadeada na m2
    - Aplicar somente com o resultado de 8.4 vazio; downgrade remove apenas o índice criado
    - _Requirements: 8.1, 8.3, 8.4, 7.3_
    - _Properties: P14_

  - [ ] 8.6 Contagem prévia de `jobs.organization_id` nulo — PARAR se houver conflito
    - Executar `SELECT count(*) FROM jobs WHERE organization_id IS NULL;` e registrar o número em `docs/alphamec-registro.md`
    - Resultado `0` → liberar a m4
    - Resultado `> 0` → **PARAR**, registrar Ponto_De_Parada com a contagem e aguardar aprovação humana; não derivar organização por `campaign_id`, não apagar job, não remover coluna
    - _Requirements: 8.4, 3.4_

  - [ ] 8.7 Criar a revisão m4 — `jobs.organization_id NOT NULL` (condicional)
    - Criar a revisão encadeada na m3 aplicando `SET NOT NULL` na coluna, e aplicá-la somente se 8.6 devolveu zero
    - Rodar `alembic upgrade head` e `alembic heads` (CWD `services/workers`), confirmando aplicação sem erro e uma única cabeça; rodar `python -m pytest tests/test_verify_migrations.py -q`
    - Se 8.6 devolveu `> 0`, deixar a tarefa aberta com o Ponto_De_Parada registrado; a garantia de aplicação da tarefa 3.2 permanece em vigor
    - _Requirements: 8.1, 8.5, 3.4_
    - _Properties: P4_

- [ ] 9. Checkpoint do Bloco 1
  - Rodar `python -m pytest tests -q -W error` e `python -m compileall -q services/api services/workers`
  - Confirmar que cada invariante tem a evidência red→green registrada em `docs/alphamec-registro.md`
  - Ensure all tests pass, ask the user if questions arise.

### Bloco 2 — Golden Path AlphaMec

- [ ] 10. Contratos do Golden Path
  - [ ] 10.1 Enviar o parâmetro de início automático da coleta
    - Em `apps/web/src/app/(protected)/campanhas/nova/page.tsx`, navegar para `/campanhas/${campaign.id}?start=true` quando `startCollection` for verdadeiro e para `/campanhas` quando falso
    - _Requirements: 9.1, 9.3_
    - _Properties: P21_

  - [ ] 10.2 Garantir disparo único da coleta automática
    - Em `apps/web/src/components/campanhas/campaign-pipeline.tsx`, trocar o efeito atual por guarda de `useRef` que dispara `handleStart('collect')` no máximo uma vez por carregamento, resistente à dupla montagem do StrictMode do React 19
    - Confirmar em `apps/web/src/app/(protected)/campanhas/[id]/page.tsx` que `autoStart` continua vindo de `searchParams.get('start') === 'true'`, sem contrato novo
    - Garantir que progresso em execução e caminho de erro com nova tentativa continuam exibidos na página
    - _Requirements: 9.2, 9.4, 9.5_
    - _Properties: P21_

  - [ ] 10.3 Corrigir o valor do filtro "Meus Leads"
    - Em `apps/web/src/components/oportunidades/lead-list.tsx`, enviar `assigned: myLeadsOnly ? 'me' : undefined`, removendo o envio do UUID do usuário
    - _Requirements: 10.1_
    - _Properties: P19_

  - [ ] 10.4 Declarar o filtro aplicado no estado vazio
    - Em `apps/web/src/components/oportunidades/lead-list.tsx`, exibir estado vazio que nomeia o filtro "Meus Leads" quando ele está ativo e o resultado é vazio, com ação de limpar o filtro
    - _Requirements: 10.4_

  - [ ] 10.5 Escrever o teste de contrato do parâmetro `assigned`
    - Criar `tests/test_leads_assigned_contract.py` extraindo o `pattern` declarado em `GET /api/leads` (`services/api/src/routes/leads.py`) e o valor emitido por `lead-list.tsx`, assertando pertinência ao conjunto `me|none|any`
    - Assertar `422` para valor fora do contrato e que `assigned=me` retorna somente leads da organização ativa atribuídos ao usuário autenticado
    - _Requirements: 10.2, 10.3, 10.5_
    - _Properties: P19, P6_

- [ ] 11. Redirecionamento pós-login seguro
  - [ ] 11.1 Criar o helper de redirecionamento seguro
    - Criar `apps/web/src/lib/safe-redirect.ts` com `resolveSafeCallbackUrl` conforme o design: decodificação até estabilizar, rejeição de caracteres de controle, backslash, ausência de `/` inicial, `//` e `/\`, com fallback `/dashboard`
    - _Requirements: 11.2, 11.3_
    - _Properties: P20_

  - [ ] 11.2 Ligar o helper ao login e ao aceite de convite
    - Em `apps/web/src/app/(auth)/login/page.tsx`, substituir o `router.push('/dashboard')` fixo por `router.push(resolveSafeCallbackUrl(searchParams.get('callbackUrl')))`
    - Em `apps/web/src/app/(auth)/aceitar-convite/page.tsx`, usar o mesmo helper ao construir e ao consumir o `callbackUrl`, preservando a tela de divergência de e-mail e a ação de trocar de conta
    - _Requirements: 11.1, 11.4, 11.5_
    - _Properties: P20_

  - [ ] 11.3 Verificar a propriedade do redirecionamento
    - **Property 20: Redirecionamento interno** — para qualquer string, inclusive variantes percent-encoded, o destino é caminho relativo interno ou `/dashboard`
    - Executar pelo runner nativo do Node (`node --test` sobre o módulo puro), sem dependência nova; se o Node do ambiente não carregar TypeScript diretamente, registrar a limitação em `docs/alphamec-registro.md` e cobrir a mesma tabela de casos (`http://`, `https://`, `javascript:`, `data:`, `//host`, `/\host`, `%2F%2Fhost`, `%5Chost`, controle, vazio) por teste tabelado no mesmo módulo, sem introduzir framework de teste
    - _Requirements: 11.6_
    - _Properties: P20_

- [ ] 12. Vazio distinto de falha de provider
  - [ ] 12.1 Criar o mapeamento puro de estados de provider
    - Criar `apps/web/src/lib/provider-state.ts` com `ProviderState`, `Apresentacao` e `apresentarResultado`, devolvendo `sem-correspondencia` somente quando todos os providers consultados retornaram `EMPTY`, e `parcial`/`falha` nomeando os providers que falharam
    - _Requirements: 12.3, 12.4, 12.5, 22.4_
    - _Properties: P22_

  - [ ] 12.2 Aplicar loading, erro, vazio e parcial por região, com marcação de inferência
    - Consumir `apresentarResultado` em `apps/web/src/components/oportunidades/evidence-card.tsx`, `contacts-tab.tsx` e `why-prospect-signals.tsx`, cada região com seu próprio estado de carregamento, erro e nova tentativa
    - Exibir badge e tooltip de inferência em todo valor derivado de heurística ou LLM, distinto de dado com fonte verificada; usar shadcn/ui sobre Base UI com a prop `render`
    - Nunca apresentar `FAILED`, `DISABLED` ou `QUOTA_EXCEEDED` como ausência de resultados
    - _Requirements: 12.1, 12.2, 12.4, 12.5, 12.6, 22.3_
    - _Properties: P22, P23_

  - [ ] 12.3 Verificar as propriedades de apresentação honesta
    - **Property 22: Vazio distinto de falha** — mapeamento total sobre combinações geradas dos cinco estados
    - **Property 23: Inferência rotulada** — todo valor com origem heurística ou LLM sai marcado
    - Executar pela mesma alternativa declarada em 11.3, sem framework novo
    - _Requirements: 12.3, 12.4, 12.5, 12.6_
    - _Properties: P22, P23_

- [ ] 13. Checkpoint do Bloco 2
  - Rodar `npm run lint`, `npx tsc --noEmit` e `npm run build` em `apps/web`
  - Executar browser QA dos fluxos do Bloco 2 (criar e iniciar coleta, Meus Leads, lote de perda, convite com login intermediário, estados de provider) e anexar evidências em `docs/alphamec-registro.md`
  - Ensure all tests pass, ask the user if questions arise.

### Bloco 3 — UAT real (execução e registro)

- [ ] 14. Preparar o ambiente do UAT
  - [ ] 14.1 Conferir e registrar os três controles de Outreach_Assistido
    - Conferir `ENVIRONMENT` diferente de `production`, SMTP não configurado (`_is_smtp_configured()` falso) e `Organization.auto_send_email = False` para a organização do UAT
    - Registrar os três valores observados em `docs/alphamec-registro.md` antes de abrir a sessão; se qualquer controle estiver fora do esperado, **PARAR** e registrar Ponto_De_Parada sem executar o roteiro
    - _Requirements: 13.4_

  - [ ] 14.2 Provisionar a organização e o token de inbound do UAT
    - Aplicar `alembic upgrade head` no Postgres real (CWD `services/workers`), criar a organização de teste e gerar o token com `services/workers/src/scripts/gerar_inbound_token.py`, guardando o token fora do repositório
    - Registrar em `docs/alphamec-registro.md` que a URL de inbound do provedor precisa apontar para a rota com token
    - _Requirements: 13.1, 1.1_

  - [ ] 14.3 Subir API e web reais para a sessão
    - Subir `uvicorn main:app --port 8000` com CWD `services/api` e `npm run dev` em `apps/web`, confirmando `GET /health` e login pela interface
    - Registrar as versões e os providers realmente disponíveis (Google Places, Groq) em `docs/alphamec-registro.md`
    - _Requirements: 13.1_

- [ ] 15. Executar o UAT e registrar o resultado
  - [ ] 15.1 Executar o roteiro do Golden Path com a Oferta_TROFEUS
    - Executar `docs/uat-runbook.md` de ponta a ponta na sessão real, registrando por item o resultado observado e a evidência em `docs/alphamec-registro.md`
    - Item não executável no ambiente é registrado como não executado com a causa, nunca como aprovado
    - _Requirements: 13.1, 13.2, 13.5, 13.6, 23.2_

  - [ ] 15.2 Preencher no mínimo dez fichas de nove itens
    - Criar `docs/alphamec-uat-fichas.md` com uma ficha por oportunidade da Oferta_TROFEUS, cobrindo os nove itens (existência real, evidência rastreável, plausibilidade do score, utilidade do timing, organizador correto, decisor útil, contato disponível, próxima ação, abordagem sugerida) mais o veredito
    - Evidência não localizável na fonte declarada reprova o veredito; valor inferido apresentado como fato verificado gera Finding `BLOCKS_ALPHAMEC`
    - Registrar a proporção de oportunidades comercialmente úteis e a proporção de fichas com evidência localizável
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_
    - _Properties: P23_

  - [ ] 15.3 Executar o smoke das Ofertas_Smoke
    - Executar discovery, scoring e visualização de oportunidade para SISTEMAS/ERP e para ENGENHARIA, registrando resultado e evidência por oferta em `docs/alphamec-registro.md`
    - _Requirements: 13.3_

  - [ ] 15.4 Registrar e classificar os findings do UAT
    - Registrar cada Finding em `docs/alphamec-registro.md` com exatamente uma classificação `BLOCKS_ALPHAMEC`, `IMPORTANT_ALPHAMEC` ou `DEFER_TO_V2`, com impacto e custo
    - Corrigir nesta branch todos os `BLOCKS_ALPHAMEC`; admitir `IMPORTANT_ALPHAMEC` só com impacto alto e custo baixo ou médio; deixar `DEFER_TO_V2` sem alterar código
    - Registrar se alguma etapa do Golden Path exigiu intervenção de desenvolvedor (nesse caso classificar como `BLOCKS_ALPHAMEC`)
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 23.3_

  - [ ] 15.5 Decidir o provider de eventos pelos limiares
    - Comparar os números de 15.2 com os limiares definidos antes do UAT: ≥60% de oportunidades comercialmente úteis e ≥80% de fichas com evidência localizável
    - Ambos atingidos → registrar o provider especializado MEJ/eventos como `DEFER_TO_V2` com os números que sustentam a decisão
    - Qualquer um abaixo → registrar como `BLOCKS_ALPHAMEC` e liberar a tarefa 16
    - Registrar a decisão e os dados observados em `docs/alphamec-registro.md` **antes** de qualquer implementação decorrente
    - _Requirements: 15.1, 15.2, 15.3, 15.5_

- [ ] 16. OPCIONAL — provider especializado MEJ/eventos
  - [ ] 16.1 Implementar o provider especializado somente se os limiares não foram atingidos
    - Executar apenas se 15.5 classificou o provider como `BLOCKS_ALPHAMEC`; se `DEFER_TO_V2`, deixar a tarefa não executada com a referência à decisão registrada
    - Implementar sobre o contrato de provider já existente em `services/workers/src/services/`, sem abstração paralela, registrando provenance, confiança e os cinco estados `FOUND`, `EMPTY`, `FAILED`, `DISABLED`, `QUOTA_EXCEEDED`
    - Usar `httpx.AsyncClient`, `logging` e configuração via `src/config/settings.py`; qualquer chave nova exige confirmação humana antes de ser adicionada ao `.env.example`
    - _Requirements: 15.2, 15.4, 22.3, 22.4_

  - [ ] 16.2 Escrever os testes do provider especializado
    - Criar `tests/test_mej_event_provider.py` cobrindo provenance, confiança e os cinco estados, com HTTP stubado (nenhuma chamada real a provider pago)
    - _Requirements: 15.4, 22.4_
    - _Properties: P22_

### Bloco 4 — BI mínimo de operação

- [ ] 17. Funil de operação no Servico_BI
  - [ ] 17.1 Estender o funil para sete etapas monotônicas e dois outcomes separados
    - Em `services/api/src/services/analytics_service.py`, reescrever `build_funnel_stages` e `funnel` com a cadeia `encontrados, qualificados, abordados, respostas, reunioes, propostas, ganhos` derivada da mesma base org-scoped
    - Expor `perdas` e `desqualificados` como bloco de outcomes fora da cadeia, mantendo as duas categorias distintas
    - Rodar `python -m pytest tests/test_analytics_funnel.py tests/test_executive_metrics.py -q`
    - _Requirements: 17.1, 17.3, 17.5, 17.6, 19.5_
    - _Properties: P25, P13, P6_

  - [ ] 17.2 Calcular a taxa de conversão com denominador zero indisponível
    - Em `services/api/src/services/analytics_service.py`, derivar a taxa das contagens da função pura, no domínio `[0, 1]`, devolvendo `null` com marcador de indisponibilidade quando o denominador é zero — nunca `0.0`
    - _Requirements: 17.2, 19.2, 19.3_
    - _Properties: P27_

  - [ ] 17.3 Adicionar os cortes por `offer_key` e por canal na rota do funil
    - Em `services/api/src/routes/analytics.py`, adicionar os parâmetros `offer_key` e `channel` a `GET /api/analytics/funnel`, alinhados ao que `executive-metrics` já aceita, aplicando conjunção com `from`, `to`, `campaign_id` e `consultant_id`
    - Derivar oferta de `LeadOpportunity.offer_key`/`Conversion.offer_key` e canal de `MessageChannel`/`PostSaleChannel`, com parcela explícita "sem oferta" e "sem canal" para fechar a partição
    - _Requirements: 18.1, 18.2, 18.3, 18.5_
    - _Properties: P24, P26_

  - [ ] 17.4 Expor `amostra` e `disponivel` em cada agregação
    - Em `services/api/src/services/analytics_service.py`, fazer cada categoria devolver `{ valor, amostra, disponivel }`, com `disponivel: false` quando a dimensão não tem dado persistido no período, e sinal de insuficiência abaixo do limiar explícito de amostra
    - Garantir que a soma das partes mais a parcela sem valor na dimensão é igual ao total do mesmo período e filtro
    - _Requirements: 18.4, 19.1, 19.2, 19.3_
    - _Properties: P24, P28_

  - [ ] 17.5 Escrever as propriedades do BI
    - Criar `tests/test_analytics_funnel_properties.py` com a ferramenta decidida em 1.2, sobre as funções puras de agregação
    - **Property 24: Partição fechada**; **Property 25: Monotonicidade do funil**; **Property 26: Comutatividade de filtros**; **Property 27: Taxa em domínio válido**; **Property 28: Ausência de dado não é zero**
    - _Requirements: 17.1, 17.2, 18.4, 18.5, 19.1, 19.2, 19.3_
    - _Properties: P24, P25, P26, P27, P28_

  - [ ] 17.6 Cobrir escopo por organização e igualdade entre telas
    - Criar `tests/test_analytics_org_scope.py` com duas organizações povoadas, assertando que todo registro retornado por `funnel`, `executive-metrics` e `campaigns` tem `organization_id` da organização ativa
    - Assertar que a mesma métrica devolve o mesmo número nos três endpoints sob período e filtros iguais
    - _Requirements: 17.5, 19.4, 19.5_
    - _Properties: P6_

- [ ] 18. Aba "Funil de operação" em `/relatorios`
  - [ ] 18.1 Adicionar a aba com as sete etapas, os dois outcomes e a taxa
    - Em `apps/web/src/app/(protected)/relatorios/page.tsx`, adicionar a aba "Funil de operação" consumindo `GET /api/analytics/funnel`, sem criar rota nova e sem mudar o gate de papel existente
    - Exibir os filtros de período, campanha, oferta e canal, aplicando conjunção; usar Base UI com a prop `render`
    - _Requirements: 17.1, 17.2, 17.4, 18.1, 18.2, 18.3, 18.5_
    - _Properties: P25, P26_

  - [ ] 18.2 Exportar a visão filtrada
    - Reutilizar o caminho de export já existente em `apps/web/src/app/(protected)/relatorios/page.tsx` para exportar a visão exibida, carregando os filtros aplicados no cabeçalho do arquivo
    - _Requirements: 18.6_

  - [ ] 18.3 Apresentar amostra, insuficiência e ausência de dado
    - Na mesma aba, exibir o tamanho da amostra por agregação, o sinal de insuficiência abaixo do limiar e "sem dado no período" quando `disponivel` é falso — nunca o número zero
    - Cobrir loading, erro com nova tentativa e resultado parcial por região
    - _Requirements: 18.4, 19.2, 19.3_
    - _Properties: P28_

- [ ] 19. OPCIONAL — recortes que dependem de evidência do UAT
  - [ ] 19.1 Expor a análise por variante de mensagem na aba de funil
    - Executar apenas se 15.4 registrou necessidade comprovada no UAT; caso contrário registrar `DEFER_TO_V2` em `docs/alphamec-registro.md` sem alterar código
    - Consumir o endpoint `message-variants` já existente, sem novo endpoint e sem dependência nova
    - _Requirements: 20.1, 20.2, 20.3_

  - [ ] 19.2 Implementar atribuição avançada de resultado
    - Executar apenas se 15.4 registrou necessidade comprovada no UAT; caso contrário registrar `DEFER_TO_V2` com a justificativa
    - _Requirements: 20.4, 20.5_

### Fechamento

- [ ] 20. Executar os nove gates de qualidade na ordem do design
  - [ ] 20.1 Gates 1 a 4 — testes, compilação, genericidade e migrations
    - Rodar, da raiz: `python -m pytest tests -q -W error`; depois `python -m compileall -q services/api services/workers`
    - Rodar `python -m pytest tests/test_genericity_harness.py tests/test_genericity_core_purity.py -q` confirmando ausência de regressão de genericidade
    - Rodar, com CWD `services/workers`: `alembic heads` (exatamente uma cabeça) e `alembic upgrade head` sem erros
    - Registrar a saída de cada comando em `docs/alphamec-registro.md`; falha bloqueia o fechamento
    - _Requirements: 21.2, 21.3, 21.4, 21.5, 21.9, 8.5, 22.1, 22.7_
    - _Properties: P18_

  - [ ] 20.2 Gates 5 a 7 — lint, tipos e build do `apps/web`
    - Rodar em `apps/web`: `npm run lint`, `npx tsc --noEmit`, `npm run build`, nesta ordem, e registrar as saídas
    - _Requirements: 21.6, 21.9_

  - [ ] 20.3 Gate 8 — browser QA dos fluxos do Bloco 2
    - Executar a verificação de navegador nos fluxos de criar e iniciar coleta, Meus Leads, lote de perda com motivo, convite com login intermediário e estados de provider, anexando as evidências em `docs/alphamec-registro.md`
    - _Requirements: 21.7, 21.9_
    - _Properties: P21, P19, P12, P20, P22_

  - [ ] 20.4 Gate 9 — atualizar o grafo de conhecimento se executável
    - Verificar se o `graphify` é executável no ambiente; se sim, rodar `graphify update .` e registrar; se não, registrar a indisponibilidade em `docs/alphamec-registro.md`
    - _Requirements: 21.8_

- [ ] 21. Revisões e Definition of Done
  - [ ] 21.1 Submeter à revisão de implementação
    - Executar a revisão de implementação contra requisitos e critérios de aceite dos Requisitos 1 a 22, cobrindo isolamento entre organizações, idempotência, Estado_Terminal, concorrência, contrato entre App_Web e API, UX enganosa, inferência apresentada como fato e falha de provider apresentada como ausência de resultado
    - Registrar os achados em `docs/alphamec-registro.md` e corrigir os `BLOCKS_ALPHAMEC` antes de seguir
    - _Requirements: 23.4_

  - [ ] 21.2 Submeter à revisão de código
    - Executar a revisão de código do diff completo da branch depois da revisão de implementação, com os mesmos eixos, e corrigir os `BLOCKS_ALPHAMEC` apontados
    - _Requirements: 23.4_

  - [ ] 21.3 Declarar a Definition of Done
    - Confirmar Requisitos 1 a 22 atendidos, Golden Path demonstrado em sessão única sem intervenção de desenvolvedor, gates 1 a 8 verdes e nenhum `BLOCKS_ALPHAMEC` aberto
    - Registrar em `docs/alphamec-registro.md` a declaração "ALPHAMEC — PRODUCTION READY: YES"; se qualquer condição falhar, registrar a etapa como `BLOCKS_ALPHAMEC` e manter a spec aberta
    - _Requirements: 23.1, 23.2, 23.3_

## Notes

- Tarefas marcadas com `*` são opcionais ou condicionais: testes de propriedade,
  o provider especializado MEJ/eventos (só se 15.5 reprovar os limiares) e os
  recortes de variante de mensagem e atribuição avançada (só com necessidade
  comprovada no UAT).
- No Bloco 1, o teste de cada invariante é escrito antes da correção e precisa
  falhar (red) com a evidência registrada; sem isso a correção não é considerada
  verificada.
- As três tarefas de contagem prévia (8.2, 8.4, 8.6) e a m4 param o trabalho com
  Ponto_De_Parada em caso de conflito. Nenhum backfill, nenhuma remoção de linha,
  nenhuma remoção de coluna sem aprovação humana.
- `hypothesis` não está instalada: a tarefa 1.2 exige confirmação humana antes de
  adicionar a dependência e define a alternativa determinística caso ela seja
  recusada.
- `apps/web` não tem runner de teste: as verificações de componente usam a
  alternativa declarada em 1.3 (módulo puro com `node --test`, contrato estático
  em `tests/` e browser QA), sem introduzir framework novo.
- A ordem dos blocos é 1 → 2 → 3 → 4, com o Bloco 4 podendo avançar em paralelo
  ao Bloco 3 exceto nas tarefas que dependem do resultado do UAT.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2.1", "3.1", "4.1", "5.1", "6.1", "7.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.2", "4.2", "5.2"] },
    { "id": 3, "tasks": ["2.4", "5.3", "6.2", "7.2"] },
    { "id": 4, "tasks": ["2.5", "3.3", "7.3", "10.3", "11.1", "12.1"] },
    { "id": 5, "tasks": ["2.6", "10.1", "10.2", "10.4", "10.5", "11.2", "12.2"] },
    { "id": 6, "tasks": ["2.7", "3.4", "4.3", "5.4", "6.3", "7.4", "11.3", "12.3"] },
    { "id": 7, "tasks": ["8.1"] },
    { "id": 8, "tasks": ["8.2"] },
    { "id": 9, "tasks": ["8.3"] },
    { "id": 10, "tasks": ["8.4"] },
    { "id": 11, "tasks": ["8.5"] },
    { "id": 12, "tasks": ["8.6"] },
    { "id": 13, "tasks": ["8.7"] },
    { "id": 14, "tasks": ["14.1", "14.2", "14.3", "17.1"] },
    { "id": 15, "tasks": ["15.1", "17.2"] },
    { "id": 16, "tasks": ["15.2", "15.3", "17.3"] },
    { "id": 17, "tasks": ["15.4", "17.4"] },
    { "id": 18, "tasks": ["15.5", "17.5", "17.6"] },
    { "id": 19, "tasks": ["16.1", "18.1"] },
    { "id": 20, "tasks": ["16.2", "18.2"] },
    { "id": 21, "tasks": ["18.3"] },
    { "id": 22, "tasks": ["19.1"] },
    { "id": 23, "tasks": ["19.2"] },
    { "id": 24, "tasks": ["20.1"] },
    { "id": 25, "tasks": ["20.2"] },
    { "id": 26, "tasks": ["20.3"] },
    { "id": 27, "tasks": ["20.4"] },
    { "id": 28, "tasks": ["21.1"] },
    { "id": 29, "tasks": ["21.2"] },
    { "id": 30, "tasks": ["21.3"] }
  ]
}
```
