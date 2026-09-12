# Requirements Document

## Introduction

Esta spec transforma a AlphaMec V1 em produto usável em operação real pela equipe
de vendas. O escopo é fechado em quatro blocos: (1) segurança e invariantes de
dados, (2) Golden Path da AlphaMec de ponta a ponta, (3) UAT real executado em
ambiente com Postgres, API, web e providers reais, e (4) BI mínimo de operação.

Nada de novas ondas de features, nada de recursos estilo Apollo, nada de feature
futura sem evidência de necessidade colhida no UAT. Todo achado novo é
classificado (`BLOCKS_ALPHAMEC`, `IMPORTANT_ALPHAMEC`, `DEFER_TO_V2`) e não
gera nova iniciativa.

Os pontos de falha abaixo foram confirmados por leitura do código em
`main @ 27d2925`:

- `services/api/src/routes/webhooks.py` valida apenas `settings.EMAIL_WEBHOOK_SECRET`
  (segredo global) e não recebe nem resolve organização.
- `services/api/src/services/inbound_email_service.py` procura o lead com
  `db.query(Lead).outerjoin(Contact)...filter(Lead.organization_id.isnot(None)).first()`,
  isto é, em qualquer organização, e usa o primeiro resultado.
- `services/api/src/routes/pipeline.py` autoriza o WebSocket quando
  `job is None or (job.organization_id and str(job.organization_id) != str(org.id))`
  é falso, ou seja, `Job.organization_id` nulo passa. `Job.organization_id` é
  `nullable=True` em `services/workers/src/database/models.py`.
- `services/api/src/services/cadence_service.py` (`send_step`, `run_due`) filtra
  `opt_out`, supressão e limites, mas não filtra `LeadStatus.PERDIDO` nem
  `LeadStatus.DESQUALIFICADO`.
- `services/api/src/routes/leads.py` `PATCH /{lead_id}/status` aceita
  `status=PERDIDO` com `lost_reason` opcional, enquanto
  `POST /{lead_id}/mark-lost` exige `lost_reason`.
- `apps/web/src/components/oportunidades/lead-list.tsx` usa `updateStatus` (o
  PATCH genérico) na ação em lote `PERDIDO`.
- `services/api/src/routes/leads.py` usa `find_duplicate_conversion` (check) e
  depois `db.add(Conversion(...))` (insert); o model `Conversion` só tem
  `Index("ix_conversions_lead_id", "lead_id")`, sem constraint única.
- `apps/web/src/app/(protected)/campanhas/nova/page.tsx` navega para
  `/campanhas/${campaign.id}` sem `?start=true`, e
  `apps/web/src/app/(protected)/campanhas/[id]/page.tsx` só passa
  `autoStart` quando `searchParams.get('start') === 'true'`.
- `lead-list.tsx` envia `assigned: currentUserId` (UUID) e
  `GET /api/leads` valida `assigned` com `pattern="^(me|none|any)$"`.
- `apps/web/src/app/(auth)/login/page.tsx` sempre executa
  `router.push('/dashboard')`, descartando o `callbackUrl` que
  `apps/web/src/app/(auth)/aceitar-convite/page.tsx` monta.

## Glossary

- **Plataforma**: o conjunto AlphaMec V1 formado por `services/api`,
  `services/workers` e `apps/web`.
- **API**: o serviço FastAPI em `services/api`.
- **Rota_Webhook_Inbound**: o handler `POST /api/webhooks/email/inbound` em
  `services/api/src/routes/webhooks.py`.
- **Servico_Inbound**: `process_inbound_email` em
  `services/api/src/services/inbound_email_service.py`.
- **Rota_WS_Pipeline**: o endpoint WebSocket de job em
  `services/api/src/routes/pipeline.py`.
- **Servico_Cadencia**: `services/api/src/services/cadence_service.py`,
  incluindo `send_step` e `run_due`.
- **Rota_Leads**: `services/api/src/routes/leads.py`.
- **Servico_BI**: `services/api/src/routes/analytics.py` mais
  `AnalyticsService`.
- **App_Web**: a aplicação Next.js em `apps/web`.
- **Painel_Oportunidades**: a tela de oportunidades do App_Web, cujo componente
  principal é `apps/web/src/components/oportunidades/lead-list.tsx`.
- **Organizacao**: a entidade `Organization`; unidade de isolamento
  multi-tenant. O identificador é `organization_id`.
- **Estado_Terminal**: `LeadStatus.PERDIDO` ou `LeadStatus.DESQUALIFICADO`.
- **Outreach**: envio de e-mail de cadência (`FollowUp` + `Message`) executado
  por Servico_Cadencia.
- **Outreach_Assistido**: modo de operação em que nenhuma mensagem sai para
  destinatário externo real sem confirmação humana explícita na sessão de UAT.
- **Golden_Path**: login → campanha → discovery → scoring → oportunidade →
  evidência → decisor → ação → outreach assistido → CRM → outcome → BI/export.
