# Opportunity Score como vetor universal

> **✅ FEITO — VECTOR_WEIGHTS expandido com dimensões universais (icp_fit/intent/buying_power/reachability/timing) peso 0 (backward compat) + formula_version v2 (#27).**  
> **Prioridade: P0**  
> **Domínio: Scoring Architecture**

## Problema

Need/commercial fit ajudam, mas a arquitetura universal precisa representar fit, necessidade, intenção, poder de compra, alcançabilidade e timing separadamente.

## Objetivo

Padronizar um vetor universal e deixar o profile escolher pesos/fórmula.

## Mudança proposta

Dimensões recomendadas: `icp_fit`, `need`, `intent`, `buying_power`, `reachability`, `timing`, `overall`. Manter dimensões específicas opcionais sem quebrar o contrato comum.

## Critérios de aceite

- Todas as verticais expõem o vetor base.
- Overall inclui `formula_version`.
- UI consegue comparar leads por dimensão.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
