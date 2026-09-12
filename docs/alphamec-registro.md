# Registro de execução — AlphaMec Production Ready

Registro único da spec `alphamec-production-ready`. Toda decisão de ferramenta,
evidência de teste, contagem prévia de migration, ponto de parada, finding e
saída de gate desta spec é gravada aqui. Seção marcada como **pendente** é
preenchida pela tarefa que a produz.

---

## 1. Decisões de ferramenta

### 1.1 Branch de trabalho

- Branch: `feat/alphamec-production-ready`, criada a partir de `main @ 27d2925`.
- No momento da criação a árvore **não** estava limpa. As pendências eram
  exclusivamente:
  - `AGENTS.md` (+3 linhas na tabela de skills);
  - `.kiro/agents/*`;
  - `.kiro/skills/*`;
  - a própria spec `.kiro/specs/alphamec-production-ready/*`.
- Zero mudanças em `services/` ou `apps/web/`. As pendências foram carregadas
  para a branch sem perda e seguem não commitadas.

### 1.2 Property-based testing

- **Hypothesis aprovada por decisão humana** e pinada como `hypothesis==6.168.0`
  em `requirements-dev.txt`.
- Python do ambiente: 3.14.6.
- Compatível com o `pytest==9.1.1` já pinado — o plugin exige apenas
  `pytest>=4.6`, sem teto de versão.
- Única dependência transitiva adicionada: `sortedcontainers-2.4.0`.
- A alternativa determinística com `random.Random(seed)` fica **descartada**.
- Todas as tarefas de propriedade da spec (2.7, 3.4, 4.3, 5.4, 7.4, 17.5) usam
  Hypothesis com `max_examples` ≥ 100.

### 1.3 Verificação de componente em `apps/web`

`apps/web` **não possui runner de teste**: `package.json` não declara script
`test` nem vitest/jest. Nenhum framework de teste novo será introduzido sem
confirmação humana. A verificação de componente desta spec usa três caminhos:

- **(a) Módulo puro em TypeScript coberto pelo runner nativo `node --test`** —
  aplicável quando o Node do ambiente carregar TS diretamente. É o caminho
  preferencial para lógica pura extraída de componente (por exemplo o helper de
  redirecionamento seguro e o mapeamento de estados de provider).
- **(b) Teste de contrato estático em `tests/`** — o teste em pytest lê o
  arquivo-fonte do componente como texto e asserta o contrato observável
  (endpoint chamado, hook usado, valor de parâmetro emitido, presença do diálogo
  de motivo). Cobre o que não é extraível para módulo puro.
- **(c) Browser QA com evidência anexada** — verificação de navegador dos fluxos
  reais, com a evidência registrada neste documento.

Se o Node do ambiente não carregar TypeScript diretamente, a limitação é
registrada aqui e o caminho (a) é substituído por teste tabelado no próprio
módulo, mantendo a mesma tabela de casos.

### 1.4 Graphify

- Presença de `graphify-out/graph.json` confirmada no repositório.
- Os comandos `graphify query` / `path` / `explain` **não** foram executados
  nesta spec e a disponibilidade do binário **não** foi verificada.
- O gate 9 (`graphify update .`) permanece condicionado a essa verificação.

---

## 2. Evidência red→green por invariante

Cada invariante do Bloco 1 exige o teste escrito antes da correção, com falha
(red) registrada, e a passagem (green) registrada depois da correção. Sem as duas
evidências a correção não é considerada verificada.

| Invariante | Arquivo de teste | Red | Green |
| --- | --- | --- | --- |
| Tenant determinístico no inbound de e-mail | `tests/test_inbound_tenant_isolation.py` | **9 failed, 3 passed** (ver 2.1) | pendente |
| Falha fechada em job e WebSocket | `tests/test_job_ws_fail_closed.py` | 2 failed, 3 passed (ver 2.2) | **5 passed** (ver 2.2) |
| Estados terminais fora da cadência | `tests/test_cadence_terminal_status.py` | 17 failed, 1 passed (ver 2.3) | **18 passed** (ver 2.3) |
| Motivo obrigatório em `PERDIDO` | `tests/test_lead_lost_reason_required.py` | 4 failed, 4 passed (ver 2.4) | pendente |
| Ação em lote sem bypass do motivo | `tests/test_bulk_lost_contract.py` | 7 failed, 1 passed (ver 2.5) | pendente |
| Conversão única sob concorrência | `tests/test_conversion_unique_concurrency.py` | 4 failed, 4 passed, **8 skipped** (ver 2.6) | pendente |

### 2.1 Inbound de e-mail

Arquivo: `tests/test_inbound_tenant_isolation.py` (12 testes).

**Red** — `python -m pytest tests/test_inbound_tenant_isolation.py -q` na raiz:
**9 failed, 3 passed em 1,09s**, exit 1, zero warnings. Executado antes de
qualquer alteração em `webhooks.py`, `inbound_email_service.py` ou `models.py`.
`git diff --stat HEAD -- services/ apps/` vazio no momento da medição, então o
red é do código de produção intocado.