- **UAT**: execução manual do roteiro em `docs/uat-runbook.md` contra ambiente
  real; leitura de código não constitui UAT.
- **Oferta_TROFEUS**: a oferta de troféus/premiação usada como Golden_Path do UAT.
- **Ofertas_Smoke**: as ofertas SISTEMAS/ERP e ENGENHARIA, usadas apenas como
  verificação de fumaça.
- **Finding**: qualquer problema encontrado durante implementação, revisão ou UAT.
- **BLOCKS_ALPHAMEC**: classificação de Finding cuja correção é obrigatória
  nesta branch.
- **IMPORTANT_ALPHAMEC**: classificação de Finding de alto impacto e custo
  baixo ou médio, admitido nesta branch.
- **DEFER_TO_V2**: classificação de Finding registrado e não implementado nesta
  branch.
- **Ponto_De_Parada**: interrupção do trabalho com registro escrito, aguardando
  aprovação humana explícita antes de qualquer execução.
- **Suite_Testes**: os testes em `tests/` executados por
  `python -m pytest tests -q -W error`.
- **Gates_De_Qualidade**: o conjunto de comandos de verificação definido no
  Requisito 21.

## Requirements

## Bloco 1 — Segurança e invariantes

### Requirement 1: Tenant determinístico no inbound de e-mail

**User Story:** Como responsável técnico da Plataforma, quero que o inbound de
e-mail resolva a Organizacao de forma determinística, para que a resposta de um
lead nunca seja atribuída ao cliente errado.

#### Acceptance Criteria

1. WHEN a Rota_Webhook_Inbound recebe uma requisição, THE API SHALL resolver
   exatamente uma Organizacao antes de qualquer consulta a `Lead`, `Contact`,
   `FollowUp`, `Message` ou `LeadActivity`.
2. IF a Rota_Webhook_Inbound recebe uma requisição sem credencial que identifique
   uma Organizacao existente, THEN THE API SHALL responder com status HTTP 401 e
   SHALL persistir zero registros.
3. WHEN o Servico_Inbound procura o lead correspondente ao remetente, THE API
   SHALL restringir a consulta a `Lead.organization_id` igual à Organizacao
   resolvida na requisição.
4. IF o endereço do remetente existe em duas ou mais Organizacao, THEN THE API
   SHALL considerar apenas os leads da Organizacao resolvida na requisição.
5. IF nenhum lead da Organizacao resolvida corresponde ao remetente, THEN THE
   API SHALL responder `matched=false` e SHALL persistir zero registros.
6. THE Suite_Testes SHALL conter um teste que falha na implementação atual e
   passa após a correção, cobrindo o cenário de duas Organizacao com o mesmo
   endereço de remetente.

### Requirement 2: Escrita confinada à organização do lead

**User Story:** Como diretor comercial, quero que toda mensagem registrada
pertença ao lead da minha própria Organizacao, para que a trilha e o BI sejam
confiáveis.

#### Acceptance Criteria

1. WHEN a API cria um registro `Message`, THE API SHALL vincular o registro a um
   `Lead` cuja `organization_id` é igual à Organizacao do contexto da operação.
2. WHEN a API cria um registro `LeadActivity`, `FollowUp` ou `Notification` a
   partir do inbound, THE API SHALL vincular o registro ao mesmo `Lead`
   verificado no critério 1.
3. IF a Organizacao do contexto da operação difere de `Lead.organization_id`,
   THEN THE API SHALL rejeitar a operação sem persistir registros.
4. THE Suite_Testes SHALL conter um teste negativo que comprova ausência de
   `Message` criada em `Lead` de outra Organizacao após inbound de remetente
   homônimo.

### Requirement 3: Falha fechada em job e WebSocket

**User Story:** Como responsável técnico da Plataforma, quero que o acesso a job
e WebSocket falhe fechado quando não houver Organizacao válida, para que dado de
execução não vaze entre clientes.

#### Acceptance Criteria

1. WHEN um cliente solicita conexão à Rota_WS_Pipeline para um `job_id`, THE API
   SHALL autorizar a conexão somente se `Job.organization_id` estiver preenchido
   e for igual à Organizacao ativa do usuário autenticado.
2. IF `Job.organization_id` é nulo, THEN THE Rota_WS_Pipeline SHALL encerrar a
   conexão com código 403 e SHALL emitir zero mensagens de progresso.
3. IF o `job_id` solicitado pertence a outra Organizacao, THEN THE
   Rota_WS_Pipeline SHALL encerrar a conexão com código 403 e SHALL usar a mesma
   razão de recusa aplicada a job inexistente.
4. WHEN a API cria um `Job`, THE API SHALL preencher `Job.organization_id` com a
   Organizacao do contexto de criação.
5. WHERE uma rota HTTP expõe estado, resultado ou log de `Job`, THE API SHALL
   aplicar as mesmas regras dos critérios 1 a 3.
6. THE Suite_Testes SHALL conter testes negativos para job com
   `organization_id` nulo e para job de outra Organizacao.

### Requirement 4: Estados terminais fora da cadência

