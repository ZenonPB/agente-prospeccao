# Data Engine Brasil

> Documento LIVE da evolução do data network brasileiro. O objetivo é aumentar
> cobertura e qualidade sem tornar provider pago requisito do fluxo principal e
> sem interromper a operação existente.

## Objetivo

A partir de uma Vertente e uma região, produzir oportunidades brasileiras
priorizadas com evidências, provenance, dados empresariais e contato quando
disponível, conhecendo o custo de obtenção de cada camada de informação.

O rollout é incremental. Cada PR deve deixar `main` utilizável e entregável.

## Auditoria da base existente

A fundação não cria um segundo sistema de providers. O projeto já possui:

| Responsabilidade | Fonte canônica | Direção |
|---|---|---|
| planejamento custo/qualidade | `prospecting/provider_planner.py` | estender |
| federação por capability | `prospecting/provider_federation.py` | estender |
| discovery específico | `discovery_executor.py` + providers | adaptar gradualmente |
| people discovery | `people_provider_registry.py` | adaptar gradualmente |
| intent | `intent_provider_registry.py` | manter especializado |
| quota diária por organização | `quota_service.py` + `ProviderUsage` | reutilizar |
| telemetria histórica | `ProviderExecutionMetric` | reutilizar |
| secrets BYOK | `OrganizationSecret` | reutilizar |
| entidade comercial | `Company` | manter canônica |
| estratégia da oferta | OfferProfile efetivo / Vertente | manter canônica |

`FederatedProviderRegistry` é o seam comum para novas fontes de discovery e
enrichment. Registries especializados existentes não são removidos numa
migração big-bang.

## Invariantes

1. O caminho existente permanece funcional durante toda a evolução.
2. `UNKNOWN != FALSE`: ausência/falha de enrichment não vira evidência negativa.
3. Provider externo opcional falha sem derrubar uma oportunidade válida.
4. Provider pago é opt-in. Novos fluxos usam `ProviderAccessPolicy` e começam
   com `paid_providers_enabled=False` e orçamento zero.
5. Cota esgotada, provider desativado, orçamento bloqueado, resultado vazio e
   falha são estados diferentes e observáveis.
6. Dados externos carregam provenance/confidence/timestamp quando disponíveis.
7. Configuração, quota, secret, usage e telemetria sensíveis permanecem
   organization-scoped.
8. Registry empresarial é universo de descoberta; um registro do registry não
   é automaticamente uma `Company` do CRM.
9. Nenhuma migration destrutiva durante rollout. Usar expand → migrate → contract.
10. Novas dimensões comerciais entram em shadow mode antes de substituir
    ranking existente.
11. Toda capability nova deve possuir caminho gratuito funcional; provider pago
    melhora cobertura/qualidade, não é requisito arquitetural.
12. Custos externos precisam ser autorizados antes do I/O, não contabilizados
    apenas depois da chamada.

## Política FREE → PAID

Novos fluxos passam explicitamente uma `ProviderAccessPolicy` à federação.
O default é seguro: somente providers de custo zero são elegíveis. Uma chamada
com custo positivo só entra no plano quando `paid_providers_enabled=True` e há
orçamento suficiente. O limite é também verificado cumulativamente durante a
waterfall.

`max_cost` tem semântica dupla e intencional: é o teto por chamada (provider
com `cost_per_request` maior é inelegível em `allows` e no planner, com
`budget_exceeded` registrado em vez de silêncio) e o teto cumulativo da
waterfall (a soma dos custos esperados das chamadas iniciadas não ultrapassa
o teto — o custo é reservado antes do I/O, inclusive quando a tentativa
falha, como provisão conservadora).
Quando a política e o `max_cost` legado do `collect` são fornecidos juntos, o
valor mais restritivo vence.

