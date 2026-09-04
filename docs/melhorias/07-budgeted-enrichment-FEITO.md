# Enriquecimento seletivo por custo e valor esperado

> **Status: ✅ FEITO — enriquecimento seletivo implementado**: candidatos abaixo do threshold (ou fora do top_k) não viram Lead e não consomem CNPJ/auditoria/LLM/contato. Capabilities com custo/pré-condições declaradas seguem no doc 21 como evolução.  
> **Prioridade: P0**  
> **Domínio: Enrichment**

## Problema

Executar CNPJ, auditoria, IA e contato em todos os resultados desperdiça cota e tempo com candidatos de baixa qualidade.

## Objetivo

Enriquecer progressivamente apenas candidatos que sobrevivem aos gates anteriores e tornar custo/benefício parte explícita da estratégia.

## Mudança proposta

Cada enrichment capability deve declarar custo relativo, pré-condições e ganho informacional esperado. O planner decide a próxima ação com base no perfil da campanha e estado do candidato.

## Contratos / modelo de dados

```json
{
  "capability": "contact_discovery",
  "cost_tier": "high",
  "requires": ["company_identity"],
  "run_if": "overall_pre_score >= 65"
}
```

## Implementação sugerida

Começar com gates determinísticos: pre-score → enrichment básico → AI scoring → contato. Evoluir depois para orçamento por campanha e early stopping.

## Critérios de aceite

- Candidatos abaixo do gate não chamam APIs caras.
- Logs mostram por que uma etapa foi pulada.
- A estratégia pode mudar por vertical.

## Testes mínimos

- Landing Page pode pular CNPJ quando não necessário.
- Engenharia pode priorizar CNPJ antes de contato.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