**User Story:** Como consultor de vendas, quero que leads em Estado_Terminal
saiam da cadência, para que a AlphaMec não escreva para quem já foi perdido ou
desqualificado.

#### Acceptance Criteria

1. WHEN o Servico_Cadencia executa `send_step` para um `FollowUp` cujo `Lead`
   está em Estado_Terminal, THE API SHALL encerrar a etapa sem enviar e-mail e
   SHALL registrar o motivo do bloqueio.
2. WHEN o Servico_Cadencia executa `run_due`, THE API SHALL excluir da seleção
   todo `FollowUp` cujo `Lead` está em Estado_Terminal.
3. WHEN um `Lead` transiciona para Estado_Terminal, THE API SHALL encerrar todo
   `FollowUp` do lead que esteja em `FollowUpStatus.PENDING`.
4. IF uma etapa é bloqueada por Estado_Terminal, THEN THE API SHALL criar zero
   registros `Message` para o lead.
5. THE Suite_Testes SHALL conter testes que comprovam zero envio para lead em
   `PERDIDO` e zero envio para lead em `DESQUALIFICADO`, tanto por `send_step`
   quanto por `run_due`.

### Requirement 5: Motivo obrigatório em PERDIDO

**User Story:** Como diretor comercial, quero que todo lead marcado como PERDIDO
tenha motivo registrado, para que a análise de perdas e o requeue funcionem.

#### Acceptance Criteria

1. WHEN a Rota_Leads recebe `PATCH /{lead_id}/status` com `status=PERDIDO` e
   `lost_reason` ausente, THE API SHALL rejeitar a requisição com status HTTP 422
   e SHALL manter o `Lead.status` anterior.
2. WHEN a API grava `Lead.status = PERDIDO` por qualquer caminho, THE API SHALL
   gravar `Lead.lost_reason` com um valor do enum `LostReason` na mesma transação.
3. WHEN a API grava `Lead.status = PERDIDO`, THE API SHALL registrar uma
   `LeadActivity` com a ação `LOST` contendo o motivo.
4. THE API SHALL manter `PERDIDO` e `DESQUALIFICADO` como outcomes distintos,
   com registros de trilha distintos.
5. THE Suite_Testes SHALL conter um teste que comprova a impossibilidade de
   `Lead.status = PERDIDO` com `Lead.lost_reason` nulo por qualquer rota exposta
   pela Rota_Leads.

### Requirement 6: Ação em lote sem bypass do motivo

**User Story:** Como consultor de vendas, quero marcar vários leads como perdidos
em lote sem burlar a exigência de motivo, para que o dado do CRM continue íntegro.

#### Acceptance Criteria

1. WHEN o usuário seleciona a ação em lote "Marcar como perdido" no
   Painel_Oportunidades, THE App_Web SHALL solicitar um motivo do enum
   `LostReason` antes de enviar qualquer requisição.
2. WHEN o usuário confirma o motivo, THE App_Web SHALL usar o caminho de API que
   exige motivo para cada lead selecionado.
3. IF o usuário cancela a solicitação de motivo, THEN THE App_Web SHALL enviar
   zero requisições de alteração de status.
4. IF a marcação de um lead do lote falha, THEN THE App_Web SHALL informar a
   quantidade de sucessos e a quantidade de falhas.
5. THE App_Web SHALL apresentar mensagem de sucesso somente após confirmação de
   resposta bem-sucedida da API.

### Requirement 7: Conversão única sob concorrência

**User Story:** Como diretor comercial, quero que o registro de uma venda seja
único por lead e oferta mesmo sob duplo clique, para que a receita não seja
contada duas vezes no BI.

#### Acceptance Criteria

1. WHEN a Rota_Leads recebe duas ou mais requisições concorrentes de conversão
   para o mesmo `lead_id` e `offer_key`, THE API SHALL persistir exatamente um
   registro `Conversion`.
2. WHILE existe um registro `Conversion` para o par `lead_id` e `offer_key`, THE
   API SHALL responder às novas requisições de conversão do mesmo par com status
   HTTP 409.
3. THE banco de dados SHALL impedir, por constraint, mais de um registro
   `Conversion` para o mesmo par `lead_id` e `offer_key`.
4. WHEN a constraint do critério 3 é violada durante a inserção, THE API SHALL
   converter a violação em resposta HTTP 409 sem expor detalhe interno do banco.
5. THE Suite_Testes SHALL conter um teste que simula inserção concorrente e
   comprova a contagem final igual a 1.

### Requirement 8: Migrations aditivas e auditáveis

**User Story:** Como responsável técnico da Plataforma, quero que mudanças de
schema sejam aditivas e auditáveis, para que nenhuma correção destrua dado de
produção.

#### Acceptance Criteria

1. WHERE uma invariante desta spec exige garantia no banco, THE Plataforma SHALL
   receber uma nova migration Alembic em `services/workers`.
2. THE Plataforma SHALL preservar as migrations existentes sem alteração de
   conteúdo.
