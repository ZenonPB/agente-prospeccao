# Implementation Plan: Consolidação da Plataforma Comercial

## Overview

Este plano converte `design.md` e `requirements.md` em PRs/fatias verticais incrementais para B4–B10. A ordem é deliberada: primeiro tenant/RBAC e schema, depois importação segura, BI cross-filter, CRM operacional, learning observacional, Golden Path, UAT multi-workspace e, por último, campanhas reais e hardening.

A implementação deve usar Python nos serviços API/workers, preservando as superfícies existentes de Next.js 16/React 19/TypeScript apenas onde o fluxo exigir integração frontend. Cada subtarefa é um prompt incremental para um agente de código: deve modificar ou testar somente o escopo descrito, integrar o resultado com o que já existe e não deixar endpoints, tabelas, componentes ou serviços órfãos.

**Regras obrigatórias em todas as tarefas:** não inventar endpoints ou payloads; consultar as rotas, schemas, hooks e testes reais antes de alterar consumidores; não duplicar `Company`, `Person`, `Lead`, `LeadOpportunity`, `LeadOpportunitySnapshot`, `CommercialTask`, `LeadActivity`, `CommercialOutcome`, `Conversion` ou `OfferProfile`; não editar migrations existentes; criar somente migrations Alembic novas, aditivas e expand-compatible; não alterar score, OfferProfile ou registry efetivo silenciosamente; preservar `UNKNOWN != FALSE`, a análise passiva de sites e o isolamento por `organization_id`.

**Convenção de testes:** subtarefas marcadas com `*` são opcionais conforme o formato da spec, mas os gates descritos nas tarefas de implementação são obrigatórios para aceitar cada PR. Toda validação deve registrar o mesmo HEAD, ambiente e resultado; falha pré-existente não deve ser normalizada como sucesso.

## Tasks

- [x] 1. Preparação: contratos tenant-first, RBAC, auditoria e schema gates
  - [x] 1.1 Mapear e fechar os limites tenant-first antes do import
    - **Prompt para o agente:** audite os caminhos existentes de API, services, jobs, WebSocket, analytics, export, provider e cache que serão tocados por B4–B10; introduza somente helpers/contratos compatíveis com o `OrganizationContext` já existente para derivar workspace, membership, papel e carteira antes da primeira leitura. Faça cada command service validar workspace, entidade e campos mutáveis por allowlist, sem aceitar `organization_id` confiado do cliente.
    - **Arquivos/domínios:** `services/api/src/auth/`, middleware/dependencies de organização e RBAC, rotas/services que serão reutilizados pelos batches, `services/api/src/jobs_consumer.py`, testes tenant existentes em `tests/`.
    - **Migration:** nenhuma nesta subtarefa; não alterar schema até o inventário demonstrar a necessidade.
    - **Testes/aceite:** requests com dois workspaces e UUID conhecido falham fechados e sem side effect; CONSULTOR permanece limitado à carteira; relações carregadas também pertencem ao workspace; secrets, providers, overlays, jobs e exports não cruzam tenant. Não criar rota nova para mascarar drift.
    - **Riscos:** alterar dependências compartilhadas pode quebrar consumidores atuais; manter respostas indistinguíveis entre inexistente e cross-tenant conforme o contrato real.
    - **Gate obrigatório:** `python -m compileall -q services/api services/workers`; `python -m pytest tests -q -W error`; testes tenant/RBAC e smoke E2E aplicáveis. Frontend somente se houver mudança em consumidor: `npm ci`, lint, `npx tsc --noEmit`, build, a11y e responsividade.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [x]* 1.2 Escrever a prova de isolamento tenant-first
    - **Prompt para o agente:** transforme a Property 1 do design em testes negativos determinísticos para rotas, services, jobs, WebSocket, analytics, export, provider e cache que já possam ser exercitados sem implementar B4–B10. Cubra membership/RBAC, carteira de CONSULTOR, UUIDs conhecidos e ausência de `organization_id`; reutilize fixtures existentes e não crie uma segunda arquitetura de autorização.
    - **Valida:** **Property 1: Isolamento tenant-first**; Requirements 1.1–1.5 e 8.2–8.3.
    - **Arquivos/domínios:** `tests/` e testes específicos dos serviços já existentes; somente fixtures/helpers compartilhados quando necessário.
    - **Migration:** nenhuma.
    - **Aceite:** cada operação rejeita antes de leitura/efeito, não revela existência cross-tenant e preserva estado persistido e assíncrono.
    - **Gate obrigatório:** pytest com `-W error`, incluindo testes de concorrência aplicáveis; não aceitar mocks que não exercitem o predicate tenant-first.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [x] 1.3 Criar o gate de schema para jobs e constraints comerciais observadas
    - **Prompt para o agente:** confirme no PostgreSQL controlado o estado real de `Job.organization_id`, unicidade de conversões, regra de `lost_reason` e índices/identidade de `Person`. Implemente apenas as correções aditivas justificadas pelo schema real: backfill determinístico e auditável, rejeição de órfãos, `NOT NULL` depois do backfill, constraints/índices parciais somente após relatório de colisões e índices `(organization_id,status,created_at)` quando o hot path for comprovado.
    - **Arquivos/domínios:** `services/workers/src/database/models.py`, novas migrations em `services/workers/migrations/versions/`, `services/api/src/jobs_consumer.py`, verifier de schema/migration e testes de Postgres.
    - **Migration:** criar uma ou mais migrations novas, expand-compatible, idempotentes para backfill; não reescrever `Job` ou migrations existentes. Rejeitar órfãos sem inventar `organization_id`.
    - **Aceite:** `alembic upgrade head` funciona duas vezes; uma única cabeça permanece; job sem workspace não pode ser enfileirado/processado; constraints reais são verificadas contra o modelo; rollback/recovery da migration é documentado no teste, sem dropar coluna em produção.
    - **Riscos:** dados históricos ambíguos e colisões de unicidade; interromper o backfill em vez de fabricar associação.
    - **Gate obrigatório:** migration/schema verifier, `alembic upgrade head` duas vezes, seed smoke, testes Postgres de job órfão e concorrência; além de `compileall` e `pytest -W error`.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

