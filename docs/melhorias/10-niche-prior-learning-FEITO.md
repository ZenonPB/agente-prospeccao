# Niche Prior por serviço e organização

> **Status: 🟡 Proposto**  
> **Prioridade: P1**  
> **Domínio: Learning / Ranking**

## Problema

O agente conhece o segmento, mas não incorpora sistematicamente o histórico de quais nichos convertem melhor para uma oferta e organização.

## Objetivo

Adicionar um prior de atratividade do nicho que comece configurável e evolua com resultados reais.

## Mudança proposta

Persistir `niche_prior` por `organization × service/vertical × segment`. Usar como fator moderado de ranking, nunca como substituto para fit individual.

## Contratos / modelo de dados

```json
{
  "organization_id": "...",
  "vertical": "landing_pages",
  "segment": "estetica",
  "prior": 0.84,
  "sample_size": 80,
  "updated_from": "outcomes"
}
```

## Implementação sugerida

Exigir amostra mínima antes de ajustar agressivamente. Aplicar smoothing para evitar que 1 venda em 1 contato domine o ranking.

## Critérios de aceite

- Prior é escopado por organização e oferta.
- Baixa amostra reduz influência.
- O histórico pode ser reprocessado.

## Testes mínimos

- Nichos com melhor conversão e amostra suficiente aumentam moderadamente no ranking.
- Organizações não contaminam priors umas das outras.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