3. IF a implementação de uma invariante exige remoção de coluna, remoção de
   tabela ou qualquer alteração destrutiva de schema, THEN THE responsável SHALL
   registrar um Ponto_De_Parada e SHALL aguardar aprovação humana antes de
   executar.
4. IF dados existentes violam a constraint que a migration introduz, THEN THE
   responsável SHALL registrar um Ponto_De_Parada descrevendo as linhas em
   conflito antes de aplicar a constraint.
5. WHEN as migrations são aplicadas, THE comando `alembic heads` SHALL reportar
   exatamente uma cabeça.

## Bloco 2 — Golden Path AlphaMec

### Requirement 9: Criar e iniciar coleta realmente inicia

**User Story:** Como consultor de vendas, quero que "Criar e iniciar coleta"
realmente inicie a coleta, para que a promessa do botão corresponda ao resultado.

#### Acceptance Criteria

1. WHEN o usuário confirma o brief com a opção de iniciar coleta, THE App_Web
   SHALL navegar para a página da campanha com o parâmetro que ativa o início
   automático da coleta.
2. WHEN a página da campanha é carregada com o parâmetro de início automático,
   THE App_Web SHALL disparar a coleta uma única vez por carregamento.
3. WHEN o usuário confirma o brief sem a opção de iniciar coleta, THE App_Web
   SHALL criar a campanha e SHALL disparar zero coletas.
4. WHILE a coleta iniciada automaticamente está em execução, THE App_Web SHALL
   exibir o progresso da execução na página da campanha.
5. IF a coleta iniciada automaticamente falha, THEN THE App_Web SHALL exibir a
   causa da falha e uma ação de nova tentativa.

### Requirement 10: Contrato do filtro Meus Leads

**User Story:** Como consultor de vendas, quero que o filtro "Meus Leads"
retorne minha carteira, para que a fila de trabalho seja confiável.

#### Acceptance Criteria

1. WHEN o usuário ativa o filtro "Meus Leads" no Painel_Oportunidades, THE
   App_Web SHALL enviar ao endpoint de listagem de leads um valor aceito pelo
   contrato do parâmetro `assigned`.
2. WHEN a Rota_Leads recebe o filtro de atribuição enviado pelo App_Web, THE API
   SHALL retornar apenas leads da Organizacao ativa atribuídos ao usuário
   autenticado.
3. IF o valor recebido no parâmetro de atribuição não pertence ao contrato, THEN
   THE API SHALL responder com status HTTP 422.
4. WHEN o filtro "Meus Leads" está ativo e o resultado é vazio, THE App_Web SHALL
   exibir estado vazio que declara o filtro aplicado.
5. THE Suite_Testes SHALL conter um teste de contrato que compara o valor enviado
   pelo App_Web com os valores aceitos pela Rota_Leads.

### Requirement 11: Redirecionamento pós-login seguro

**User Story:** Como usuário convidado, quero voltar ao destino pretendido após o
login, para concluir o fluxo sem me perder.

#### Acceptance Criteria

1. WHEN o login é concluído com sucesso e existe um `callbackUrl` na URL, THE
   App_Web SHALL redirecionar o usuário ao destino informado.
2. IF o `callbackUrl` não é um caminho relativo interno da própria aplicação,
   THEN THE App_Web SHALL redirecionar o usuário para `/dashboard`.
3. WHEN o login é concluído com sucesso e não existe `callbackUrl`, THE App_Web
   SHALL redirecionar o usuário para `/dashboard`.
4. WHEN um usuário já cadastrado abre um convite e precisa autenticar, THE
   App_Web SHALL preservar o destino do convite através do login e SHALL retornar
   à página de aceite após a autenticação.
5. IF o e-mail da sessão difere do e-mail do convite, THEN THE App_Web SHALL
   informar a divergência e SHALL oferecer troca de conta.
6. THE Suite_Testes SHALL conter testes para os valores de `callbackUrl`
   absolutos externos, com esquema alternativo e com barras iniciais duplicadas,
   comprovando redirecionamento para `/dashboard`.

### Requirement 12: Vazio distinto de falha de provider

**User Story:** Como consultor de vendas, quero distinguir "nada encontrado" de
"a busca falhou", para não abandonar uma campanha por causa de um erro técnico.

#### Acceptance Criteria

1. WHILE uma requisição de dados está em andamento, THE App_Web SHALL exibir
   estado de carregamento na região correspondente.
2. IF uma requisição de dados falha, THEN THE App_Web SHALL exibir estado de erro
   com uma ação de nova tentativa.
3. IF um provider retorna estado `EMPTY`, THEN THE App_Web SHALL apresentar o
   resultado como ausência de correspondência.
4. IF um provider retorna estado `FAILED`, `DISABLED` ou `QUOTA_EXCEEDED`, THEN
   THE App_Web SHALL apresentar o estado específico do provider e SHALL evitar a
   mensagem de ausência de resultados.
5. WHEN um resultado é parcial por falha de um provider entre vários, THE
   App_Web SHALL indicar que o resultado está incompleto e qual provider falhou.
