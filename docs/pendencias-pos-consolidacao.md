# Pendências pós-consolidação

> **LIVE · atualizado em 2026-09-13.** Este arquivo contém apenas trabalho
> residual. Itens já entregues saíram daqui e estão no `00-status-mapa.md`.

## Prioridade 0 — bloquear RC se falhar

### P0.1 OfferProfile efetivo por workspace

**Estado:** em validação no PR #172.

Critério de saída:
- pipeline completo usa versão ativa do workspace;
- nenhum fallback global quando existe overlay válido;
- jobs concorrentes de A/B não contaminam registry;
- criação/edição de campanha aceita keys publicadas no workspace;
- CI e UAT cross-tenant verdes.

### P0.2 CRM mínimo para abandonar planilha

**Estado:** parcial.

Já existe Kanban, owner/status, valor/previsão, atividades, tarefas, outcomes e
visões 360 read-only. Falta:
- Opportunity 360 editável sobre as fontes canônicas;
- busca/filtros operacionais consolidados;
- ações em massa necessárias no UAT;
- importação histórica segura;
- exportação/auditoria final.

### P0.3 Importador histórico AlphaMec

**Estado:** pendente.

Obrigatório:
`upload → preview → mapping → validation → dedupe → import → report`.

Gates:
- dry-run sem escrita;
- organization_id obrigatório;
- dedupe determinístico;
- relatório por linha;
- transação/estratégia explícita para erro parcial;
- idempotência/reprocessamento seguro;
- provenance da planilha/importação.

### P0.4 UAT multi-workspace

**Estado:** pendente como sessão formal do RC.

Cobrir UUID conhecido, carteira, providers/secrets/quotas, OfferProfile
publicado, CRM 360, importação, analytics e jobs concorrentes.

## Prioridade 1 — necessária para operação confortável

### P1.1 Filter Context compartilhado

Um contrato único para período, owner, campanha, oferta/versão, estágio,
segmento, região, provider e workspace. Backend compõe filtros; frontend não
filtra o universo inteiro em memória.

### P1.2 BI interativo final

Conectar Filter Context a pipeline, qualidade de lead, feedback, outcomes,
provider performance, forecast e atribuição. Todo card/gráfico deve explicar o
período/coorte usado.

### P1.3 Coaching comercial

Transformar sinais existentes em filas acionáveis: sem próxima ação, tarefa
vencida, oportunidade parada, estágio sem avanço, feedback negativo recorrente,
risco de perda e gaps de contato. Recomendação deve ser explicável.

### P1.4 Busca global e navegação CRM

Encontrar Company, Person e Opportunity em uma busca; navegação cruzada entre
360s; suporte a filtros/tags conforme necessidade real.

### P1.5 Notas/propostas/contratos

Não criar entidades por antecipação. UAT decide:
- se `Lead.notes` atende ou se Note append-only é necessária;
- se Proposal precisa versão/arquivo/aprovação;
- se Contract precisa ciclo de vida/assinatura/documentos.

## Prioridade 2 — qualidade/calibração

### P2.1 Consolidação de loops de learning

Evitar dois motores concorrentes entre `CampaignScoringTemplate` e
`OfferProfile`. ICP/sinais/pesos/thresholds/providers/buyer/timing devem convergir
para OfferProfile versionado. Template só permanece onde houver responsabilidade
operacional distinta e documentada.

### P2.2 Calibração estatística

Após amostra real:
- Precision@K por oferta/versão;
- taxa de utilidade;
- conversão e ticket;
- cobertura/custo por provider;
- calibration/threshold por coorte;
- intervalo/incerteza e amostra mínima.

Mudança de produção continua exigindo aprovação humana.

### P2.3 Golden Path troféus/eventos/MEJ

Provar o caso prioritário da AlphaMec de ponta a ponta sem hardcode do núcleo:
evento/organizador → conta → decisor → oferta trophies → ação → outcome → BI.

## Prioridade 3 — hardening final

- campanha real autorizada;
- medição de custo/latência/coverage/precision/routability/bounce;
- revisar índices/query plans de telas principais;
- rate limits e timeouts externos;
- observabilidade de erros por estágio;
- backup/restore e runbook operacional;
- revisão de segurança/LGPD e retention;
- acessibilidade e performance do frontend em volume real.

## Fora do RC salvo evidência de UAT

- recriar integralmente um banco proprietário estilo Apollo;
- automação irrestrita de LinkedIn;
- auto-learning sem aprovação;
- entidades/feature sets especulativos sem caso AlphaMec;
- otimizações prematuras sem perfil/medição.

## Regra de triagem

Todo achado novo recebe uma classe:

- `BLOCKS_ALPHAMEC`: impede operação segura/correta;
- `IMPORTANT_ALPHAMEC`: relevante para uso real, mas não bloqueia o primeiro RC;
- `DEFER_TO_V2`: evolução sem evidência imediata.

Não reabrir itens encerrados só porque há uma versão mais sofisticada possível.