Custo aqui é estimativa de planejamento, não fatura: `cost_spent` soma os
custos *esperados* das chamadas executadas. O sistema nunca apresenta essa
estimativa como gasto financeiro auditável (`expected != billed`). `float` é
aceitável nesta fase exatamente por ser estimativa; valores não finitos
(`NaN`/`inf`) são rejeitados na construção porque contornariam o budget —
comparações com `NaN` são sempre falsas e liberariam I/O pago.

Consumidores legados que ainda não fornecem a política mantêm o comportamento
anterior. Isso é deliberado para rollout backward-compatible; cada capability
será migrada e testada isoladamente.

## Status agregado e UNKNOWN != FALSE

Cada tentativa carrega `provider`, `status`, `result_count`, `cost` e `error`
quando aplicável. O status agregado segue esta precedência com itens vazios:

1. alguma tentativa falhou (ou retornou estado desconhecido) → `failed`;
2. alguma fonte foi bloqueada sem ser consultada (`provider_disabled`,
   `quota_exhausted`, `paid_provider_disabled`, `budget_exceeded`) → `disabled`;
3. todas as fontes consultadas responderam sem achados → `empty`;
4. nenhum provider registrado → `disabled`.

`empty` exige, portanto, todas as fontes consultadas sem achados: um `empty`
ao lado de um bloqueio agrega `disabled`, nunca `empty`. Ausência de consulta
não vira ausência de dado. Uma exceção do provider nunca pode registrar
`success` ou `empty` — esses estados implicam afirmação sobre dados que a
chamada não produziu; sinais informativos (`timeout`, `rate_limited`,
`quota_exhausted`) passam para observabilidade e estados desconhecidos viram
`failed` (fail-closed).

## Separação de responsabilidades

- **política de autorização** (`ProviderAccessPolicy`): paid opt-in + teto de
  custo por execução. Domínio puro, sem I/O, sem organização;
- **quota** (`QuotaService` + `ProviderUsage`): contador diário persistente por
  organização. O chamador traduz `QuotaService.remaining` em
  `ProviderPolicy.quota_remaining` ao montar o plano; a foto pode defasar sob
  concorrência — o enforcement concorrente real continua no `consume`;
- **budget financeiro** (`max_cost`): teto de estimativa por execução
  federada, verificado antes do plano e cumulativamente na waterfall;
- **telemetria** (`ProviderExecutionMetric`): histórico org-scoped para
  investigação (planejado/bloqueado/executado, custo, resultados, falha,
  quota, budget). A federação expõe `plan` + `attempts` por chamada para
  alimentar esse registro; a persistência por organização acontece no caller.

## Limites desta fase

- A política protege o `FederatedProviderRegistry`. Chamadas diretas a
  providers (`enrichment_orchestrator`, `continuous_intelligence_service`,
  registries de people/intent) não passam por ela — a migração é por
  capability, sem big-bang.
- Ainda não há consumidor de produção passando `access_policy`; o contrato
  está pronto e travado por testes para os próximos fluxos.
- Multi-tenancy não se aplica ao núcleo (sem `organization_id`, sem I/O):
  quota, secret, usage e métrica permanecem org-scoped nas bordas existentes.

## Capabilities alvo

- `company_registry`: universo empresarial estruturado;
- `company_discovery`: geração de candidatos;
- `web_intelligence`: evidência pública/passiva;
- `people_discovery`: identificação de pessoas relevantes;
- `contact_enrichment`: obtenção de meios de contato;
- `contact_verification`: validação de contato;
- `llm_reasoning`: interpretação não determinística quando necessária.

Interfaces abstratas só devem ser adicionadas quando houver implementação ou
consumidor real. Capability é contrato; não justificativa para código morto.

## Rollout

### Fundação

Consolidar política de acesso/custo sobre planner/federação existentes, manter
compatibilidade e tornar bloqueios observáveis.

### Brazil Company Registry ✅ implementado (Fase 1B)

