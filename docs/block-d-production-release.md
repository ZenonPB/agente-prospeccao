# Bloco D — UAT, Production Readiness e Campanhas Controladas

Status: **implementado tecnicamente**. Este documento separa explicitamente prova técnica de evidência comercial real.

## D1 — Multi-workspace UAT e segurança adversarial

O gate `tests/test_block_d_uat_production_campaigns.py` cria dois workspaces simultâneos — AlphaMec e `Vendas Samuel e Zenon` — com o mesmo usuário em papéis diferentes e dados comerciais propositalmente semelhantes. O teste usa UUIDs conhecidos do outro tenant e exige falha fechada para leitura de campanha/funil fora do workspace.

Ele é executado junto dos gates anteriores de import, bulk, Opportunity 360, Company/Person 360, Sales Operating System, Event Intelligence e Controlled Learning. Assim, o UAT final não substitui as provas anteriores: ele fecha o cenário de alternância multi-workspace sobre o conjunto já protegido.

Invariantes de release:

- `organization_id` é derivado do contexto autenticado, nunca confiado de payload;
- Campaign/Lead/Opportunity/Outcome continuam canônicos e tenant-scoped;
- o mesmo usuário pode pertencer a dois workspaces sem compartilhar coorte, receita, OfferProfile efetivo ou resultados;
- chaves novas de cache devem usar `tenant_cache_key()` e obrigatoriamente incluem `organization_id`;
- segredo/provider/quota permanecem por workspace;
- cross-tenant retorna ausência/erro antes de produzir efeito.

## D2 — Production readiness

### Providers e falhas externas

`services/workers/src/services/production_resilience.py` padroniza:

- retry limitado;
- backoff exponencial com jitter e teto;
- respeito a `Retry-After` limitado pelo teto operacional;
- distinção entre status transitório e erro permanente;
- circuit breaker explícito;
- redaction de campos sensíveis;
- cache key tenant-first.

Os providers existentes continuam exigindo opt-in/cota e registrando métricas de execução. Nenhuma configuração de provider é habilitada apenas porque existe uma API key.

### Backup e restore

Os scripts `scripts/backup_postgres.sh` e `scripts/restore_postgres.sh` usam formato custom do PostgreSQL, `--no-owner`, `--no-acl`, `umask 077` e validação com `pg_restore --list`. A CI cria um dump do banco migrado, restaura em outro database e consulta `alembic_version` no banco restaurado.

Isto prova o procedimento em PostgreSQL efêmero de CI. Não substitui política externa de retenção, criptografia at-rest nem teste periódico do backup real de produção.

### Readiness verificável

`scripts/verify_block_d_readiness.py` falha fechado se detectar:

- registros órfãos de `organization_id` em tabelas canônicas disponíveis;
- mais de uma versão ativa de OfferProfile no mesmo workspace/oferta;
- drift de cabeça Alembic.

O serviço interno do Bloco D também distingue DB pronta, integridade tenant, provider opt-in e autorização humana para live outreach. Health verde sozinho não é tratado como prova de worker/provider/campanha.

## D3 — Campanhas controladas e calibração final

A matriz de release cobre:

1. `landing_page` — landing pages;
2. `web_systems_erp` — sistemas sob medida;
3. `mechanical_engineering` — engenharia mecânica;
4. `trophies_sports` — troféus esportivos;
5. `trophies_mej` — troféus para eventos/MEJ.

`CampaignReleaseRequest` possui três modos:

- `DRY_RUN`: preparação sem envio externo;
- `REHEARSAL`: ensaio integral, ainda sem envio externo;
- `LIVE_AUTHORIZED`: somente válido com provider opt-in, gestor identificado, justificativa explícita, teto de custo e limite de contatos.

A medição usa as entidades canônicas e retorna leads, oportunidades, respostas, reuniões, ganhos, receita e attribution rate. `calibration_ready` só fica verdadeiro com amostra mínima, wins suficientes e pelo menos 80% dos outcomes atribuídos à oportunidade correta. O resultado é **observacional**, não causal.

Nenhuma campanha altera pesos automaticamente. Quando a amostra real se torna suficiente, o Bloco C continua responsável por replay, comparação, aprovação humana, publicação e rollback.

## O que a CI pode e não pode provar

A CI executa um **production rehearsal** em PostgreSQL real, sem chamar pessoas ou providers externos. Isso prova isolamento, contratos, guardrails, mensuração, backup/restore e integração do learning. Não seria correto chamar dados sintéticos de CI de conversão comercial real.

Uma campanha externa só deve ser executada quando houver simultaneamente:

- workspace correto;
- público/contatos revisados;
- base legal/consentimento aplicável;
- provider explicitamente habilitado para aquele workspace;
- quota disponível;
- `LIVE_AUTHORIZED` por gestor;
- teto de custo e tamanho da amostra;
- correlation/provenance/outcome attribution ativos.

## Gate de merge do Bloco D

O PR só pode entrar em `main` quando, no mesmo HEAD:

- Web lint + TypeScript + production build estiverem verdes;
- `compileall` e suíte Python completa com `-W error` estiverem verdes;
- Alembic upgrade + segundo upgrade idempotente + schema verifiers + seed estiverem verdes;
- backup/restore rehearsal estiver verde;
- E2E PostgreSQL dos Blocos A/B/C permanecer verde;
- gate D1/D2/D3 estiver verde;
- CI pós-merge da `main` repetir os mesmos gates com sucesso.