- [x] 2. B4.1: contrato e schema do Import Job tenant-scoped
  - [x] 2.1 Implementar o lifecycle persistido do Import Job e seus resultados
    - **Prompt para o agente:** crie o ciclo de vida `DRAFT`, `PREVIEWED`, `QUEUED`, `RUNNING`, `SUCCEEDED`, `PARTIAL`, `FAILED`, `CANCEL_REQUESTED` e `CANCELLED`, com versão, actor, source hash, idempotency key, mapping, contadores, row results, auditoria e recovery. Integre com o consumer existente somente após validar workspace e claim com `FOR UPDATE SKIP LOCKED`; estados e transições devem ser rejeitados de forma explícita quando inválidos.
    - **Arquivos/domínios:** `services/workers/src/database/models.py`, nova migration, `services/api/src/services/import_job_service.py` e schemas/routes existentes ou novos somente se o contrato real autorizar, `services/api/src/jobs_consumer.py`, testes de domínio.
    - **Migration:** criar tabelas/índices de import job, row result e auditoria de forma aditiva; FK e índice devem incluir `organization_id` nos hot paths; preservar jobs legados e registrar órfãos sem processá-los.
    - **Aceite:** toda transição exige actor autorizado, versão esperada, `organization_id` não nulo e auditoria; `SUCCEEDED`/`CANCELLED` são terminais; no máximo um claim por job; segredos, tokens, conteúdo bruto e PII desnecessária não entram em logs.
    - **Riscos:** divergência entre enum Python/Postgres e retries concorrentes; manter o modelo canônico dos workers como fonte única.
    - **Gate obrigatório:** compileall, pytest `-W error`, migration/schema/seed em Postgres, testes tenant/RBAC, idempotência e claim concorrente, além de E2E comercial de criação/consulta se o endpoint existir no contrato real.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [ ]* 2.2 Testar estados, idempotência e claim concorrente do Import Job
    - **Prompt para o agente:** escreva testes de unidade e Postgres para transições válidas/inválidas, confirmação concorrente com a mesma chave, isolamento entre workspaces, retry de job, cancelamento, terminalidade e contadores persistidos. Prove que o mesmo `source_hash` + `idempotency_key` produz uma única importação lógica.
    - **Valida:** **Property 2: Idempotência de importação**; Requirements 2.1, 2.10–2.17.
    - **Arquivos/domínios:** testes do Import Job e fixtures Postgres; nenhum novo modelo paralelo para facilitar o teste.
    - **Migration:** validar a migration de 2.1; não criar migration de teste separada.
    - **Aceite:** corrida não duplica trabalho nem efeitos; retry reaproveita resultado persistido; job de outro workspace não é reutilizado; soma de estados/contadores permanece coerente.
    - **Gate obrigatório:** Postgres real para concorrência e `pytest -W error`; fixtures devem cobrir pelo menos dois workspaces.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

- [ ] 3. B4.2: upload seguro, parsing, preview, mapping e dry-run
  - [ ] 3.1 Implementar validação de CSV/XLSX e preview sem efeitos canônicos
    - **Prompt para o agente:** implemente parser seguro com validação do tipo real e extensão, limites de 25 MiB, 100.000 linhas, 1.000.000 células e 100 colunas, cabeçalho obrigatório, CSV UTF-8/UTF-8 BOM, escape de conteúdo de planilha e preview de no máximo 100 linhas. O preview deve identificar colunas e sugerir mapping sem criar ou alterar entidades canônicas; URLs permanecem dados e nunca são buscadas.
    - **Arquivos/domínios:** serviços de parsing/import API existentes, schemas da API, `apps/web/src/lib/api.ts`, tipos e componentes de upload/preview existentes ou novos sob a convenção atual.
    - **Migration:** nenhuma salvo necessidade comprovada de versão/hash/mapping não coberta por 2.1; se necessária, criar migration nova aditiva.
    - **Aceite:** fórmula executável, arquivo malformado, limite excedido, encoding inválido e estrutura mínima inválida são rejeitados; HTML/script é texto escapado; fórmula não executa; SSRF não ocorre; preview/dry-run não mutam Company, Person, Lead, Opportunity, Task, Activity ou Outcome.
    - **Riscos:** zip bomb/parser DoS, formula injection, XSS no preview e contratos frontend/backend divergentes.
    - **Gate obrigatório:** compileall, pytest `-W error`, testes de segurança de arquivo/SSRF/XSS e side effect; se houver frontend, `npm ci`, lint, `tsc`, build, a11y e responsividade do fluxo de upload.
    - **Guardrails:** não inventar endpoints/payloads, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [ ]* 3.2 Testar preview, dry-run e limites de segurança
    - **Prompt para o agente:** crie testes para MIME/assinatura/extension, encoding, fórmula, HTML/XSS, URL privada, tamanho, linhas, células, colunas, mapeamento ausente/duplicado e comparação antes/depois das fontes canônicas. Inclua estados empty/error/partial e testes acessíveis para o preview quando o frontend for alterado.
    - **Valida:** **Property 8: Preview, estados e recuperação do import sem efeitos indevidos**; Requirements 2.2–2.6 e 8.1.
    - **Arquivos/domínios:** testes Python de parser/service e testes frontend existentes; não executar servidor interativo como substituto de testes automatizados.
    - **Migration:** somente validação das migrations existentes do B4.
    - **Aceite:** nenhuma fórmula/requisição é executada, nenhum arquivo bruto/segredo é exposto e nenhum registro canônico muda antes da confirmação.
    - **Gate obrigatório:** pytest `-W error`, testes de contrato e, para UI, lint/tsc/build/a11y/responsive.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [ ] 3.3 Integrar mapping versionado e confirmação autorizada
    - **Prompt para o agente:** conecte preview, mapping explícito, dry-run e confirmação ao Import Job de 2.1. Cada coluna deve ser aceita ou ignorada; campos canônicos de valor único não podem receber mapping duplicado; a confirmação exige versão exata, autorização e persistência de auditoria antes do enqueue. Preserve compatibilidade do import legado somente se o contrato existente exigir e marque-o como legado/tenant-safe.
    - **Arquivos/domínios:** `services/api/src/services/import_job_service.py`, routes/schemas reais, hooks/types/componentes de import em `apps/web`, testes de contrato.
    - **Migration:** nenhuma nova se 2.1 cobrir versionamento; qualquer alteração deve ser nova e expand-compatible.
    - **Aceite:** arquivo/mapping/versão alterados exigem novo dry-run; falha de auditoria impede enqueue; confirmação concorrente retorna o mesmo job; nenhum `organization_id` vem do arquivo ou do payload confiado.
    - **Riscos:** import legado por webhook resolve campanha sem tenant; corrigir ou isolar antes de reutilizar.
    - **Gate obrigatório:** compileall, pytest `-W error`, testes tenant/RBAC/idempotência e E2E do fluxo preview→dry-run→confirm; frontend com npm ci/lint/tsc/build/a11y/responsive quando alterado.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

