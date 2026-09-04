# Vertical Pack declarativo

> **Status: 🟡 Proposto**  
> **Prioridade: P0**  
> **Domínio: Architecture / Configuration**

## Problema

Adicionar uma nova oferta ainda pode exigir espalhar regras por vários arquivos e prompts.

## Objetivo

Empacotar toda inteligência da oferta em um `VerticalPack`/ProspectingProfile versionado e declarativo.

## Mudança proposta

O pack deve definir ICP, discovery, fontes/capabilities, sinais/pesos, enrichment, exclusions, buyer roles, intent, cadence, pitch, perguntas e objeções. Pode ser armazenado no banco ou em configuração declarativa, com seed e overrides por organização.

## Fluxo esperado

```text
Archetype
    ↓
Vertical Pack base
    ↓
Organization override
    ↓
Campaign snapshot
```

## Critérios de aceite

- Adicionar uma nova vertical não exige alterar lógica central.
- Pack é validado por schema.
- Campanha salva snapshot/version do pack usado.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