Estratégia sem Postgres: o teste usa uma sessão em memória que **avalia os
critérios SQLAlchemy reais** montados pelo serviço (`or_`, `eq`, `is_not`, `le`,
`order_by`) contra linhas de teste, incluindo o pareamento do `outerjoin`
`Lead × Contact`. É o filtro do próprio serviço que decide o resultado, então a
evidência é do comportamento e não de um mock de conveniência. Nenhum skip: a
evidência red foi obtida agora, sem `E2E_DATABASE_URL`.

As duas organizações têm um lead com o mesmo remetente
(`decisor@empresa-homonima.com.br`) e o lead da organização B é o **primeiro** da
lista — pior caso de `.first()` em consulta sem escopo de tenant, cuja ordem de
retorno depende do planner.

Chamada: o helper `_processar` invoca `process_inbound_email` com
`organization_id=` (assinatura exigida pelos requisitos) e, ao receber
`TypeError` de parâmetro inesperado, cai na assinatura legada. Isso faz a falha
observada ser a **asserção de isolamento** — o vazamento real — e não apenas o
erro de assinatura.

| Teste | Modo de falha observado | Requisito |
| --- | --- | --- |
| `test_inbound_da_org_a_afeta_somente_o_lead_da_org_a` | `AssertionError`: lead de A permaneceu `CONTATADO` — o serviço marcou `RESPONDIDO` no lead de **B** | 1.3, 1.4 |
| `test_process_inbound_email_exige_organization_id` | `AssertionError`: `organization_id` ausente na assinatura | 1.1 |
| `test_zero_message_criada_no_lead_da_outra_organizacao` | `AssertionError`: a `Message` espelho foi criada com o `lead_id` de **B** | 2.1, 2.4 |
| `test_trilha_e_notificacao_ficam_no_lead_da_organizacao_resolvida` | `AssertionError`: `LeadActivity` gravada no lead de B | 2.2 |
| `test_followup_pendente_da_outra_organizacao_permanece_intocado` | `AssertionError`: `FollowUp` de A ficou `PENDING`; o cancelado foi o de B | 2.2 |
| `test_stop_da_org_a_nao_marca_opt_out_no_lead_da_org_b` | `AssertionError`: `opt_out` aplicado ao lead de B | 2.3 |
| `test_sem_lead_na_organizacao_resolvida_retorna_matched_false_sem_persistir` | `AssertionError`: retornou `matched=True` usando lead de outra organização | 1.5 |
| `test_rota_por_token_com_token_invalido_responde_401_sem_persistir` | `404 != 401` — a rota `POST /api/webhooks/email/inbound/{token}` ainda não existe | 1.1, 1.2 |
| `test_rota_legada_sem_identificacao_de_organizacao_responde_401` | `200 != 401` — o segredo global sozinho autoriza o processamento | 1.2 |

Os 3 testes que **já passam** cobrem guardas hoje corretas e entram como
regressão: `test_remetente_vazio_nao_persiste_nada` (retorno antes de qualquer
`db.add`), `test_rota_legada_com_segredo_invalido_responde_401_sem_persistir`
(`X-Webhook-Secret` divergente → 401 sem persistência) e
`test_rota_legada_sem_credencial_alguma_responde_401_sem_persistir` (header
ausente recusado igual a header inválido). Os dois últimos fecham o par
"credencial ausente/inválida" exigido pelo Requisito 1.2.

O green é registrado pela tarefa 2.5, após 2.2 a 2.5.

### 2.2 Job e WebSocket

**Red registrado.** Arquivo: `tests/test_job_ws_fail_closed.py` (5 testes).

Comando executado da raiz:

```
python -m pytest tests/test_job_ws_fail_closed.py -q
```

Saída: `2 failed, 3 passed in 1.07s`, exit 1.

O teste exercita a corrotina real `websocket_pipeline` com stub assíncrono de
WebSocket (`accept`, `receive_text`, `send_json`, `close` registrados) e sessão
de banco falsa — sem Postgres e sem rede. O handshake reproduzido é o real:
primeira mensagem `{"type": "auth", "token": "..."}` sem `organization_id`, logo
a organização ativa vem de `user_organization`.

Falhas observadas, ambas no cenário do job órfão:

| Teste | Falha |
| --- | --- |
| `test_job_orfao_e_recusado_com_403` | `assert None == (403, 'Acesso negado a este job')` — nenhum `close` é chamado |
| `test_nenhum_cenario_recusado_emite_mensagem_de_progresso` | `assert True is False` em `registrado_no_broadcast` — o job órfão entra em `active_connections` |

Os três testes que passam confirmam que job de outra organização e job
inexistente já falham fechados hoje, com recusa idêntica `(403, "Acesso negado a
este job")` — a indistinguibilidade da recusa (Property 5) já vale para esse par.

Causa raiz confirmada em `services/api/src/routes/pipeline.py` (~linha 226): a
guarda é `job is None or (job.organization_id and str(job.organization_id) !=
str(org.id))`. Com `Job.organization_id` nulo (`nullable=True` em
`services/workers/src/database/models.py`) a conjunção é falsa, a conexão é
aceita e registrada no canal de broadcast de progresso. Nenhum arquivo de
produção foi alterado nesta etapa.