- [ ] 4. B4.3: processamento canônico, dedupe conservador e recovery
  - [ ] 4.1 Processar lotes, resolver identidade e gerar relatório operacional
    - **Prompt para o agente:** implemente processamento assíncrono em lotes de até 1.000 linhas, reutilizando os resolvers canônicos de Company/Person e criando apenas Lead/relações necessárias. Aplique precedência forte, revisão para ambiguidade/confidence < 0,80, provenance e row results separados em accepted/duplicate/rejected/failed; rollback deve ser por lote e recovery limitado ao permitido pelo estado/versão.
    - **Arquivos/domínios:** `services/api/src/services/import_job_service.py`, identity services existentes, consumer/worker de import, auditoria/provenance, componentes de relatório e tipos existentes.
    - **Migration:** índices parciais/aliases somente após colisões medidas; nenhuma deduplicação destrutiva ou remoção de histórico.
    - **Aceite:** mesmo arquivo repetido não duplica entidades; conflito não faz merge; no máximo um resultado terminal por linha/versão; cancelamento fecha lote corrente; falha recuperável tem no máximo três tentativas; relatório não expõe PII desnecessária.
    - **Riscos:** colisão histórica, commits parciais e divergência entre dry-run e processamento; manter normalização determinística por versão.
    - **Gate obrigatório:** compileall, pytest `-W error`, Postgres migration/schema/seed quando schema mudar, testes tenant/RBAC/idempotência/concorrência/recovery e E2E comercial sem mock de sucesso.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [ ]* 4.2 Testar dedupe conservador e recovery de import
    - **Prompt para o agente:** escreva testes com CNPJ, domínio, place_id, alias, CPF, e-mail, nomes iguais em workspaces distintos, identificadores conflitantes, ausência de sinais e falhas de lote. Verifique que decisões registram regra/confidence/source/timestamp, distinguem `UNKNOWN` de não encontrado e não alteram entidades durante revisão.
    - **Valida:** **Property 4: Dedupe conservador de Company e Person**; Requirements 2.7–2.9 e 4.1–4.5.
    - **Arquivos/domínios:** testes de identity resolver, import service e row results; fixtures tenant-safe.
    - **Migration:** testar índices/constraints novos somente contra Postgres controlado; não editar migrations.
    - **Aceite:** nenhum resultado fora do workspace, nenhum merge destrutivo e recovery reprocessa somente linhas/lotes permitidos.
    - **Gate obrigatório:** pytest `-W error`, concorrência Postgres e E2E de import com dois workspaces.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [ ] 4.3 Encerrar B4 com compatibilidade e gate vertical
    - **Prompt para o agente:** faça a revisão de integração do importador, removendo caminhos órfãos e documentando o contrato efetivamente implementado sem ampliar escopo. Garanta que upload, preview, dry-run, confirmação, consumer, relatório, cancelamento e recovery sejam um fluxo único; o XLSX legado permanece apenas como compatibilidade temporária, não como fonte operacional.
    - **Arquivos/domínios:** import services/routes, consumer, componentes web, testes e somente documentação LIVE se o comportamento tiver mudado.
    - **Migration:** confirmar cadeia Alembic e schema diff sem reescrever migrations.
    - **Aceite:** relatório distingue accepted/duplicate/rejected/failed; preview não cria lead; duas organizações permanecem isoladas; import histórico contabiliza todas as linhas.
    - **Riscos:** declarar B4 pronto por teste unitário sem Postgres/sem UI; exigir evidência de fluxo vertical.
    - **Gate obrigatório:** compileall; pytest completo `-W error`; migration upgrade duas vezes, schema verifier, seed smoke; E2E comercial de import; `npm ci`, lint, tsc, build, a11y e responsive para superfícies frontend alteradas.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

- [ ] 5. Checkpoint B4 — garantir testes e perguntar ao usuário se houver questões
  - Confirmar que somente o contrato real foi expandido, que não há migration existente editada, que o consumer falha fechado sem workspace e que B5 só começa com B4 verticalmente integrado e auditável.

