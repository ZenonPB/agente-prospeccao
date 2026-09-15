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

Consumidores legados que ainda não fornecem a política mantêm o comportamento
anterior. Isso é deliberado para rollout backward-compatible; cada capability
será migrada e testada isoladamente.

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