Universo empresarial brasileiro pesquisável, separado do CRM. Detalhes na
seção `Brazil Company Registry (Fase 1B)` abaixo.

### Discovery Brasil + Public Web Intelligence — CODE COMPLETE / OPERATIONAL VALIDATION PENDING (Fases 1C + 1D)

Código integrado à `main`, opt-in e backward-compatible. Snapshot real da
Receita em escala, benchmark de CNAE secundário em escala real e piloto
controlado AlphaMec continuam gates operacionais antes de promover o novo
caminho como default.

### Commercial Dimensions — shadow (Fase 1E)

Calcular aderência, momento, contatabilidade e confiança dos dados em paralelo
ao score existente, derivando prioridade comercial experimental. Ausência de
contato não reduz aderência e `UNKNOWN` não vira zero. O ranking novo só pode
virar principal após benchmark e campanhas reais.

### Contact waterfall

Preferir banco interno/site/web público antes de consumir quota externa. Hunter
e futuros providers são fallbacks plugáveis e sujeitos à política de custo.

### Piloto

Validar pelo menos Engenharia/Troféus na AlphaMec e Landing Pages em operação
individual. Medir candidatos, oportunidades trabalháveis, contatos válidos,
respostas, reuniões, receita atribuída e custo externo.

## Brazil Company Registry (Fase 1B)

### Fonte

Dados públicos do CNPJ (Receita Federal, catálogo dados.gov.br, snapshots
mensais). Layout oficial: "NOVOLAYOUTDOSDADOSABERTOSDOCNPJ" (gov.br).
Físico: `;` como separador, aspas, sem cabeçalho, encoding por snapshot
(historicamente ISO-8859-1 — configurável em `REGISTRY_ENCODING`, confirmar
por snapshot). Tabelas ingeridas: `ESTABELECIMENTOS` (30 colunas, unidade do
Registry), `EMPRESAS` (7 colunas, razão/porte/capital por `cnpj_basico`),
`CNAE` (referência). `SOCIOS`/`SIMPLES` e demais domínios ficam de fora:
sem QSA nesta fase (minimização; CPFs vêm mascarados da origem).

Restrição de acesso encontrada: o host legado de bulk
(`arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj`) devolve 404
desde a migração para o SERPRO+, cujo acesso exige login interativo — o
operador baixa os ZIPs mensais e o CLI ingere os arquivos extraídos. Volume
de referência: ~4,7 GB compactados / ~17 GB brutos em 2021 (maior em 2026).

### Manifesto do snapshot

Todo snapshot real deve ser acompanhado de um `manifest.json`
(`services/workers/src/services/registry/manifest.py`): mês, layout,
encoding, origem (URL efetivamente usada + data de acesso) e, por arquivo,
tamanho e SHA-256 observados. Origem oficial exige host conhecido
(`arquivos.receitafederal.gov.br`, `gov.br`, `dados.gov.br`); espelho de
terceiros só com `origin_kind` explícito — nunca autoridade silenciosa.
O importer valida mês/encoding/tamanho/hash contra o manifesto, registra
`layout_version` no ledger e falha fechado em divergência
(`--manifest` no CLI `import_registry`).

### Download robusto (opt-in)

O CLI `download_registry` baixa os arquivos do manifesto com streaming,
retomada por Range, retry com backoff, SHA-256 contínuo e rename atômico;
destino com SHA igual é reaproveitado sem rede. Retomada valida o
`Content-Range` de forma estrita: `/total` já é o total (nunca somar o
`.part`), start precisa ser igual ao pedido, end < total conhecido,
`Content-Length` precisa bater com o range, e o total anunciado precisa
bater com o manifesto antes de baixar — qualquer divergência falha fechado
sem publicar parcial. Confiança restrita: https
obrigatório, host limitado ao da origem declarada, IP literal e todos os
IPs resolvidos precisam ser públicos, redirects revalidados por hop — sem
exceção genérica de rede privada. `--write-manifest` grava o manifesto com
bytes/hashes observados, pronto para `import_registry --manifest`.