6. THE App_Web SHALL identificar como inferência todo valor derivado por
   heurística ou por modelo de linguagem, distinguindo-o de dado com fonte
   verificada.

## Bloco 3 — UAT real

### Requirement 13: UAT executado em ambiente real

**User Story:** Como diretor da AlphaMec, quero um UAT executado no sistema real,
para confiar que a operação funciona sem desenvolvedor por perto.

#### Acceptance Criteria

1. THE responsável SHALL executar o roteiro de `docs/uat-runbook.md` contra
   Postgres real, API real, App_Web real e os providers configurados disponíveis,
   incluindo Google API e Groq.
2. THE responsável SHALL executar o Golden_Path completo com a Oferta_TROFEUS.
3. THE responsável SHALL executar verificação de fumaça com as Ofertas_Smoke,
   cobrindo discovery, scoring e visualização de oportunidade.
4. WHILE o UAT está em execução, THE Plataforma SHALL operar em
   Outreach_Assistido, sem envio automático para destinatário externo real.
5. WHEN cada item do roteiro é executado, THE responsável SHALL registrar
   resultado observado e evidência.
6. IF um item do roteiro não pode ser executado no ambiente disponível, THEN THE
   responsável SHALL registrar o item como não executado com a causa, sem
   marcá-lo como aprovado.

### Requirement 14: Utilidade comercial das oportunidades

**User Story:** Como diretor da AlphaMec, quero avaliar utilidade comercial das
oportunidades, não apenas se o sistema executou, para decidir se posso vender com
isso.

#### Acceptance Criteria

1. WHEN uma oportunidade da Oferta_TROFEUS é avaliada no UAT, THE responsável
   SHALL verificar os nove itens: existência real do evento ou empresa,
   evidência real e rastreável, plausibilidade do score, utilidade do timing,
   organizador correto, decisor útil, contato disponível, próxima ação definida e
   abordagem sugerida.
2. THE responsável SHALL avaliar no mínimo dez oportunidades da Oferta_TROFEUS
   com os nove itens do critério 1.
3. IF a evidência apresentada não é localizável na fonte declarada, THEN THE
   responsável SHALL registrar a oportunidade como não útil.
4. IF um valor inferido é apresentado como fato verificado, THEN THE responsável
   SHALL registrar um Finding classificado como `BLOCKS_ALPHAMEC`.
5. WHEN a avaliação termina, THE responsável SHALL registrar a proporção de
   oportunidades consideradas comercialmente úteis.

### Requirement 15: Decisão sobre provider de eventos por evidência

**User Story:** Como diretor da AlphaMec, quero que a decisão sobre provider de
eventos seja tomada por evidência do UAT, para não investir em integração
desnecessária.

#### Acceptance Criteria

1. WHEN a avaliação do Requisito 14 é concluída, THE responsável SHALL decidir
   sobre o provider especializado de eventos e MEJ com base exclusivamente no
   resultado registrado.
2. IF a qualidade entregue pelo provider de eventos atual é insuficiente para a
   operação da AlphaMec, THEN THE responsável SHALL classificar o provider
   especializado como `BLOCKS_ALPHAMEC` e SHALL implementá-lo nesta branch.
3. IF a qualidade entregue pelo provider de eventos atual é suficiente para a
   operação da AlphaMec, THEN THE responsável SHALL classificar o provider
   especializado como `DEFER_TO_V2` e SHALL registrar a justificativa.
4. WHERE o provider especializado é implementado, THE Plataforma SHALL registrar
   provenance, confiança e os estados `FOUND`, `EMPTY`, `FAILED`, `DISABLED` e
   `QUOTA_EXCEEDED` do provider.
5. THE responsável SHALL registrar a decisão com os dados observados que a
   sustentam antes de iniciar qualquer implementação decorrente.

### Requirement 16: Classificação e contenção de findings

**User Story:** Como responsável técnico da Plataforma, quero controle de escopo
sobre os achados, para que o UAT não vire uma nova rodada de features.

#### Acceptance Criteria

1. WHEN um Finding é registrado, THE responsável SHALL atribuir exatamente uma
   das classificações `BLOCKS_ALPHAMEC`, `IMPORTANT_ALPHAMEC` ou `DEFER_TO_V2`.
2. THE responsável SHALL corrigir nesta branch todos os Findings classificados
   como `BLOCKS_ALPHAMEC`.
3. WHERE um Finding é classificado como `IMPORTANT_ALPHAMEC`, THE responsável
   SHALL implementá-lo apenas quando o impacto for alto e o custo for baixo ou
   médio.
4. WHERE um Finding é classificado como `DEFER_TO_V2`, THE responsável SHALL
   registrá-lo em documentação e SHALL manter o código desta branch inalterado
   por causa dele.
5. THE responsável SHALL manter os quatro blocos desta spec como escopo total do
   trabalho.

## Bloco 4 — BI mínimo de operação

### Requirement 17: Funil operacional da organização