A segunda falha é a evidência do critério de zero progresso: `active_connections`
é o canal por onde o job-consumer transmite o progresso, então o registro do
socket órfão significa progresso entregue a quem não deveria recebê-lo.

**Green registrado (tarefa 3.2).** Correção em
`services/api/src/routes/pipeline.py`: a guarda passou a ser
`job is None or job.organization_id is None or str(job.organization_id) != str(org.id)`,
com o mesmo `close(code=403, reason="Acesso negado a este job")` nos três casos.
Nenhum outro arquivo de produção foi alterado.

Comando executado da raiz:

```
python -m pytest tests/test_job_ws_fail_closed.py -q
```

Saída: `5 passed in 0.86s`, exit 0.

Suíte completa, para confirmar ausência de regressão:

```
python -m pytest tests -q
```

Saída: `41 failed, 1235 passed, 27 skipped, 8 warnings in 22.77s`, exit 1 —
baseline anterior era `43 failed, 1233 passed, 27 skipped`. As 41 falhas restantes
são os reds intencionais das tarefas 2.1, 4.1, 5.1, 6.1 e 7.1; nenhuma falha nova.

Requisitos 3.1, 3.2 e 3.3 cobertos: job órfão e job de outra organização são
recusados com 403, a recusa é idêntica à de job inexistente (Property 5) e nenhum
socket recusado entra em `active_connections`, logo zero mensagens de progresso
(Property 4).

### 2.3 Cadência e estado terminal

**Red registrado.** Arquivo: `tests/test_cadence_terminal_status.py` (18 testes).

Comando executado da raiz:

```
python -m pytest tests/test_cadence_terminal_status.py -q
```

Saída: `17 failed, 1 passed in 1.12s`, exit 1. Nenhum arquivo de produção foi
alterado nesta etapa — `services/api/src/services/cadence_service.py` segue
intocado.

Harness: o teste reaproveita a consulta em memória extraída para
`tests/sqlalchemy_memory.py` (era local em `tests/test_inbound_tenant_isolation.py`
e passou a ser compartilhada, com suporte adicional a `in_`/`not_in` e aos
literais de `is_(True)`/`is_(False)`). Os critérios SQLAlchemy montados pelo
próprio `run_due` são avaliados contra as linhas de teste, então é o filtro de
produção que decide a seleção. SMTP é stubado por `monkeypatch` em
`src.services.email_service.send_email`, que **conta as chamadas** — zero rede,
zero Postgres, zero provider. `tests/test_inbound_tenant_isolation.py` continua
com a mesma medição de red (`9 failed, 3 passed`) depois da extração.

População do `run_due`: cinco follow-ups vencidos na mesma organização, dois de
leads terminais (`PERDIDO`, `DESQUALIFICADO`) e três de leads elegíveis
(`CONTATADO`, `QUALIFICADO`, `RESPONDIDO`), com endereço distinto por lead para
verificar o destino real de cada envio. Os terminais vêm primeiro na lista. A
organização tem janela aberta e teto alto, e o teste asserta `postergadas == 0`,
para que a disjunção não possa ser efeito de throttling.

| Teste | Modo de falha observado | Requisito |
| --- | --- | --- |
| `test_send_step_em_lead_terminal_nao_envia_email` (4 casos: `PERDIDO`/`DESQUALIFICADO` × scheduler/consultor) | `AssertionError`: `envios` contém a chamada de SMTP — a etapa foi enviada ao lead terminal | 4.1 |
| `test_send_step_em_lead_terminal_nao_cria_message` (2 casos) | `AssertionError`: `Message` de outreach criada no lead terminal | 4.4 |
| `test_send_step_em_lead_terminal_marca_skipped_com_motivo` (2 casos) | `AssertionError`: etapa terminou `SENT` em vez de `SKIPPED`; nenhum evento `cadence_skipped` com motivo de estado terminal | 4.1 |
| `test_send_step_em_lead_terminal_preserva_o_status_do_lead[DESQUALIFICADO]` | `AssertionError`: `DESQUALIFICADO` → `CONTATADO` — o envio reabriu o funil do lead | 4.1 |
| `test_run_due_seleciona_conjunto_disjunto_dos_leads_terminais` | `AssertionError`: a seleção de vencidos incluiu os dois follow-ups de leads terminais | 4.2 |
| `test_run_due_nao_chama_o_envio_para_etapa_de_lead_terminal` | `AssertionError`: `send_step` foi chamado para as etapas dos leads terminais | 4.2 |
| `test_run_due_nao_manda_email_para_lead_terminal` | `AssertionError`: `perdido@empresa.com.br` e `desqualificado@empresa.com.br` receberam e-mail no caminho completo | 4.1, 4.2, 4.4 |
| `test_run_due_nao_altera_etapa_de_lead_terminal` | `AssertionError`: as etapas dos leads terminais saíram de `PENDING` para `SENT` | 4.2 |
| `test_transicao_terminal_zera_followup_pendente` (2 casos) | `AssertionError`: `cadence_service` não expõe `cancel_pending_for_terminal` | 4.3 |
| `test_cancelamento_terminal_nao_commita_por_conta_propria` | `AssertionError`: mesma ausência da função | 4.3 |
| `test_cancelamento_terminal_sem_pendencia_e_inocuo` | `AssertionError`: mesma ausência da função | 4.3 |