### Escopo e ativação

Arquivos oficiais são nacionais; o importer aceita escopo
(`--uf/--municipio-cod/--cnae/--situacao`, mesma semântica de CNAE da
busca) e materializa só o recorte — linhas fora do escopo avançam o
checkpoint sem tocar as tabelas. O recorte fica registrado em
`registry_snapshots.scope` (e no manifesto, quando informado) e é exposto
no health: snapshot filtrado nunca se apresenta como nacional.

Provenance é separada de visibilidade. `source_snapshot` registra o snapshot
da última MUDANÇA de conteúdo (linhas idênticas não são reescritas na
ativação); quem decide o universo visível é o membership versionado
(`registry_snapshot_members`, gravado por observação) + o ponteiro ACTIVE
(`registry_snapshots.is_active`, único por source via índice parcial).
COMPLETED = carga válida e elegível, ainda invisível. ACTIVE = universo
servido pela descoberta padrão. A busca default enxerga o ACTIVE; mês
explícito exige snapshot COMPLETED/ACTIVE e falha fechado caso contrário
(sem fallback silencioso).

O importer escreve em staging (`registry_staging_*`), nunca no canônico:
linhas de snapshot RUNNING/FAILED nunca vazam para descoberta e o ACTIVE
anterior segue servindo integralmente (conjunto e conteúdo) até a ativação
bem-sucedida. A ativação (`activate_snapshot`, ou `--activate` no CLI
`import_registry`) aplica staging → canônico + membership + flip em
transação única — falha no meio reverte tudo. Membership é gravado por
observação (linhas inalteradas continuam pertencendo ao snapshot novo) e
preservado após ativações seguintes, então `search(snapshot=A)` reproduz o
universo histórico dentro da retenção. Backfill reconstrói membership só
para o COMPLETED mais recente por source; COMPLETEDs antigos sem
membership não são reproduzíveis (limitação documentada, não dado
fabricado). Limite conhecido: atualizações mensais completas ainda não
fazem tombstoning explícito de linhas ausentes no mês novo além da ausência
natural no membership (escopo de hardening nacional).

O smoke do piloto (`run_pilot_smoke`) segue contrato A: o `snapshot_month`
solicitado controla efetivamente a query (sem fallback silencioso para o
ACTIVE) e o relatório registra `requested_snapshot`/`resolved_snapshot`.
Mês inexistente, RUNNING ou FAILED falha fechado.

"Empresas disponíveis" (saúde da base, admin e métricas) = membership do
snapshot ACTIVE — a mesma regra da busca, sem duplicação. A saúde distingue
última tentativa, último COMPLETED, ACTIVE servido e última ativação:
ACTIVE servindo com tentativa posterior FAILED é `degraded` (operacional com
atualização falha), nunca erro total; sem ACTIVE é `unknown`/`empty`, nunca
contagem inventada.

Desde jul/2026 a Receita emite CNPJs alfanuméricos (ex. `00.000.000/E08G-12`).
O Registry valida 14 posições com DV oficial único (Q&A RFB + manual SERPRO:
valor = ASCII − 48, mod 11, mesmos pesos; o numérico legado é caso particular
do mesmo cálculo) e o schema usa texto, não inteiro.

### RegistryCandidate != Company

Uma linha do universo empresarial NÃO pertence ao CRM. Tabelas `registry_*`
são globais (sem `organization_id`); ingestão e busca nunca criam
`Company`/`Person`/`Lead`/`LeadOpportunity` (travado por teste). A promoção
futura será explícita, em camada própria.

### Schema (migration `c1d2e3f4a5b6`)

- `registry_snapshots`: ledger do snapshot (origem, mês, status, contadores
  processed/inserted/updated/unchanged/rejected/failed da execução);
