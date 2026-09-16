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
seção `Brazil Company Registry (Fase 1B)` abaixo. Discovery produtivo a
partir do Registry entra na 1C; nesta fase nada do fluxo de campanhas o
consome.

### Public Web Intelligence

Enrichment passivo e determinístico primeiro (HTTP/DNS/HTML/metadados/links);
LLM somente para interpretação em que regras determinísticas não bastam.

### Dimensões comerciais

Calcular aderência, momento, contatabilidade e confiança em paralelo ao score
existente. Ausência de contato não reduz aderência. Ranking novo só vira
principal após benchmark e campanhas reais.

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

Restrição de acesso encontrada: o host legado de bulk não responde desta
rede e o novo exige login interativo — o operador baixa os ZIPs mensais e o
CLI ingere os arquivos extraídos. Volume de referência: ~4,7 GB compactados
/ ~17 GB brutos em 2021 (maior em 2026).

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
- `registry_cnaes`: domínio CNAE (labels com upsert real por reimport).
  Município: só código (sem tabela de labels — linhas de referência não
  trazem UF; fica para a 1C).

Índices (todos validados com EXPLAIN ANALYZE, §benchmark): PK por CNPJ;
`cnpj_basico`; covering `(cnae_principal, uf, cnpj)`; covering
`(uf, municipio_cod, situacao, cnpj)`; assoc `(cnae, cnpj)`. Sem GIN/array:
`EXISTS` na assoc (0,19 ms) venceu GIN (28 ms) no spike.

### Ingestão (`services/registry/importer.py` + CLI `import_registry`)

Streaming em chunks de 5000 linhas: parse → temp table → upsert → checkpoint
commitado. Idempotente por chave natural. Identidade do arquivo é SHA-256 em
streaming (tamanho sozinho não decide): concluído + digest igual pula;
tamanhos iguais com bytes diferentes reprocessam. `content_hash` inclui
secundários ordenados e distingue updated/unchanged (linhas importadas antes
do hash novo atualizam uma vez e estabilizam).
Arquivos são aplicados na ordem canônica (estabelecimentos → empresas →
CNAE) independente da ordem do CLI. Empresas aplicam razão/porte/capital via
merge por `cnpj_basico` (só quando diferentes — `IS DISTINCT FROM`); labels
CNAE fazem upsert real. `snapshot_month` exige `AAAA-MM`; cursor de busca
exige 14 alnum. Linha ruim conta `rejected` sem abortar; arquivo
inacessível/corrompido falha fechado com ledger. Concorrência no mesmo
snapshot é segura (PK + retry de criação); totais valem por execução.

Operação local (CWD `services/workers`):
`python -m src.scripts.import_registry --snapshot-month 2026-08
--estabelecimentos <arquivo> [--empresas ...] [--cnaes ...]`.
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

### Limites e próximos (1C)

Sem labels de município/natureza/motivo; sem busca textual; sem promoção
para `Company`; sem consumo por campanhas; sem Places/web/people/scores.
1C integra o Registry ao discovery (shadow/opt-in) e resolve identidade
RegistryCandidate → Company quando houver regra explícita.

### Integração 1C + 1D (em validação — branch `feat/registry-discovery-web-intelligence`)

Estado observável nesta branch (não mergeado; sem migração — zero migrations):

- runtime produtivo preservado: OfferProfile → plano →
  `DiscoveryProviderRegistry` → `DiscoveryExecutor`; federation segue seam
  futuro e `RegistryDiscoveryProvider` continua fora do pipeline produtivo;
- conceito público continua `cnae_discovery` (sem provider novo): com
  `REGISTRY_DISCOVERY_ENABLED=True`, `RegistryCnaeDiscoveryAdapter`
  (workers `services/registry/discovery_adapter.py`) vira a implementação
  primária e o `CnaeDiscoveryService` legado vira fallback automático em
  falha; default (`False`) mantém comportamento idêntico ao anterior;
- CNAE com semântica explícita (`services/registry/cnae_matching.py`):
  completo 7 dígitos → exato; prefixo 1–6 dígitos → faixa ancorada
  (ex.: `"28"` → `2800000–2899999`); inválido → `ValueError` (fail-closed);
  `SearchFilters` aceita `cnae_prefixes` + `situacoes`, preservando keyset e
  no máximo 3 queries;