O único teste que **já passa** é
`test_send_step_em_lead_terminal_preserva_o_status_do_lead[PERDIDO]`: `PERDIDO`
não está na lista de status que o envio promove para `CONTATADO`, então o estado
sobrevive por acidente do código atual. Entra como regressão.

Causa raiz confirmada em `services/api/src/services/cadence_service.py`:
`send_step` checa `SENT`, `opt_out`, conteúdo, destinatário e supressão, sem
nenhuma checagem de `Lead.status`; o filtro de `run_due` (linha ~455) tem
`PENDING & scheduled_at <= now & opt_out is False & auto_send_email is True`, sem
exclusão de estado terminal; e não existe função de cancelamento de pendências na
transição terminal (`mark_opt_out` faz isso só para opt-out).

Alcançabilidade do green verificada antes de fechar o red: a correção prevista no
design (guarda em `send_step`, `& (~Lead.status.in_(TERMINAL_STATUSES))` em
`run_due` e `cancel_pending_for_terminal`) foi aplicada **em memória** por um
arquivo descartável de simulação, que levou o mesmo conjunto a `18 passed`. O
arquivo foi removido em seguida; nenhuma correção ficou no repositório. Isso
descarta red falso (teste que não passa nem com a correção).

**Green registrado (tarefa 4.2).** Correção em
`services/api/src/services/cadence_service.py`, arquivo único alterado, nos três
pontos previstos pelo design:

1. `TERMINAL_STATUSES = (LeadStatus.PERDIDO, LeadStatus.DESQUALIFICADO)` definida
   ao lado de `MAX_ATTEMPTS`.
2. Guarda em `send_step` imediatamente após o early-return de `SENT` e antes de
   resolver destinatário, criar `Message` ou tocar o SMTP: o lead é resolvido uma
   vez (`follow_up.lead` ou consulta por `lead_id`), a etapa vira `SKIPPED` e sai
   `log_event("cadence_skipped", reason="terminal_status", status=..., step=...,
   lead_id=..., organization_id=...)` mais um `logger.info`. A resolução do lead
   que existia depois da checagem de conteúdo foi removida, já que a guarda passou
   a fazê-la antes — sem consulta duplicada e sem mudança de comportamento.
3. Filtro de `run_due` ganhou `& (~Lead.status.in_(TERMINAL_STATUSES))`, com
   operadores SQLAlchemy (`&`, `~`), nunca `and`/`not` do Python.
4. `cancel_pending_for_terminal(db, lead, reason)` criada ao lado de
   `mark_opt_out`: cancela todo `FollowUp` `PENDING` do lead (`CANCELLED`),
   preserva etapa já `SENT`, registra o encerramento em log e retorna a
   contagem. **Sem commit próprio** — a transação é do chamador. Os consumidores
   (rotas de transição de status) são ligados pela tarefa 5.3; nenhuma rota foi
   alterada aqui.

`SKIPPED` em `send_step` e `CANCELLED` em `cancel_pending_for_terminal`, seguindo
o design: no primeiro caso o bloqueio é de elegibilidade da etapa, no segundo o
relacionamento terminou.

Comando executado da raiz:

```
python -m pytest tests/test_cadence_terminal_status.py tests/test_cadence_run_due.py tests/test_cadence_close.py -q
```

Saída: `32 passed in 0.80s`, exit 0 — os 18 testes do red mais os 14 de regressão
de `run_due` e do encerramento de cadência. Medido isolado, o arquivo do red vai
de `17 failed, 1 passed` para `18 passed in 0.71s`.

Suíte completa, para confirmar ausência de regressão:

```
python -m pytest tests -q
```

Saída: `24 failed, 1266 passed, 27 skipped, 8 warnings in 22.68s`, exit 1 —
baseline anterior era `41 failed, 1235 passed, 27 skipped`. As 24 falhas restantes
são exclusivamente os reds intencionais ainda abertos, por arquivo:
`test_inbound_tenant_isolation.py` (9), `test_bulk_lost_contract.py` (7),
`test_conversion_unique_concurrency.py` (4) e
`test_lead_lost_reason_required.py` (4). Nenhuma falha de cadência e nenhuma
falha nova.

Requisitos 4.1 a 4.4 cobertos: etapa de lead terminal é encerrada sem envio e com
motivo registrado (4.1), a seleção de vencidos é disjunta dos follow-ups de leads
terminais (4.2), a transição terminal tem ponto único que zera as pendências (4.3)
e zero `Message` é criada no bloqueio (4.4). As propriedades P7, P8 e P9 ficam com
a verificação exaustiva na tarefa 4.3.

### 2.4 Motivo obrigatório em `PERDIDO`

**Red registrado.** Arquivo: `tests/test_lead_lost_reason_required.py` (8 testes).

Comando executado da raiz:

```
python -m pytest tests/test_lead_lost_reason_required.py -q
```

