# Discovery Planner orientado pela oferta

> **Status: ✅ FEITO (fundação completa) — DiscoveryPlanner serviço criado (seam profundo), testado, com interface plan(). Próximo: integrar ao pipeline_worker.**
> **Prioridade: P0**  
> **Domínio: Architecture / Discovery**

## Problema

A mesma fonte de descoberta não é ideal para todos os tipos de venda. Maps é forte em negócios locais; CNPJ/CNAE, web, vagas e procurement são mais adequados para B2B industrial ou ERP.

## Objetivo

Criar um planner que escolha fontes, filtros, consultas e orçamento de coleta a partir do ProspectingProfile.

## Mudança proposta

O planner recebe oferta, segmento, geografia e profile; retorna um plano com providers, queries/filtros, ordem, limites e critério de dedup.

## Contratos / modelo de dados

```json
{
  "providers": [
    {"type": "google_places", "queries": ["..."], "budget": 100},
    {"type": "cnae_discovery", "filters": {"city": "...", "cnaes": ["..."]}}
  ],
  "target_candidates": 300
}
```

## Critérios de aceite

- Landing Page pode usar Places como principal.
- ERP pode priorizar company registry/CNAE.
- Engenharia pode usar CNAE/web sem depender do Maps.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