- [ ] 6. B5.1: DTO, normalização e analytics server-side
  - [ ] 6.1 Implementar filtros comerciais versionados sem quebrar consumidores
    - **Prompt para o agente:** derive `CommercialFilterDTO` dos parâmetros reais de analytics e adicione de forma compatível somente dimensões suportadas: período, campanha, consultor, oferta/versão, canal, status, score bucket, outcome, attribution, busca e cursor. Normalize no servidor, derive workspace/carteira da sessão, aplique predicates SQLAlchemy com `&`/`|`, rejeite campos desconhecidos com 422 e retorne value/sample_size/availability/as_of.
    - **Arquivos/domínios:** `services/api/src/services/analytics_service.py`, routes/schemas analytics, `apps/web/src/lib/api.ts` e tipos; reutilizar endpoints existentes em vez de inventar nomes.
    - **Migration:** nenhuma inicialmente; criar índices apenas após `EXPLAIN (ANALYZE, BUFFERS)` com dataset representativo.
    - **Aceite:** filtros combinam por interseção, não são ignorados; denominador zero vira `NOT_APPLICABLE`; amostra <30 vira `INSUFFICIENT_SAMPLE`; consultant scope e tenant são aplicados antes da agregação.
    - **Riscos:** drift entre funil atual de cinco estágios e novo DTO; manter resposta versionada/aditiva e regressão do consumidor atual.
    - **Gate obrigatório:** compileall, pytest `-W error`, testes tenant/RBAC/enum/422/cursor e contrato; sem índice não medido; frontend alterado passa npm ci/lint/tsc/build/a11y/responsive.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [ ]* 6.2 Testar consistência de filtros e métricas
    - **Prompt para o agente:** transforme a Property 5 em testes de normalização, query keys/contrato, enum, limites de search/limit/cursor, sample/availability, carteira, dois workspaces, cards/tabela/export e estados empty/partial/error. Compare o universo autorizado da tabela e do export para o mesmo snapshot.
    - **Valida:** **Property 5: Consistência de filtros e analytics**; Requirements 5.1–5.7 e 5.9–5.10.
    - **Arquivos/domínios:** testes API analytics/export e contratos do frontend; fixtures sem dados inventados além do necessário.
    - **Migration:** nenhuma; benchmark e índices ficam em 6.3.
    - **Aceite:** filtro desconhecido falha explicitamente, nenhuma métrica apresenta taxa zero enganosa e export não amplia escopo.
    - **Gate obrigatório:** pytest `-W error`, Postgres para agregações relevantes e testes de contrato frontend.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

- [ ] 7. B5.2: CommercialFilterContext, relatórios e export
  - [ ] 7.1 Integrar contexto compartilhado, URL e React Query
    - **Prompt para o agente:** crie o `CommercialFilterContext` somente com o contrato retornado pela API real, mantendo estado serializável e pequeno na URL, query keys estáveis e invalidação seletiva. Conecte dashboard, relatórios, CRM e export aos mesmos filtros sem duplicar fetching; cada visão deve manter loading, empty, error e partial independentes.
    - **Arquivos/domínios:** `apps/web/src/app/(protected)/relatorios/page.tsx`, hooks/context, componentes de cards/funil/tabela/export, `apps/web/src/lib/api.ts` e tipos existentes; respeitar Base UI/shadcn atual.
    - **Migration:** nenhuma.
    - **Aceite:** alterar um filtro atualiza todas as visões; reload/back/forward restaura snapshot; não há fetch duplicado para parâmetros iguais; teclado, foco, semântica, contraste e responsividade permanecem operáveis.
    - **Riscos:** estado local legado e cache stale; não introduzir contrato frontend que a API não suporte.
    - **Gate obrigatório:** para qualquer alteração web: `npm ci`, lint, `npx tsc --noEmit`, production build, testes a11y, responsividade e smoke E2E comercial; backend relevante também passa compileall/pytest.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [ ] 7.2 Implementar export autorizado com snapshot exato
    - **Prompt para o agente:** conecte a exportação ao mesmo snapshot normalizado usado pelas visões, revalide workspace/carteira antes da leitura, aplique limite de 10.000 linhas, auditoria de actor/filtros/quantidade/resultado e resposta de limite sem exportação parcial. Preserve o XLSX de compatibilidade somente se o endpoint real exigir redaction e aviso de origem.
    - **Arquivos/domínios:** export service/routes existentes, analytics query layer, auditoria, `apps/web` export consumer.
    - **Migration:** nenhuma salvo índice comprovado; não criar warehouse ou Elasticsearch.
    - **Aceite:** tabela e export têm o mesmo universo autorizado; PII/secret não vazam; limite excedido não amplia escopo nem gera arquivo parcial.
    - **Riscos:** export síncrono bloquear transação; usar job apenas se houver contrato/infra existente e documentar sua integração.
    - **Gate obrigatório:** compileall, pytest `-W error`, testes tenant/RBAC/export e E2E comercial; frontend com npm ci/lint/tsc/build/a11y/responsive se alterado.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [ ]* 7.3 Medir performance e decidir índices por evidência
    - **Prompt para o agente:** execute benchmark em dataset de no mínimo 10.000 registros, com 5 aquecimentos e 30 execuções, separado entre agregações e detalhe/lista; registre ambiente, filtros, p50, p95, máximo e rows scanned. Só proponha migration de índice após `EXPLAIN (ANALYZE, BUFFERS)` e cardinalidade justificarem a mudança.
    - **Valida:** Requirement 5.8 e parte de 5.7.
    - **Arquivos/domínios:** scripts/verifier de benchmark, consultas analytics e migration nova apenas se aprovada pelos planos.
    - **Migration:** nunca editar existente; nova migration deve ser expand-compatible e incluir estratégia de rollback/observação.
    - **Aceite:** p95 ≤2s para métrica agregada e ≤5s para detalhe/lista, ou gate permanece vermelho com risco registrado; não carregar universo no navegador.
    - **Gate obrigatório:** Postgres controlado, schema diff, pytest de regressão e documentação da evidência; não substituir benchmark por métrica estimada.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

- [ ] 8. Checkpoint B5 — garantir filtros, export e UI sem divergência
  - Confirmar que cards, funil, tabela, comparação e export usam o mesmo snapshot, que estados parciais são independentes e que qualquer índice foi motivado por plano de consulta e benchmark.