- `registry_import_files`: ledger por arquivo + checkpoint (`processed_lines`)
  para resume; skip rápido quando concluído e com mesmo tamanho;
- `registry_companies`: 1 linha por estabelecimento, PK `cnpj`; sem e-mail,
  telefones ou fax (minimização); `content_hash` distingue updated/unchanged;
  `imported_at` é importação, não observação (`observed_at` não existe na
  fonte — documentado no candidato);
- `registry_company_cnaes`: secundários normalizados (FK, PK composta);
- `registry_snapshot_members`: membership versionado `(snapshot_id, cnpj)`;
- `registry_staging_companies` / `registry_staging_company_cnaes`: staging
  invisível da importação em curso (limpo na ativação);
- `registry_snapshots.is_active`: ponteiro do snapshot servido (único por
  source);
- `registry_cnaes`: domínio CNAE (labels com upsert real por reimport).
  Município: só código (sem tabela de labels — linhas de referência não
  trazem UF; fica para a 1C).

Índices (todos validados com EXPLAIN ANALYZE, §benchmark): PK por CNPJ;
`cnpj_basico`; covering `(cnae_principal, uf, cnpj)`; covering
`(uf, municipio_cod, situacao, cnpj)`; assoc `(cnae, cnpj)`. Sem GIN/array:
`EXISTS` na assoc (0,19 ms) venceu GIN (28 ms) no spike.

### Ingestão (`services/registry/importer.py` + CLI `import_registry`)

Streaming em chunks de 5000 linhas: parse → temp table → staging → checkpoint
commitado. Idempotente por chave natural. Identidade do arquivo é SHA-256 em
streaming (tamanho sozinho não decide): concluído + digest igual pula;
tamanhos iguais com bytes diferentes reprocessam. `content_hash` inclui
secundários ordenados e distingue updated/unchanged (comparação só-leitura
contra o canônico; o canônico só muda na ativação).
Arquivos são aplicados na ordem canônica (estabelecimentos → empresas →
CNAE) independente da ordem do CLI. Empresas enriquecem as linhas do
staging do próprio snapshot via merge por `cnpj_basico` (só quando
diferentes — `IS DISTINCT FROM`); bases fora do staging/escopo não são
tocadas. Labels CNAE fazem upsert real (referência global, sem semântica de
visibilidade). `snapshot_month` exige `AAAA-MM`; cursor de busca exige 14
alnum. Linha ruim conta `rejected` sem abortar; arquivo inacessível/
corrompido falha fechado com ledger. Concorrência no mesmo snapshot é
segura (PK + retry de criação); totais valem por execução.

Operação local (CWD `services/workers`):
`python -m src.scripts.import_registry --snapshot-month 2026-08
--estabelecimentos <arquivo> [--empresas ...] [--cnaes ...] [--activate]`.
Sem `--activate`, o snapshot termina COMPLETED porém invisível; a descoberta
padrão continua servindo o ACTIVE anterior até a ativação explícita.
Baixe os ZIPs mensais, extraia para `dados-registry/` (gitignored) e aponte
o CLI para os arquivos extraídos.

### Busca (`services/registry/search.py`)

Filtros composáveis: CNPJ exato, CNAEs (principal ou secundários), UF,
município, situação, matriz/filial, porte. Paginação keyset por CNPJ
(`cursor` + `limit` 1..100), ordenação determinística, no máximo 3 queries
(página + secundários + labels — sem N+1). Ponte 1A: `RegistryDiscoveryProvider`
(capability `company_registry`, custo zero) executa sob policy free-only;
não é registrado em nenhum pipeline produtivo.

### Benchmark (spike, 500 mil linhas fiéis ao layout, PG 16 local)

- parse: ~43 mil linhas/s (streaming obrigatório — materializar deu 942 MB);
- COPY: ~266 mil linhas/s; upsert isolado (update-path): ~5,1 mil linhas/s;
- importer ponta a ponta (parse+merge+checkpoint, inserts): ~2,6 mil linhas/s
  em chunks de 5000; hash-verify de 125 MB em ~0,1 s (~1 GB/s);