Saída: `4 failed, 4 passed in 1.55s`, exit 1, zero warnings de Python.
`git diff --stat HEAD -- services/ apps/` vazio no momento da medição, então o
red é do código de produção intocado.

Estratégia sem Postgres: as rotas reais de `services/api/src/routes/leads.py` são
exercitadas por `TestClient` (schema, dependências e ordem entre validar e
consultar o banco sob teste), com uma sessão em memória construída sobre a
consulta compartilhada `tests/sqlalchemy_memory.py` — **os critérios SQLAlchemy
montados pela própria rota são avaliados linha a linha** — que registra consultas,
objetos adicionados e commits. O limitador global é desligado
por `monkeypatch` dentro do teste, para a evidência não depender de quota
consumida por outros arquivos da suíte. Nenhum skip.

O log capturado traz `Falha ao persistir outcome do lead ...: '_Sessao' object has
no attribute 'scalars'`: a sessão do harness não implementa o acesso usado pelo
serviço de outcome comercial, que a rota já trata com `try/except` e log. Isso não
afeta as asserções deste arquivo — a idempotência de outcome é coberta por P17 nas
tarefas 5.3 e 5.4.

| Teste | Modo de falha observado | Requisito |
| --- | --- | --- |
| `test_patch_status_perdido_sem_motivo_responde_422` | `assert 200 == 422` — `PATCH /status` com `status=PERDIDO` e sem `lost_reason` é aceito e grava `PERDIDO` | 5.1 |
| `test_patch_status_perdido_sem_motivo_rejeita_antes_de_consultar_o_banco` | `AssertionError`: 2 consultas executadas (`Lead` e `Organization`) onde o esperado é zero | 5.1 |
| `test_patch_status_perdido_com_motivo_grava_trilha_lost_com_o_motivo` | `AssertionError`: a trilha `LOST` sai com `detail = "PERDIDO"`, sem o motivo, e sem `status_from` | 5.2, 5.3 |
| `test_patch_status_desqualificado_nao_grava_lost_reason` | `AssertionError`: `lost_reason` enviado junto de `DESQUALIFICADO` é persistido, colapsando os dois outcomes | 5.4 |

Causa raiz confirmada em `services/api/src/routes/leads.py`:
`UpdateLeadStatusRequest.lost_reason` é `Optional[LostReason] = None`, sem
validador de consistência, então `PERDIDO` sem motivo passa pelo schema; a rota
grava `lead.lost_reason` para **qualquer** status quando o campo vem preenchido; e
a trilha semântica de `PERDIDO` usa `detail=body.status.value` (`"PERDIDO"`), sem
o motivo e sem `status_from`.

Os 4 testes que **já passam** entram como regressão da garantia atual:
`test_mark_lost_sem_motivo_responde_422_sem_alterar_o_lead` e
`test_mark_lost_com_motivo_grava_trilha_lost_com_o_motivo` (o `MarkLostRequest`
já exige o motivo e a trilha `LOST` da rota dedicada já registra o valor),
`test_patch_status_desqualificado_grava_trilha_distinta_da_perda` e
`test_mark_disqualified_nao_grava_trilha_de_perda` (desqualificação grava
`STATUS_CHANGED` e nunca `LOST`) — o par exigido pelo Requisito 5.4.

Nenhum arquivo de produção foi alterado nesta etapa. O green é registrado pela
tarefa 5.3, após 5.2 e 5.3.

### 2.5 Ação em lote

**Red registrado.** Arquivo: `tests/test_bulk_lost_contract.py` (8 testes).

Comando executado da raiz:

```
python -m pytest tests/test_bulk_lost_contract.py -q
```

Saída: `7 failed, 1 passed in 0.36s`, exit 1, zero warnings.
`git diff --stat HEAD -- services/ apps/` vazio no momento da medição, então o
red é do código de produção intocado.

Estratégia de verificação: caminho (b) da decisão 1.3 — teste de contrato
estático. O teste lê `apps/web/src/components/oportunidades/lead-list.tsx` como
texto e asserta o contrato observável do componente. Nenhum framework de teste
novo foi introduzido em `apps/web`.

Para não quebrar por formatação, o teste extrai o **corpo da função** por
contagem de chaves (a menor função nomeada cujo corpo contém a chamada
procurada) e usa expressões com `\s*` entre identificador, ponto e chamada.
Assim `updateStatus.mutate` e `updateStatus\n  .mutate` são equivalentes, e a
ordem entre a guarda e o disparo é medida dentro do escopo da função, não do
arquivo — checagem de ordem no arquivo inteiro passaria por acidente, já que
`PERDIDO` aparece em `statusLabels` e em `bulkStatusOptions` antes do disparo.
O texto de UI é comparado por radical (`sucess|marcad|movid|atualizad|perdid` e
`falh|erro`), então a redação pode mudar sem quebrar o teste.

