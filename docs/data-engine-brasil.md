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
com `cost_per_request` maior é inelegível em `allows` e no planner) e o teto
cumulativo da waterfall (`spent + expected_cost` nunca ultrapassa o teto).
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

### Brazil Company Registry

Ingerir/indexar fonte empresarial brasileira sem popular `Company` em massa.
Antes de escolher armazenamento definitivo, medir volume, atualização, índices
e custo operacional. Discovery do registry entra inicialmente em shadow/opt-in.

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