- projeção: primeira carga de ~60 M em ~6,4 h (job mensal offline, resumível);
  reimport mensal pula arquivos iguais e só reescreve o que mudou (hash);
- consultas: CNPJ exato 0,11 ms; UF+município+situação 0,13 ms;
  CNAE+UF 0,10 ms; CNAE (principal|secundário)+geografia 0,19 ms —
  todas Index (Only) Scan, sem seq scan nos caminhos quentes.

### Limites da 1B (histórico)

A 1B terminou sem labels de município/natureza/motivo, busca textual,
promoção automática para `Company`, Places/web/people/scores. As integrações
de discovery e web que pertenciam à 1C+1D já estão code complete; os limites
operacionais atuais ficam registrados abaixo.

### Integração 1C + 1D — CODE COMPLETE / OPERATIONAL VALIDATION PENDING

Estado integrado à `main` (sem migração — zero migrations):

- runtime produtivo preservado: OfferProfile → plano →
  `DiscoveryProviderRegistry` → `DiscoveryExecutor`; federation segue seam
  futuro e `RegistryDiscoveryProvider` continua fora do pipeline produtivo;
- conceito público continua `cnae_discovery` (sem provider novo): com
  `REGISTRY_DISCOVERY_ENABLED=True`, `RegistryCnaeDiscoveryAdapter`
  vira a implementação primária e o `CnaeDiscoveryService` legado vira
  fallback automático em falha; default (`False`) mantém o comportamento
  anterior;
- CNAE tem semântica explícita e fail-closed: divisão/grupo/classe/prefixos
  suportados viram ranges ancorados; subclasse completa de 7 dígitos vira
  exato; entrada inválida não dispara varredura ampla;
- gate anti-varredura: sem CNAE válido o Registry não é consultado; UF(s),
  situação e demais filtros suportados são aplicados no PostgreSQL e
  `target_candidates` vira `LIMIT`, sem materializar o universo em Python;
- RegistryCandidate continua separado do CRM; promoção reutiliza a fronteira
  de entity resolution existente, sem criar uma segunda entidade;
- shadow barato (`REGISTRY_SHADOW_MODE=True`) compara candidatos sem repetir
  enrichment caro e usa `ProviderExecutionMetric`, sem nova tabela;
- 1D reutiliza `SafePublicWebClient` + `web_facts` + `web_intelligence`:
  allowlist http/https, DNS resolve-all, redirects revalidados, timeouts,
  streaming limitado, Content-Type allowlist e extração determinística FACT;
  falha permanece `UNKNOWN`, nunca `website_absent`; provenance e
  `observed_at` são preservados;
- consumidores web legados ainda não foram migrados em big-bang; a
  consolidação continua gradual e behavior-preserving;
- kill-switches: `REGISTRY_DISCOVERY_ENABLED`, `REGISTRY_SHADOW_MODE`,
  `PUBLIC_WEB_ENABLED`, `PUBLIC_WEB_MAX_TARGETS`,
  `PUBLIC_WEB_MAX_CONCURRENCY`.

Validação de código já concluída: testes Registry/search/prefix/provider/
ingestion/tenant em PostgreSQL real, migrations idempotentes, schema verifier,
backup/restore e benchmark sintético de 30 mil empresas. O índice secundário
continua `ix_registry_cnaes_cnae (cnae, cnpj)`.

Validação operacional pendente: snapshot real atual da Receita em escala,
benchmark com milhões de associações CNAE secundárias e piloto AlphaMec. O
risco residual de TOCTOU resolve→connect do cliente HTTP permanece documentado.
A falha de concorrência do Historical Importer registrada separadamente é
pré-existente e não pertence ao escopo da 1C+1D.