- [ ] 9. B6: CRM operacional canônico e escala
  - [ ] 9.1 Unificar Company/People/Opportunity/Activity/Task/Outcome/Timeline
    - **Prompt para o agente:** componha a visão CRM 360 exclusivamente das fontes canônicas existentes e dos command services de Opportunity 360. Adicione apenas leitura de timeline/eventos e campos aditivos necessários, com ordenação determinística, attribution, provenance, version check e RBAC por campo. Não crie Proposal/Contract/Note/Timeline paralelos sem regra distinta, lifecycle, consumidor e UAT.
    - **Arquivos/domínios:** rotas/command services de CRM e opportunities, `services/api/src/services/opportunity_command_service.py`, modelos canônicos nos workers, componentes CRM existentes, timeline read model se necessário.
    - **Migration:** somente migration nova para evento/versão aditivo comprovado; nenhum drop ou edição de migration.
    - **Aceite:** edição concorrente não sobrescreve; cada mutação audita actor/workspace/action/version/correlation ID; timeline não mistura workspaces; snapshots são append-only.
    - **Riscos:** duplicação de estado e drift entre Company 360, Person 360 e Opportunity 360; reutilizar fontes existentes.
    - **Gate obrigatório:** compileall, pytest `-W error`, Postgres schema/seed quando aplicável, testes tenant/RBAC/idempotência/concorrência e E2E CRM comercial; frontend com npm ci/lint/tsc/build/a11y/responsive.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [ ]* 9.2 Testar idempotência de comandos, versionamento e atribuição
    - **Prompt para o agente:** escreva testes de repetição e corrida para tasks, transitions, outcomes e conversions, optimistic concurrency, audit trail, attribution única/múltipla e timeline ordenada. Reuse os testes existentes de Opportunity 360 e conversão, ampliando apenas os caminhos necessários.
    - **Valida:** **Property 3: Idempotência de tarefas e comandos comerciais**; Requirements 3.1, 3.4–3.5 e 3.11.
    - **Arquivos/domínios:** `tests/` e testes de commands/rotas existentes.
    - **Migration:** testar constraints reais contra Postgres; não criar duplicata de modelo.
    - **Aceite:** uma operação lógica e uma auditoria correspondente sob retry/concorrência; versão obsoleta não gera tarefa/outcome/evento; outcome sem evidência vira `unattributed`.
    - **Gate obrigatório:** pytest `-W error`, concorrência Postgres, tenant/RBAC e E2E comercial.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [ ] 9.3 Implementar escala operacional: cursor, bulk, saved views e estados de UI
    - **Prompt para o agente:** adicione paginação/cursor server-side, filtros, ordenação estável, limite e operações bulk com seleção explícita, preview, autorização, idempotency key e relatório accepted/duplicate/rejected/failed. Reutilize estruturas existentes para saved views/tags quando houver consumidor; não crie entidade paralela de domínio. Na UI, preserve dados válidos por visão em loading/empty/error/partial.
    - **Arquivos/domínios:** services/routes de leads/opportunities, índices hot path, componentes CRM/kanban/tabela, hooks React Query e tipos reais.
    - **Migration:** índices somente depois de benchmark; novas migrations aditivas e sem Elasticsearch neste estágio.
    - **Aceite:** navegador não carrega universo completo; bulk acima do limite falha sem efeitos; export é autorizado; fetch não duplica; a11y/keyboard/responsive são mantidos.
    - **Riscos:** N+1, mass assignment e export de PII; usar DTO allowlist e query count.
    - **Gate obrigatório:** compileall/pytest `-W error`, testes tenant/RBAC/idempotência/cursor/bulk/concorrência, benchmark Postgres e E2E; frontend npm ci/lint/tsc/build/a11y/responsive.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

- [ ] 10. Checkpoint B6 — garantir CRM sem estado paralelo
  - Confirmar que Company/Person/Lead/Opportunity/Task/Activity/Outcome/Conversion continuam canônicos, que bulk e paginação são auditáveis e que a UI preserva estados e acessibilidade sem contratos inventados.

- [ ] 11. B7: coaching, métricas observacionais e Controlled Learning
  - [ ] 11.1 Implementar métricas por bucket com baseline, amostra e disponibilidade
    - **Prompt para o agente:** implemente Precision@K e NDCG para K entre 1 e 10, além de resposta, reunião, win, receita e custo somente quando dados e denominadores existirem. Persista baseline, versão, período, segmento, numerador/denominador, amostra, disponibilidade, limitações, provenance e as-of; trate associação como observação, nunca causalidade.
    - **Arquivos/domínios:** analytics/learning services, snapshots e outcomes existentes, schemas/types e painel de coaching.
    - **Migration:** somente campos aditivos comprovadamente necessários; não alterar pesos ou registry.
    - **Aceite:** amostra mínima de 30 por segmento/versão para comparação disponível; vazio/denominador zero retorna `NOT_APPLICABLE`; insuficiente retorna `INSUFFICIENT_SAMPLE`; nenhuma proposta publica automaticamente.
    - **Riscos:** duplicação de outcome, viés de seleção e claims causais; separar score, contactability, resposta, reunião, win, receita e custo.
    - **Gate obrigatório:** compileall, pytest `-W error`, testes tenant/RBAC/attribution, Postgres schema/seed quando aplicável, E2E de painel; frontend npm ci/lint/tsc/build/a11y/responsive se alterado.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [ ]* 11.2 Testar learning observacional sem publicação silenciosa
    - **Prompt para o agente:** cubra comparação vazia/insuficiente, segmentação por oferta/canal/vertical/bucket, proposta sem publicação, tentativa sem aprovação, aprovação, publicação, rollback e isolamento de overlays/jobs entre workspaces. Compare snapshots efetivos antes/depois e valide aprovador, evidência e versão anterior.
    - **Valida:** **Property 7: Learning observacional sem publicação silenciosa**; Requirements 7.1–7.10.
    - **Arquivos/domínios:** testes `test_controlled_learning.py`, `test_learning.py` e novos testes de provider/registry/contexto quando necessários.
    - **Migration:** validar qualquer campo novo em migration nova; não promover proposta a configuração por fixture.
    - **Aceite:** score/OfferProfile/registry permanecem iguais antes da aprovação; publicação sem aprovação falha; rollback restaura snapshot exato e não contamina outro workspace.
    - **Gate obrigatório:** pytest `-W error`, Postgres real para concorrência e E2E de aprovação/rollback sem mocks de sucesso.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [ ] 11.3 Integrar feedback, attribution e UI de calibração
    - **Prompt para o agente:** conecte feedback/outcome ao workspace, lead, opportunity, oferta, canal, período, actor e attribution já existentes; exiba limitações e disponibilidade; permita revisão/aprovação explícita sem mutar score diretamente. Preserve loading/empty/error/partial e a linguagem de não causalidade.
    - **Arquivos/domínios:** rotas/services de feedback/learning, `apps/web` hooks/types/painel, audit/provenance.
    - **Migration:** nenhuma se contratos existentes bastarem; caso contrário, nova migration aditiva.
    - **Aceite:** feedback inválido/cross-tenant é rejeitado; outcome sem oportunidade vira `unattributed`; proposta é distinta da configuração efetiva; ação de publicar/rollback é RBAC e auditável.
    - **Riscos:** expor PII/feedback privado ou permitir overlay global; aplicar OrganizationContext em cada execução.
    - **Gate obrigatório:** compileall, pytest `-W error`, tenant/RBAC/idempotência/concorrência, E2E de coaching e npm ci/lint/tsc/build/a11y/responsive.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