| Teste | Modo de falha observado | Requisito |
| --- | --- | --- |
| `test_componente_importa_o_hook_de_marcacao_com_motivo` | `AssertionError`: o componente não importa `useMarkLost` de `@/hooks/use-api` — só tem `useUpdateLeadStatus` | 6.2 |
| `test_lote_de_perdido_dispara_a_marcacao_com_motivo_por_lead` | `AssertionError`: nenhuma função do componente chama `markLost.mutate*` | 6.2 |
| `test_lote_de_perdido_nao_usa_o_patch_generico_de_status` | `AssertionError`: `bulkStatus` manda qualquer status pelo PATCH genérico, sem guarda de `PERDIDO` | 6.1, 6.2 |
| `test_componente_declara_o_dialogo_de_motivo_do_lote` | `AssertionError`: não existe estado de diálogo de motivo (`useState` com nome de motivo/perda) | 6.1 |
| `test_dialogo_de_motivo_reaproveita_o_enum_de_lost_reason` | `AssertionError`: `LOST_REASON_OPTIONS` não é importado — sem enum compartilhado, o lote pode divergir do aceito pela API | 6.1 |
| `test_lote_de_perdido_abre_o_dialogo_antes_de_qualquer_requisicao` | `AssertionError`: `bulkStatus` não desvia `PERDIDO` para o diálogo antes do disparo | 6.1 |
| `test_resumo_do_lote_informa_sucessos_e_falhas` | `AssertionError`: nenhuma função dispara a marcação com motivo, logo não há resumo com as duas contagens | 6.4 |

O único teste que **já passa** é
`test_opcao_de_marcar_como_perdido_continua_disponivel_no_lote`: a opção
"Marcar como perdido" segue no menu de lote com rótulo em português. Entra como
regressão — a correção precisa manter a ação disponível, não removê-la.

Causa raiz confirmada em `apps/web/src/components/oportunidades/lead-list.tsx`:
`bulkStatus(status)` encaminha **qualquer** valor do seletor de lote para
`updateStatus.mutate({ id, status })`, o PATCH genérico que hoje aceita
`PERDIDO` com `lost_reason` nulo. Não há diálogo de motivo, não há contagem de
falhas — o `toast.success` sai antes de qualquer resposta da API, contado por
`selectedLeads.length` — e o `onError` mostra só uma mensagem genérica por lead.

Alcançabilidade do green verificada antes de fechar o red: a correção prevista
(guarda de `PERDIDO` com `return`, diálogo de motivo sobre `LOST_REASON_OPTIONS`
e confirmação disparando `markLost` por lead com resumo de sucessos e falhas) foi
aplicada **em memória** por um script descartável sobre uma cópia temporária do
componente, levando o mesmo conjunto a `8 passed`. O script foi removido e
`lead-list.tsx` não foi tocado. Isso descarta red falso.

O green é registrado pela tarefa 6.2.

### 2.6 Conversão única

**Red registrado na camada determinística; camada de concorrência real não
executada por ausência de Postgres.** Arquivo:
`tests/test_conversion_unique_concurrency.py` (16 testes).

Comando executado da raiz:

```
python -m pytest tests/test_conversion_unique_concurrency.py -q
```

Saída: `4 failed, 4 passed, 8 skipped in 1.20s`, exit 1, zero warnings.
`git diff --stat HEAD -- services/ apps/` vazio no momento da medição, então o
red é do código de produção intocado — `services/api/src/routes/leads.py` e
`services/workers/src/database/models.py` seguem como estão.

O arquivo tem duas camadas, por decisão explícita: a garantia sob teste é
metade declaração de schema e metade comportamento sob corrida, e só a segunda
exige banco.

#### Camada determinística (8 testes, executados)

Cobre o que dá para provar sem Postgres: a garantia declarada em
`Conversion.__table_args__` e o escopo do filtro de `find_duplicate_conversion`.
O filtro roda contra a consulta em memória compartilhada
`tests/sqlalchemy_memory.py` — os critérios SQLAlchemy montados pela própria
produção são avaliados linha a linha, então quem decide o resultado é o código
de produção, não um mock de conveniência.

| Teste | Modo de falha observado | Requisito |
| --- | --- | --- |
| `test_modelo_declara_indice_unico_por_lead_e_oferta` | `AssertionError`: índices declarados em `Conversion.__table_args__` são apenas `['ix_conversions_lead_id']` — nenhuma constraint única de `lead_id` + oferta | 7.3 |
| `test_indice_unico_cobre_lead_e_oferta_com_sentinel` | `AssertionError`: índice `uq_conversions_lead_offer` inexistente, logo não há `coalesce` sobre `offer_key` nem o sentinel `'unknown'` | 7.3 |
| `test_duplicata_ignora_a_oportunidade_de_origem` | `AssertionError`: conversão da mesma oferta em **outra** oportunidade não é vista como duplicata — o filtro condicional por `lead_opportunity_id` é mais estreito que a unicidade de lead+oferta | 7.1, 7.2 |
| `test_oferta_nula_conta_como_sem_oferta` | `AssertionError`: conversão legada com `offer_key` nulo não é reconhecida como duplicata de `'unknown'` — app e banco discordariam sobre "sem oferta" | 7.1, 7.2, 7.3 |

Os 4 testes que **já passam** entram como regressão: `ix_conversions_lead_id`
preservado (a mudança tem de ser aditiva), sentinel repetido reconhecido,
oferta diferente no mesmo lead não é duplicata e mesma oferta em outro lead não
é duplicata — os dois últimos garantem que o alinhamento do filtro não alargue
a unicidade além de `lead_id` + oferta.