Como habilitar/desabilitar/testar (runbook):

1. `REGISTRY_DISCOVERY_ENABLED=True` (+ `REGISTRY_SHADOW_MODE=True` para
   comparar sem alterar o resultado) e `PUBLIC_WEB_ENABLED=True` quando a
   oferta declarar `public_web_facts` nos enrichment steps;
2. desligar = voltar flags a `False` (sem rollback de banco);
3. testes: `pytest tests/test_registry_cnae_matching.py
   tests/test_registry_targeting.py tests/test_registry_discovery_adapter.py
   tests/test_registry_discovery_boundary.py
   tests/test_registry_pipeline_wiring.py tests/test_safe_web_client.py
   tests/test_safe_web_client_fetch.py tests/test_web_facts.py
   tests/test_web_intelligence.py tests/test_web_intelligence_orchestrator.py -q`;
   com PG real: `E2E_DATABASE_URL=... pytest tests/test_registry_prefix_search.py
   tests/test_registry_search.py tests/test_registry_provider.py -q`;
4. piloto controlado (sem outreach, sem paid provider): Vertente Projeto
   Mecânico + SP + CNAEs 25/28/33 → Registry → shortlist (`target_candidates`)
   → web intelligence limitada; conferir universo, prefixo, falsos positivos,
   nº com site, FACTs úteis e HTTP evitados; sem e-mail/WhatsApp/LinkedIn.

## Commercial Dimensions (Fase 1E — shadow)

A 1E reutiliza o Opportunity Vector, scoring/prescoring e evidências existentes;
não cria motor paralelo, provider, tabela ou migration. O contrato fica em
`services/prospecting/commercial_dimensions.py` e é versionado como
`commercial-dimensions-shadow-v1`.

Dimensões:

- **Aderência**: `icp_fit`, `commercial_fit` e `buying_power`;
- **Momento**: `intent`, `timing` e `need`;
- **Contatabilidade**: `reachability` e sinais legados equivalentes;
- **Confiança dos dados**: confiança explícita das evidências quando existe,
  combinada com `coverage` do Opportunity Vector como medida de completude.

`decision_maker_accessibility` continua declarado como fonte de Contatabilidade,
mas hoje não existe no Opportunity Vector: o valor nasce aninhado no resultado
do pipeline de decisor e não é projetado no vetor. Como a renormalização ignora
chaves ausentes, a dimensão segue medida por `reachability` e `contactability` —
o trecho não é zero, é ausente. Enquanto isso não for projetado explicitamente,
não trate essa fonte como observada.

A **Prioridade Comercial** shadow dá peso dominante a Aderência e Momento;
Contatabilidade orienta a próxima ação e não contamina Aderência. Dimensões
UNKNOWN não recebem zero: pesos conhecidos são renormalizados e, sem
Aderência conhecida, a prioridade permanece UNKNOWN.

Rollout: `COMMERCIAL_DIMENSIONS_SHADOW_ENABLED=False` por default. Quando
habilitado, `DataIntelligenceService` calcula o diagnóstico e, em recomputes
persistidos, grava somente `score_vector.commercial_dimensions`. Não altera
`overall`, `qualification_score`, prioridade legada, ordenação, promoção ou
funil. A promoção da fórmula para ranking produtivo exige benchmark shadow e
campanhas reais; até lá, qualquer diferença é observação, não decisão.

## Definition of Done por fatia

- comportamento existente preservado;
- testes unitários de invariantes antes/de junto da implementação;
- tenant isolation provado quando houver persistência por organização;
- migration backward-compatible e idempotente quando houver schema;
- falhas externas e quota não mascaradas;
- nenhum custo pago sem autorização explícita;
- compileall + `pytest -W error` + gates específicos;
- PostgreSQL real para concorrência/persistência quando aplicável;
- lint + TypeScript + production build quando houver impacto web;
- documentação LIVE atualizada no mesmo HEAD.