- [ ] 12. Checkpoint B7 — garantir aprendizado somente observacional e aprovado
  - Confirmar que todas as métricas têm denominador/amostra/disponibilidade, que nenhuma alteração efetiva ocorre sem aprovação e que rollback, auditoria e isolamento de overlay foram demonstrados.

- [ ] 13. B8: Golden Path Troféus/MEJ e separação epistemológica
  - [ ] 13.1 Fechar contrato de provenance FACT/INFERENCE/HYPOTHESIS/UNKNOWN
    - **Prompt para o agente:** estenda somente os modelos/serviços existentes para persistir classificação epistemológica, fonte/evidence URL, observed_at, classified_at, regra, confidence e sinais. `FACT` exige evidência, `INFERENCE` exige regra/sinais/confidence, `HYPOTHESIS` permanece pendente e `UNKNOWN` não vira `FALSE`; toda coleta externa continua passiva.
    - **Arquivos/domínios:** event discovery, provenance/identity/scoring/offers existentes, modelos canônicos e schemas de snapshot.
    - **Migration:** campos/tabelas aditivos somente se o gap for comprovado; manter histórico e não reescrever migrations.
    - **Aceite:** entidade ambígua não é confirmada; evidência é navegável sem secret/PII indevida; hipótese não autoriza conversão/publicação/ação irreversível; lead sem site segue business scoring e não é desqualificado só por isso.
    - **Riscos:** confundir data do evento com observed/processed at e inventar evidence; registrar ausência explicitamente.
    - **Gate obrigatório:** compileall, pytest `-W error`, schema/seed quando aplicável, testes tenant/RBAC/provenance e E2E comercial passivo.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [ ]* 13.2 Testar separação epistemológica e bloqueio de ações indevidas
    - **Prompt para o agente:** crie fixtures com evento real controlado, evidência navegável, dados ausentes, inferência de score, hipótese de identidade e lead sem site. Verifique payload/timeline/UI, bloqueio de conversão/publicação dependente apenas de hipótese/unknown e ausência de sondagem, autenticação, formulário, injection ou alteração remota.
    - **Valida:** **Property 6: Separação entre FACT, INFERENCE e HYPOTHESIS**; Requirements 6.1–6.7.
    - **Arquivos/domínios:** testes de event discovery, scoring, identity, opportunity/outcome e frontend afetado.
    - **Migration:** testar schema real sem editar migration.
    - **Aceite:** exatamente uma classificação por informação; provenance e confidence não são fabricadas; outcome sem vínculo único é `unattributed`.
    - **Gate obrigatório:** pytest `-W error`, tenant/RBAC, E2E passivo com evidência controlada e checks de a11y/responsive se UI mudar.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [ ] 13.3 Integrar evento → entidade → oferta/snapshot → NBA → outcome
    - **Prompt para o agente:** conecte o evento Troféus/MEJ ao resolver conservador, Lead, LeadOpportunity, OfferProfile efetivo, snapshot, CommercialTask/NBA e outcome, preservando cada vínculo e data. Use as fontes canônicas e regras existentes; não crie um pipeline paralelo nem trate organizador/EJ/decisor ambíguo como confirmado.
    - **Arquivos/domínios:** event discovery, company/person identity, scoring, effective offer registry, opportunity/task/outcome services e componentes de revisão.
    - **Migration:** somente mudanças aditivas comprovadas para recorrência/provenance; não apagar dados.
    - **Aceite:** fluxo idempotente não duplica empresa/pessoa; revisão bloqueia ação que exige identidade confirmada; lead sem site é pontuado pelo caminho business; NBA e outcome possuem attribution/provenance.
    - **Riscos:** evento real sem evidência suficiente e decisão comercial irreversível baseada em hipótese.
    - **Gate obrigatório:** compileall, pytest `-W error`, tenant/RBAC/idempotência/concorrência, Postgres quando aplicável e E2E Golden Path sem mock de sucesso.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

- [ ] 14. Checkpoint B8 — garantir Golden Path passivo e auditável
  - Confirmar que o caminho completo é executável, que evidence/provenance e classificação epistemológica aparecem sem fabricar dados e que o resultado alimenta oportunidade/NBA/outcome sem duplicar identidade.