Causa raiz confirmada: `Conversion.__table_args__` tem só
`Index("ix_conversions_lead_id", "lead_id")`, sem unicidade; e
`find_duplicate_conversion` filtra `Conversion.offer_key == offer_key` com um
`if lead_opportunity_id:` adicional. `offer_key` é `String(64) nullable`, então
nem um índice único simples resolveria: NULLs são distintos entre si.

Extensão do harness: `tests/sqlalchemy_memory.py` passou a avaliar
`func.coalesce` e `text(...)` (literal SQL e referência crua de coluna), o que o
filtro alinhado à constraint exige. É capacidade nova do harness, sem mudança de
comportamento para os critérios já suportados —
`tests/test_inbound_tenant_isolation.py`, `tests/test_cadence_terminal_status.py`
e `tests/test_lead_lost_reason_required.py` mantêm exatamente as mesmas medições
de red (`9 failed / 3 passed`, `17 failed / 1 passed`, `4 failed / 4 passed`)
depois da extensão.

Alcançabilidade do green verificada antes de fechar o red: a correção prevista no
design (índice `uq_conversions_lead_offer` sobre
`(lead_id, coalesce(offer_key, 'unknown'))` e filtro por `coalesce`, sem
`lead_opportunity_id`) foi aplicada **em memória** por um arquivo descartável de
simulação, que levou os 8 testes determinísticos a passar. O arquivo foi removido
em seguida; nenhuma correção ficou no repositório. Isso descarta red falso.

#### Camada de concorrência real (8 testes, **skipados**)

Não executada: **Postgres indisponível neste ambiente**. `E2E_DATABASE_URL` não
está definida e a `DATABASE_URL` dummy injetada por `tests/conftest.py` não é
alcançável, então o skip vem do helper compartilhado `tests/db_reachable.py`
(`is_database_reachable`), no mesmo padrão de `tests/e2e_outreach_cycle.py`.
Saída de `-rs`:

```
SKIPPED [2] test_conversion_unique_concurrency.py:416: Postgres indisponivel - concorrencia real requer banco real
SKIPPED [2] test_conversion_unique_concurrency.py:435: Postgres indisponivel - concorrencia real requer banco real
SKIPPED [1] test_conversion_unique_concurrency.py:455: Postgres indisponivel - concorrencia real requer banco real
SKIPPED [2] test_conversion_unique_concurrency.py:467: Postgres indisponivel - concorrencia real requer banco real
SKIPPED [1] test_conversion_unique_concurrency.py:502: Postgres indisponivel - concorrencia real requer banco real
```

**A evidência red do caminho concorrente depende de banco real e não foi
obtida.** Nada dessa camada é declarado aprovado nem reprovado: os testes
existem, estão pulados e ficam pendentes de execução com
`E2E_DATABASE_URL` apontando para o Postgres real. Isso é registrado como
limitação de ambiente, não como resultado.

Cobertura prevista quando o banco existir, por teste:

| Teste | Verifica | Requisito / Property |
| --- | --- | --- |
| `test_conversoes_concorrentes_geram_um_unico_registro[n=2,5]` | contagem final de `Conversion` para o par igual a 1 | 7.1, 7.5 / P14 |
| `test_concorrencia_tem_exatamente_um_sucesso_e_o_resto_409[n=2,5]` | distribuição de status: 1 sucesso e `n-1` respostas `409`, sem `500` | 7.2 / P15 |
| `test_conflito_nao_expoe_detalhe_do_banco` | corpo das respostas de erro sem nome de índice, de tabela, `constraint`, `duplicate key`, `IntegrityError`, `psycopg`, `sqlalchemy` ou traceback | 7.4 / P16 |
| `test_conversao_com_oferta_nula_nao_duplica[n=1,3]` | conversão legada com `offer_key` nulo já ocupa a chave "sem oferta": toda requisição `unknown` responde `409` e a contagem fica em 1 | 7.1, 7.2, 7.3 / P14, P15 |
| `test_banco_rejeita_segunda_conversao_do_mesmo_par` | a garantia é do banco: segunda inserção do mesmo par levanta `IntegrityError` | 7.3 / P14 |

Duas decisões de método nessa camada, para o teste medir a rota e não o
escalonador:

- **Uma sessão de banco por requisição** (override de `get_db` criando
  `SessionLocal` a cada chamada) e **um `TestClient` por thread** — sem isso
  seriam n chamadas na mesma unidade de trabalho, não transações paralelas.
- **Barreira determinística**: `find_duplicate_conversion` é envolvida por um
  wrapper que chama a função real e só então espera na `threading.Barrier(n)`.
  O check roda de verdade e devolve o resultado real; a barreira apenas garante
  que as n transações atravessem o check antes de qualquer inserção. Sem ela a
  corrida dependeria do escalonador e o teste seria intermitente.

O caso `offer_key` nulo entra pelo dado legado porque a rota não aceita oferta
nula (`offer_key: str = Field(..., min_length=1)`): o cenário insere uma
`Conversion` com `offer_key` nulo e dispara requisições `unknown`.

