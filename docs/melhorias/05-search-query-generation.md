# Geração automática de queries de descoberta

> **Status: 🟡 Proposto**  
> **Prioridade: P1**  
> **Domínio: Discovery Planner**

## Problema

O usuário normalmente informa serviço, segmento e localização em nível mais amplo do que o necessário para maximizar recall em mecanismos de busca.

## Objetivo

Gerar automaticamente consultas de descoberta relevantes, específicas e diversificadas, usando LLM apenas como expansor de consulta.

## Mudança proposta

Criar `SearchQueryGenerationService` com entrada `service`, `segment`, `city`, `state`, contexto da oferta e perfil. A saída é uma lista de queries/subnichos. A LLM não qualifica leads nessa etapa.

## Contratos / modelo de dados

```json
{
  "queries": [
    {"query": "clínica de psicologia Araraquara", "intent": "core"},
    {"query": "psicólogo infantil Araraquara", "intent": "subniche"}
  ]
}
```

## Implementação sugerida

Deduplicar consultas semanticamente próximas, limitar quantidade, aplicar templates determinísticos quando a LLM estiver indisponível e salvar a lista utilizada na campanha.

## Critérios de aceite

- O serviço funciona sem promover/desqualificar leads.
- Falha da LLM possui fallback.
- Queries geradas ficam auditáveis na campanha.

## Testes mínimos

- Segmento de estética gera termos relacionados sem inventar localidades.
- Não gerar dezenas de variações quase idênticas.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