- [ ] 15. B9: UAT multi-workspace, WebSocket, jobs e concorrência
  - [ ] 15.1 Criar matriz UAT em PostgreSQL real para dois ou mais workspaces
    - **Prompt para o agente:** implemente o harness automatizado de UAT com workspaces, usuários e papéis representativos, cobrindo UUID/search/analytics/learning/config/secrets/provider/jobs/WebSocket/exports/import/CRM. Para cada cenário registre workspace, papel, dados, resultado e evidência; toda tentativa de leitura e mutação cross-tenant deve falhar fechado.
    - **Arquivos/domínios:** `tests/`, fixtures Postgres/E2E, helpers de auth e WebSocket existentes, runbook somente se necessário para descrever execução real.
    - **Migration:** validação da cadeia existente; nenhuma mutação de schema sem gap comprovado.
    - **Aceite:** recursos de outro workspace não revelam existência nem geram side effect; CONSULTOR respeita carteira; retries não duplicam; respostas e audit logs não vazam secrets/PII.
    - **Riscos:** fixtures compartilhadas, estado global e falsos positivos por mocks; usar Postgres real e dados controlados.
    - **Gate obrigatório:** compileall, pytest `-W error`, migrations upgrade duas vezes/schema/seed, E2E API/WS comercial e invariantes tenant/RBAC/concorrência.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [ ]* 15.2 Testar isolamento de jobs, registry, cache e ContextVar sob concorrência
    - **Prompt para o agente:** execute jobs concorrentes de workspaces distintos e verifique claim, processamento, effective offer registry, `ContextVar`, cache, cleanup, feedback, métricas e idempotência. Prove que a execução seguinte não herda estado da anterior e que job órfão não processa linhas.
    - **Valida:** Property 1, Property 2 e Property 7 do design; Requirements 8.2–8.3 e 7.8–7.10.
    - **Arquivos/domínios:** `services/api/src/jobs_consumer.py`, runtime/effective registry, provider execution metrics, testes Postgres.
    - **Migration:** nenhuma; validar schema do job criado em 1.3/2.1.
    - **Aceite:** nenhum overlay/cache/contexto cruza tenant; WebSocket fecha/falha fechado; cleanup ocorre em `finally` ou equivalente testável.
    - **Gate obrigatório:** testes concorrentes Postgres, pytest `-W error`, E2E WS/provider/jobs e evidência de cleanup.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [ ] 15.3 Executar smoke E2E das superfícies frontend afetadas
    - **Prompt para o agente:** conecte o UAT aos fluxos web de import, relatórios, CRM, coaching, Golden Path e export que realmente existirem, sem substituir a API por mocks de sucesso. Verifique loading/empty/error/partial, teclado, foco, contraste, responsividade e ausência de fetch duplicado.
    - **Arquivos/domínios:** `apps/web/src/app/(protected)/`, hooks/components afetados e testes E2E existentes.
    - **Migration:** nenhuma.
    - **Aceite:** cada fluxo afetado tem smoke reproduzível e registra tenant/papel/resultado; cross-tenant é negativo; export/import respeitam filtros e RBAC.
    - **Riscos:** chamar UAT visual de prova de backend; manter os testes API/Postgres como evidência principal.
    - **Gate obrigatório:** `npm ci`, lint, `npx tsc --noEmit`, build, a11y, responsive e E2E comercial; backend compileall/pytest/migrations também quando o HEAD contiver mudanças compartilhadas.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

- [ ] 16. Checkpoint B9 — garantir UAT negativo e concorrente
  - Confirmar que todas as provas cross-tenant falham fechadas, que jobs concorrentes limpam contexto/registry/cache e que o UAT não depende de mock de sucesso comercial.

- [ ] 17. B10: campanhas reais controladas e hardening final
  - [ ] 17.1 Executar campanha Tecnologia e campanha Engenharia com dados reais controlados
    - **Prompt para o agente:** prepare fixtures/configuração operacional para campanhas autorizadas de Tecnologia e Engenharia, usando providers permitidos, enriquecimento passivo, consentimento aplicável e outcomes reais ou ausência explícita. Registre provenance, custo, amostra, correlation ID e estados `success`, `empty`, `quota`, `disabled` e `failed` sem contar falha/empty como sucesso.
    - **Arquivos/domínios:** configurações de campanha/provider, pipeline, outreach consentido, telemetria, analytics e UAT.
    - **Migration:** somente schema já aprovado; não introduzir tabela de campanha paralela.
    - **Aceite:** pelo menos uma entrada representativa por campanha; nenhum sucesso declarado por mock; falhas são recuperáveis/classificadas; BI reproduz filtros e attribution.
    - **Riscos:** custo, PII, volume insuficiente e provider não autorizado; aplicar opt-in/quota e limite operacional.
    - **Gate obrigatório:** compileall, pytest `-W error`, E2E comercial real controlado, testes tenant/RBAC/provider/idempotência e gates frontend aplicáveis; registrar custo e amostra.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [ ] 17.2 Executar Troféus/MEJ e hardening técnico P0–P3
    - **Prompt para o agente:** execute a campanha Troféus/MEJ pelo Golden Path e audite tenant isolation, RBAC/mass assignment, enum drift, race/idempotência, upload/formula injection, SSRF, XSS, open redirect, secrets/PII em logs, quotas, timeouts, observabilidade, backup/restore, incident response e rollback. Corrija somente problemas comprovados em PRs pequenos, sem reabrir escopo de domínio.
    - **Arquivos/domínios:** caminhos críticos API/workers/web, providers, DB, logs/telemetria, runbooks e testes de segurança.
    - **Migration:** `alembic upgrade head` duas vezes, verifier, seed smoke e schema diff em Postgres controlado; migrations existentes permanecem intocadas.
    - **Aceite:** campanha completa tem provenance e outcome/unattributed; nenhum P0 permanece aberto; provider mantém cinco estados; rollback é exercitado; não há ação não-passiva.
    - **Riscos:** declarar produto pronto por métrica de vaidade, amostra pequena ou mock; registrar limites e risco residual.
    - **Gate obrigatório:** compileall; pytest completo `-W error`; migrations/schema/seed; E2E comercial sem mock de sucesso; tenant/RBAC/idempotência/concorrência; web npm ci/lint/tsc/build/a11y/responsive.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

  - [ ] 17.3 Fechar documentação LIVE, operação e abandono da planilha
    - **Prompt para o agente:** atualize somente a documentação LIVE após comportamento entregue: `docs/context.md`, architecture, business rules, runbook, status map e decisions. Anexe evidência de que 100% das linhas históricas estão accepted/duplicate/rejected/recoverable failed, que a reconciliação canônica foi concluída, que CRM executou operação representativa/export/recovery/rollback e que a planilha deixou de ser dependência operacional. Preserve snapshots históricos sem reescrever fatos.
    - **Arquivos/domínios:** docs LIVE citados, release gate, relatório de campanha e evidências CI/UAT.
    - **Migration:** validar novamente cadeia e execução; nenhuma migration de documentação.
    - **Aceite:** DoD só fica verde com todos os gates verificáveis no mesmo release; qualquer gate ausente/vermelho/mock mantém consolidação não concluída e planilha não abandonada.
    - **Riscos:** documentação declarar capability antes do código; descrever comportamento efetivamente observado e condições de operação.
    - **Gate obrigatório:** repetir compileall, pytest `-W error`, migration/schema/seed, E2E, npm ci/lint/tsc/build/a11y/responsive e revisão de evidências de performance/segurança.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