O green é registrado pela tarefa 7.3, após 7.2 e 7.3. A camada de concorrência
só pode ser declarada verde em execução com Postgres real.

---

## 3. Contagens prévias de migration

Nenhuma migration com efeito restritivo é aplicada antes da contagem prévia
correspondente. Resultado em conflito abre Ponto_De_Parada e interrompe o
trabalho: sem backfill, sem remoção de linha, sem remoção de constraint ou
coluna.

| Contagem | Consulta | Resultado | Liberação |
| --- | --- | --- | --- |
| `lost_reason` ausente em `PERDIDO` | `SELECT count(*) FROM leads WHERE status = 'PERDIDO' AND lost_reason IS NULL;` | pendente | `VALIDATE CONSTRAINT` da m2 |
| Duplicatas em `conversions` | `SELECT lead_id, coalesce(offer_key,'unknown') AS ofr, count(*) FROM conversions GROUP BY 1,2 HAVING count(*) > 1;` | pendente | índice único da m3 |
| `jobs.organization_id` nulo | `SELECT count(*) FROM jobs WHERE organization_id IS NULL;` | pendente | `SET NOT NULL` da m4 |

Cadeia de revisões criada (m1 a m4) e saída de `alembic heads` / `alembic upgrade
head`: pendente.

---

## 4. Pontos_De_Parada

Nenhum ponto de parada aberto.

| Origem | Descrição | Dado observado | Situação |
| --- | --- | --- | --- |
| — | — | — | — |

---

## 5. Findings classificados

Cada finding recebe **exatamente uma** classificação: `BLOCKS_ALPHAMEC`,
`IMPORTANT_ALPHAMEC` ou `DEFER_TO_V2`. `BLOCKS_ALPHAMEC` é corrigido nesta
branch; `IMPORTANT_ALPHAMEC` só entra com impacto alto e custo baixo ou médio;
`DEFER_TO_V2` fica registrado sem alteração de código.

| ID | Finding | Classificação | Impacto | Custo | Situação |
| --- | --- | --- | --- | --- | --- |
| — | — | — | — | — | — |

Intervenção de desenvolvedor em etapa do Golden Path durante o UAT: pendente.

---

## 6. Decisão do provider de eventos

Limiares definidos antes do UAT:

- ≥ 60% de oportunidades comercialmente úteis;
- ≥ 80% de fichas com evidência localizável.

| Métrica | Limiar | Observado |
| --- | --- | --- |
| Oportunidades comercialmente úteis | ≥ 60% | pendente |
| Fichas com evidência localizável | ≥ 80% | pendente |

Decisão: pendente. Ambos os limiares atingidos → provider especializado
MEJ/eventos classificado como `DEFER_TO_V2` com os números que sustentam a
decisão. Qualquer um abaixo → `BLOCKS_ALPHAMEC`, liberando a implementação do
provider. A decisão é registrada aqui **antes** de qualquer implementação
decorrente.

---

## 7. Gates executados

### 7.1 Baseline medido antes das correções (HEAD `27d2925`)

- `python -m pytest tests -q` (da raiz): **1217 passed, 19 skipped, 8 warnings**,
  exit 0, ~23,9s. **Sem falhas preexistentes.**
- Os **19 skips** são os testes que exigem Postgres real (E2E), pulados
  automaticamente por ausência de `E2E_DATABASE_URL`.
- Os **8 warnings** são `InsecureKeyLengthWarning` do PyJWT em
  `test_jwt_claims.py` e `test_login_lockout.py`, causados pela chave dummy de
  11 bytes injetada por `tests/conftest.py`. São preexistentes e não têm relação
  com as mudanças desta spec.
- Este baseline **substitui** o número `1097 passed, 19 skipped` citado na
  documentação do projeto, que estava desatualizado.

### 7.2 Gates de fechamento

| # | Gate | Comando | Resultado |
| --- | --- | --- | --- |
| 1 | Testes | `python -m pytest tests -q -W error` (raiz) | pendente |
| 2 | Compilação | `python -m compileall -q services/api services/workers` | pendente |
| 3 | Genericidade | `python -m pytest tests/test_genericity_harness.py tests/test_genericity_core_purity.py -q` | pendente |
| 4 | Migrations | `alembic heads` (uma cabeça) + `alembic upgrade head` (CWD `services/workers`) | pendente |
| 5 | Lint web | `npm run lint` (`apps/web`) | pendente |
| 6 | Tipos web | `npx tsc --noEmit` (`apps/web`) | pendente |
| 7 | Build web | `npm run build` (`apps/web`) | pendente |
| 8 | Browser QA | fluxos do Bloco 2 com evidência anexada | pendente |
| 9 | Grafo de conhecimento | `graphify update .` se executável | pendente (ver 1.4) |

Falha em qualquer gate de 1 a 8 bloqueia o fechamento.

### 7.3 Definition of Done

Pendente. A declaração final só é gravada com os Requisitos 1 a 22 atendidos,
Golden Path demonstrado em sessão única sem intervenção de desenvolvedor, gates
1 a 8 verdes e nenhum `BLOCKS_ALPHAMEC` aberto.