**User Story:** Como diretor da AlphaMec, quero uma visão única do funil, para
entender a operação sem pedir relatório para ninguém.

#### Acceptance Criteria

1. THE Servico_BI SHALL expor, para a Organizacao ativa, as quantidades de leads
   encontrados, qualificados, abordados, respostas, reuniões, propostas, ganhos e
   perdas.
2. THE Servico_BI SHALL expor a taxa de conversão calculada a partir das
   quantidades do critério 1.
3. WHEN o usuário aplica um período, THE Servico_BI SHALL restringir todas as
   quantidades ao período informado.
4. THE App_Web SHALL apresentar as métricas do critério 1 e do critério 2 em uma
   única tela alcançável a partir da navegação principal.
5. THE Servico_BI SHALL restringir todo resultado a `organization_id` da
   Organizacao ativa.
6. THE Servico_BI SHALL contar `PERDIDO` e `DESQUALIFICADO` como categorias
   distintas.

### Requirement 18: Cortes por campanha, oferta e canal

**User Story:** Como diretor da AlphaMec, quero cortar as métricas por campanha,
oferta e canal, para saber onde a operação está funcionando.

#### Acceptance Criteria

1. WHERE o corte por campanha está disponível, THE Servico_BI SHALL permitir
   filtrar as métricas do Requisito 17 por campanha da Organizacao ativa.
2. WHERE o corte por oferta está disponível, THE Servico_BI SHALL permitir
   filtrar as métricas do Requisito 17 por `offer_key`.
3. WHERE o dado de canal existe no registro de origem, THE Servico_BI SHALL
   permitir filtrar as métricas de abordagem e resposta por canal.
4. IF uma dimensão de corte não possui dado persistido para o período
   selecionado, THEN THE Servico_BI SHALL declarar a ausência de dado em vez de
   retornar zero como valor medido.
5. WHEN dois ou mais filtros são aplicados simultaneamente, THE Servico_BI SHALL
   aplicar a conjunção dos filtros.
6. THE App_Web SHALL permitir exportar a visão filtrada exibida na tela.

### Requirement 19: Consistência dos números do BI

**User Story:** Como diretor da AlphaMec, quero que os números do BI sejam
consistentes entre si, para tomar decisão sem conferir na planilha.

#### Acceptance Criteria

1. WHEN o Servico_BI apresenta um corte por dimensão, THE Servico_BI SHALL
   manter a soma das partes igual ao total do mesmo período e filtro, mais a
   parcela sem valor na dimensão quando existir.
2. THE Servico_BI SHALL expor o tamanho da amostra de cada agregação
   apresentada.
3. IF a amostra de uma agregação é insuficiente para leitura, THEN THE
   Servico_BI SHALL sinalizar a insuficiência junto ao valor.
4. THE Servico_BI SHALL derivar as métricas de resultado comercial dos registros
   persistidos de outcome, trilha e conversão.
5. THE Servico_BI SHALL apresentar a mesma quantidade para a mesma métrica em
   telas diferentes sob período e filtros iguais.

### Requirement 20: Contenção de escopo do BI

**User Story:** Como responsável técnico da Plataforma, quero conter o escopo do
BI, para não construir uma solução de BI corporativo nesta branch.

#### Acceptance Criteria

1. THE Plataforma SHALL entregar o BI dos Requisitos 17 a 19 usando os recursos
   já existentes na Plataforma, sem ferramenta externa de BI.
2. WHERE a análise por variante de mensagem é necessária para a AlphaMec operar
   no UAT, THE Plataforma SHALL expô-la nesta branch.
3. IF a análise por variante de mensagem não é necessária para a AlphaMec operar
   no UAT, THEN THE responsável SHALL classificá-la como `DEFER_TO_V2`.
4. WHERE a atribuição avançada de resultado é necessária para a AlphaMec operar
   no UAT, THE Plataforma SHALL expô-la nesta branch.
5. IF a atribuição avançada de resultado não é necessária para a AlphaMec operar
   no UAT, THEN THE responsável SHALL classificá-la como `DEFER_TO_V2`.

## Requisitos transversais

### Requirement 21: Gates de qualidade executados

**User Story:** Como responsável técnico da Plataforma, quero gates de qualidade
executados e verdes, para que a branch seja segura de mesclar.

#### Acceptance Criteria

1. WHEN uma correção de invariante do Bloco 1 é implementada, THE responsável
   SHALL escrever primeiro um teste que reproduz o problema e falha, e somente
   depois a correção.
2. THE responsável SHALL executar `python -m pytest tests -q -W error` com
   resultado sem falhas e sem erros.
3. THE responsável SHALL executar
   `python -m compileall -q services/api services/workers` sem erros.
4. THE responsável SHALL executar o Genericity Harness sem regressão de
   genericidade do núcleo.
5. THE responsável SHALL executar `alembic heads` obtendo exatamente uma cabeça e
   `alembic upgrade head` sem erros.
6. THE responsável SHALL executar `npm run lint`, `npx tsc --noEmit` e
   `npm run build` em `apps/web` sem erros.