- [ ] 18. Checkpoint B10 — decisão de release baseada em evidência
  - Confirmar que três campanhas foram executadas com providers autorizados e sem mock de sucesso, que não há P0 aberto, que rollback e recovery foram exercitados e que a planilha somente é declarada abandonada se a reconciliação completa estiver comprovada.

- [ ] 19. Gate final — validar a Definition of Done no mesmo HEAD
  - [ ] 19.1 Reunir evidências e decidir o release gate
    - **Prompt para o agente:** reúna a matriz de evidências do release e marque cada item abaixo como PASS, FAIL ou NÃO EXECUTADO; nenhum item pode ser inferido pela existência de classe/tabela isolada.
    - [ ] 19.2 Tenant-first completo em rotas, services, jobs, WebSocket, providers, analytics, export, cache e migrations relevantes.
    - [ ] 19.3 RBAC/membership/carteira, allowlist de campos, import, bulk, secrets, learning, export e publicação testados.
    - [ ] 19.4 Schema Alembic com uma cabeça, migrations novas/expand-compatible, backfills verificados, índices medidos e seed idempotente.
    - [ ] 19.5 CRM canônico com lifecycle, timeline, attribution, provenance, idempotência e optimistic concurrency; sem entidades paralelas não justificadas.
    - [ ] 19.6 Import CSV/XLSX com upload seguro, preview, mapping, dry-run, job, progresso, dedupe, relatório, retry/cancelamento/recovery e idempotência.
    - [ ] 19.7 BI com FilterContext URL/React Query, agregação server-side, amostra/disponibilidade, cursor e export do mesmo snapshot.
    - [ ] 19.8 Learning com Precision@K/NDCG/outcomes observacionais, baseline/versão, aprovação manual, publicação auditada e rollback exato.
    - [ ] 19.9 Golden Path evento→evidência→entidade→contactability→fit/score/confidence→oferta/snapshot→NBA→outcome, separando FACT/INFERENCE/HYPOTHESIS/UNKNOWN.
    - [ ] 19.10 UAT multi-workspace em Postgres real, incluindo cross-tenant, jobs/registry/cache/ContextVar, WebSocket, providers e exports.
    - [ ] 19.11 Três campanhas reais controladas, consentimento aplicável, provenance/custo/amostra/correlation ID e estados de provider diferenciados.
    - [ ] 19.12 Segurança sem P0 aberto; performance com p50/p95 e plano de índice; backup/restore, incident response, observabilidade e rollback evidenciados.
    - [ ] 19.13 Gates de qualidade: compileall; pytest completo com `-W error`; migrations/seed/schema verifier; E2E comercial; `npm ci`, lint, TypeScript sem emissão, production build, a11y e responsive para mudanças web.
    - [ ] 19.14 Documentação LIVE atualizada e snapshots históricos preservados.
    - **Guardrails:** não inventar endpoints, não duplicar fontes canônicas, não editar migrations existentes e não alterar learning silenciosamente.

## Notes

- Tarefas sem `*` são obrigatórias para o plano; subtarefas marcadas com `*` são testes opcionais conforme o formato da spec, mas não dispensam os gates obrigatórios descritos nas tarefas de implementação.
- Cada PR deve ser vertical, tenant-first, revisável e integrado ao código existente; não iniciar a próxima fatia com a anterior apenas parcialmente implementada.
- A seleção de linguagem do workflow foi **Python** para implementação. A presença de TypeScript/Next.js no plano representa apenas a superfície frontend real do projeto; não há pseudocódigo de implementação a converter.
- Os nomes de endpoints do design são contratos propostos, não autorização para criá-los. Antes de qualquer mudança, consultar a API, schemas, hooks e testes reais.
- Não criar Elasticsearch neste estágio, não filtrar universo completo no navegador, não executar análise ativa de sites e não mudar pesos de score/OfferProfile/registry sem Controlled Learning aprovado.
- Tarefas de benchmark, UAT e campanhas devem produzir evidência reproduzível; execução manual sem teste automatizado não fecha o gate sozinha.
- Este documento é exclusivamente um plano. Ele não autoriza execução automática, implementação de código, alteração de migrations, alteração de `design.md`/`requirements.md` ou declaração antecipada de consolidação.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["2.1"] },
    { "id": 3, "tasks": ["2.2", "3.1"] },
    { "id": 4, "tasks": ["3.2", "3.3"] },
    { "id": 5, "tasks": ["4.1"] },
    { "id": 6, "tasks": ["4.2"] },
    { "id": 7, "tasks": ["4.3"] },
    { "id": 8, "tasks": ["6.1"] },
    { "id": 9, "tasks": ["6.2", "7.1"] },
    { "id": 10, "tasks": ["7.2"] },
    { "id": 11, "tasks": ["7.3"] },
    { "id": 12, "tasks": ["9.1"] },
    { "id": 13, "tasks": ["9.2", "9.3"] },
    { "id": 14, "tasks": ["11.1"] },
    { "id": 15, "tasks": ["11.2", "11.3"] },
    { "id": 16, "tasks": ["13.1"] },
    { "id": 17, "tasks": ["13.2", "13.3"] },
    { "id": 18, "tasks": ["15.1"] },
    { "id": 19, "tasks": ["15.2", "15.3"] },
    { "id": 20, "tasks": ["17.1"] },
    { "id": 21, "tasks": ["17.2", "17.3"] },
    { "id": 22, "tasks": ["19.1", "19.2", "19.3", "19.4", "19.5", "19.6", "19.7", "19.8", "19.9", "19.10", "19.11", "19.12", "19.13", "19.14"] }
  ]
}
```