- gate anti-varredura (`services/registry/targeting.py`): sem ≥1 CNAE
  válido o Registry não é consultado (retorna `None`, chamador usa providers
  existentes); 1 UF vira filtro, múltiplas UFs não inventam filtro; raio/
  cidade-nome nunca viram `municipio_cod` (vão para `unapplied`);
  `target_candidates` vira `limit` da query PG (filtro no banco, depois
  paginação) — nunca materializa o universo para fatiar em Python; múltiplas
  UFs suportadas viram `IN` set-based, sem varredura por UF em Python;
- RegistryCandidate continua separado do CRM (sem `organization_id`; busca
  pura não cria Company/Lead/Opportunity); promoção usa a fronteira
  existente (`resolve_cross_provider_lead` → `find_company_by_aliases`,
  CNPJ → domínio → aliases);
- shadow barato (`REGISTRY_SHADOW_MODE=True`, coroutine, nunca loop
  aninhado): `compare` conta candidatos no nível mais barato (sem
  enrichment, sem Places/Groq, sem promoção; `enrichment_calls=0`/
  `promoted_count=0`), persistido em `ProviderExecutionMetric.usage`
  (`cnae_discovery:shadow`) — sem nova tabela. Nesta fatia o shadow do
  pipeline registra `registry_count`/`registry_status`; `legacy_count`/
  `overlap` ficam em 0 porque o legado externo não é reexecutado só para
  comparar (a série histórica de `provider_metrics` continua sendo a base
  de comparação; o `compare` unitário com `legacy_run` cobre overlap);
- 1D (`services/prospecting/safe_web_client.py` + `web_facts.py` +
  `web_intelligence.py`): `SafePublicWebClient` com allowlist http/https,
  DNS resolve-all (qualquer IP não-global rejeita), redirect manual com
  revalidação por hop, timeouts, streaming com teto (~2 MB), Content-Type
  allowlist, sem JS/headless; extração determinística FACT-only (sem LLM,
  sem API paga); falha → `UNKNOWN`, nunca `website_absent`; `observed_at` =
  UTC real da observação; provenance reutilizada
  (`source/source_url/observed_at/provider/capability/kind=FACT`); hook
  opt-in `public_web_facts` no enrichment (após `_persist_scoring`,
  `PUBLIC_WEB_ENABLED=True`, só com website) persiste em
  `Enrichment.raw_technical_data["web_facts"]` + `Lead.evidence`;
  concorrência limitada, sem transação DB aberta durante HTTP;
- consumidores web legados (`TechnicalEnrichmentService`, people providers)
  NÃO foram migrados nesta fatia (dívida explícita): o caminho 1D novo é
  seguro; a consolidação gradual fica para depois com substituição pequena
  e behavior-preserving;
- configuração (default seguro, kill-switch sem rollback de banco):
  `REGISTRY_DISCOVERY_ENABLED`, `REGISTRY_SHADOW_MODE` (API + workers),
  `PUBLIC_WEB_ENABLED`, `PUBLIC_WEB_MAX_TARGETS`,
  `PUBLIC_WEB_MAX_CONCURRENCY` (workers).

- O caminho dedicado `source=cnae` reutiliza o mesmo adapter Registry-backed;
  com Registry desligado ou sem targeting declarativo, mantém o fallback legado.

Validação PostgreSQL desta branch (banco local descartável, PostgreSQL 16.14):
os testes Registry/search/prefix/provider/ingestion/tenant passaram em banco
real; migrations passaram no upgrade vazio, segundo upgrade e schema verifier;
backup/restore com `pg_dump`/`pg_restore` também passou. O benchmark sintético
de 30.000 empresas demonstrou LIMIT no PostgreSQL, matching set-based e não
materialização do universo. O índice de CNAE secundário existente é
`ix_registry_cnaes_cnae (cnae, cnpj)`, criado na migration
`c1d2e3f4a5b6` e verificado pelo schema verifier. O EXPLAIN do dataset
pequeno mostrou `Seq Scan` na associação com apenas 32 linhas; isso é uma
escolha racional do planner para tabela minúscula, não evidência para criar
índice adicional. Benchmark com milhões de associações secundárias permanece
validação operacional pendente.

Limites conhecidos: `empty` (sem match) vs snapshot ausente não são
distinguidos (sem query extra); TOCTOU resolve→connect documentado como
risco residual (httpx não pinna IP com SNI de forma simples); snapshot real da
Receita e piloto AlphaMec ainda não estão disponíveis neste ambiente. A falha
de concorrência do Historical Importer em
`test_import_concurrency.py::test_confirm_concorrente_aceita_um_e_rejeita_o_resto_por_versao`
foi reproduzida na main limpa e está registrada como dívida separada,
pré-existente e fora do escopo desta branch.

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