7. THE responsável SHALL executar verificação de navegador nos fluxos do Bloco 2
   e SHALL anexar as evidências.
8. WHERE o Graphify é comprovadamente executável no ambiente, THE responsável
   SHALL executar `graphify update .` após as mudanças de código.
9. IF qualquer gate dos critérios 2 a 7 falha, THEN THE responsável SHALL
   corrigir a causa antes de declarar a spec concluída.

### Requirement 22: Preservação das invariantes de arquitetura

**User Story:** Como responsável técnico da Plataforma, quero preservar as
invariantes de arquitetura já conquistadas, para que as correções não regridam o
produto.

#### Acceptance Criteria

1. THE Plataforma SHALL preservar a oferta-centricidade, incluindo
   `OfferProfile` e `OfferMatcher`, sem acoplar oferta específica ao núcleo.
2. THE Plataforma SHALL manter os snapshots de oportunidade como registros
   somente-inserção.
3. THE Plataforma SHALL preservar provenance e confiança dos dados coletados e
   inferidos.
4. THE Plataforma SHALL preservar os estados de provider `FOUND`, `EMPTY`,
   `FAILED`, `DISABLED` e `QUOTA_EXCEEDED` como valores distintos.
5. THE Plataforma SHALL manter a confirmação humana nos pontos de decisão
   comercial já existentes.
6. THE Plataforma SHALL manter `services/workers/src/database/models.py` como
   única definição dos modelos, com a API apenas reexportando.
7. THE Plataforma SHALL manter toda análise de site restrita a coleta passiva.

### Requirement 23: Definition of Done da branch

**User Story:** Como diretor da AlphaMec, quero um critério de conclusão
inequívoco, para saber quando o sistema está pronto para a operação.

#### Acceptance Criteria

1. WHEN todos os Requisitos 1 a 22 estão atendidos, THE responsável SHALL
   registrar a declaração "ALPHAMEC — PRODUCTION READY: YES".
2. THE responsável SHALL demonstrar o Golden_Path completo em uma única sessão,
   sem intervenção de desenvolvedor.
3. IF a demonstração do Golden_Path exige intervenção de desenvolvedor em
   qualquer etapa, THEN THE responsável SHALL registrar a etapa como
   `BLOCKS_ALPHAMEC` e SHALL manter a spec aberta.
4. THE responsável SHALL submeter o trabalho a revisão de implementação e, em
   seguida, a revisão de código, cobrindo isolamento entre Organizacao,
   idempotência, Estado_Terminal, concorrência, contrato entre App_Web e API, UX
   enganosa, inferência apresentada como fato e falha de provider apresentada
   como ausência de resultado.
5. THE responsável SHALL trabalhar na branch `feat/alphamec-production-ready`
   originada de `main @ 27d2925`.

## Propriedades de Correção

Propriedades destinadas a teste baseado em propriedades (property-based testing)
das invariantes desta spec. Cada propriedade deve valer para qualquer entrada
gerada dentro do domínio indicado.

### Isolamento entre organizações

- **P1 — Inbound confinado à organização.** Para qualquer conjunto de
  organizações, leads e contatos, e qualquer endereço de remetente, o lead
  afetado por um inbound autenticado para a organização `O` tem
  `organization_id == O`, ou nenhum lead é afetado.
  _Cobre: Requisito 1._
- **P2 — Escrita confinada à organização.** Para qualquer sequência de operações
  de inbound, toda `Message`, `LeadActivity`, `FollowUp` e `Notification` criada
  pertence a um lead da organização resolvida na operação que a criou.
  _Cobre: Requisito 2._
- **P3 — Ausência de efeito sem correspondência.** Para qualquer inbound sem lead
  correspondente na organização resolvida, a contagem de registros de todas as
  tabelas envolvidas permanece igual à contagem anterior à requisição.
  _Cobre: Requisitos 1 e 2._
- **P4 — Falha fechada de job.** Para qualquer job `J` e qualquer usuário `U`, o
  acesso é autorizado se e somente se `J.organization_id` é não nulo e igual à
  organização ativa de `U`. Job com `organization_id` nulo nunca é autorizado.
  _Cobre: Requisito 3._
- **P5 — Indistinguibilidade da recusa.** Para qualquer job inexistente e
  qualquer job de outra organização, a resposta de recusa é idêntica em código e
  razão, sem revelar existência.
  _Cobre: Requisito 3._
- **P6 — Leitura confinada.** Para qualquer consulta de BI ou de listagem
  executada no contexto da organização `O`, todo registro retornado tem
  `organization_id == O`.
  _Cobre: Requisitos 10 e 17._

### Estados terminais

- **P7 — Estado terminal absorve a cadência.** Para qualquer lead que entre em
  `PERDIDO` ou `DESQUALIFICADO` no instante `t`, o número de `Message` de
  outreach com `sent_at > t` para esse lead é zero.
  _Cobre: Requisito 4._
