# Archetypes apenas como fallback de geração

> **Status: 🟡 Proposto**  
> **Prioridade: P1**  
> **Domínio: Template Generation**

## Problema

Arquétipos digitais/ERP/engenharia/fabricação são úteis para bootstrap, mas não devem virar regras universais rígidas.

## Objetivo

Usar archetypes como base para gerar um Vertical Pack específico, que depois pode ser customizado e aprendido.

## Mudança proposta

Fluxo: archetype → profile gerado → customização da organização → learning. O archetype não deve sobrescrever regras aprendidas/específicas.

## Critérios de aceite

- Nova vertical desconhecida pode nascer de um archetype.
- Depois de gerado, o profile possui identidade/versionamento próprio.
- Customização da organização prevalece sobre fallback.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