- **P8 — Seleção de vencidos exclui terminais.** Para qualquer população de
  `FollowUp` pendentes, o conjunto selecionado por `run_due` é disjunto do
  conjunto de follow-ups de leads em estado terminal.
  _Cobre: Requisito 4._
- **P9 — Sem pendências após terminal.** Para qualquer lead em estado terminal,
  a contagem de `FollowUp` com status `PENDING` é zero após a transição.
  _Cobre: Requisito 4._

### Motivo de perda

- **P10 — Perda implica motivo.** Para qualquer sequência de requisições
  aceitas, todo lead com `status == PERDIDO` tem `lost_reason` não nulo e
  pertencente ao enum `LostReason`.
  _Cobre: Requisitos 5 e 6._
- **P11 — Rejeição preserva estado.** Para qualquer requisição de status
  rejeitada, o `status` e o `lost_reason` do lead permanecem iguais aos valores
  anteriores à requisição.
  _Cobre: Requisito 5._
- **P12 — Lote equivale a individual.** Para qualquer conjunto de leads, o efeito
  da ação em lote de perda é igual ao efeito da mesma marcação executada
  individualmente lead por lead.
  _Cobre: Requisito 6._
- **P13 — Perda e desqualificação não colapsam.** Para qualquer lead, `PERDIDO` e
  `DESQUALIFICADO` produzem trilhas e outcomes distintos, e nenhum caminho
  converte um no outro.
  _Cobre: Requisitos 5 e 17._

### Idempotência e concorrência

- **P14 — Conversão única.** Para qualquer `n >= 1` de requisições de conversão
  concorrentes ou sequenciais com o mesmo `lead_id` e `offer_key`, a contagem
  final de `Conversion` para o par é exatamente 1.
  _Cobre: Requisito 7._
- **P15 — Exatamente um sucesso.** Para qualquer `n >= 2` de requisições
  concorrentes do mesmo par, exatamente uma resposta é de sucesso e as demais são
  HTTP 409.
  _Cobre: Requisito 7._
- **P16 — Sem vazamento de erro de banco.** Para qualquer violação de constraint
  provocada por concorrência, o corpo da resposta não contém nome de constraint,
  nome de tabela nem texto de exceção do banco.
  _Cobre: Requisito 7._
- **P17 — Idempotência de outcome.** Para qualquer repetição da mesma transição
  de status com a mesma chave de evento, a quantidade de outcomes comerciais
  persistidos não aumenta.
  _Cobre: Requisitos 5 e 19._
- **P18 — Snapshots somente-inserção.** Para qualquer sequência de operações,
  nenhum registro de snapshot de oportunidade existente é alterado ou removido.
  _Cobre: Requisito 22._

### Contrato entre App_Web e API

- **P19 — Valores de filtro pertencem ao contrato.** Para qualquer estado da
  interface do Painel_Oportunidades, o valor enviado no parâmetro de atribuição
  pertence ao conjunto aceito pela API.
  _Cobre: Requisito 10._
- **P20 — Redirecionamento interno.** Para qualquer string fornecida como
  `callbackUrl`, o destino final do redirecionamento é um caminho relativo da
  própria aplicação; qualquer outro valor resulta em `/dashboard`.
  _Cobre: Requisito 11._
- **P21 — Intenção do botão preservada.** Para qualquer confirmação de brief com
  a intenção de iniciar coleta, exatamente uma coleta é iniciada; sem essa
  intenção, nenhuma coleta é iniciada.
  _Cobre: Requisito 9._

### Apresentação honesta

- **P22 — Vazio distinto de falha.** Para qualquer combinação de estados de
  provider, a interface apresenta ausência de resultados apenas quando todos os
  providers consultados retornaram `EMPTY`.
  _Cobre: Requisito 12._
- **P23 — Inferência rotulada.** Para qualquer valor exibido, se a origem do
  valor é heurística ou modelo de linguagem, o valor é apresentado com marcação
  de inferência.
  _Cobre: Requisitos 12 e 14._

### Consistência do BI

- **P24 — Partição fechada.** Para qualquer período, filtro e dimensão, a soma
  das partes do corte mais a parcela sem valor na dimensão é igual ao total da
  métrica.
  _Cobre: Requisito 19._
- **P25 — Monotonicidade do funil.** Para qualquer período e filtro, cada etapa
  do funil tem quantidade menor ou igual à etapa imediatamente anterior.
  _Cobre: Requisitos 17 e 19._
- **P26 — Comutatividade de filtros.** Para qualquer conjunto de filtros
  compatíveis, o resultado é independente da ordem de aplicação.
  _Cobre: Requisito 18._
- **P27 — Taxa em domínio válido.** Para qualquer período e filtro, a taxa de
  conversão está no intervalo de 0 a 1, e é declarada indisponível quando o
  denominador é zero.
  _Cobre: Requisitos 17 e 19._
- **P28 — Ausência de dado não é zero.** Para qualquer dimensão sem dado
  persistido no período, a resposta declara ausência de dado em vez de valor
  medido igual a zero.
  _Cobre: Requisito 18._
