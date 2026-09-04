# Aprendizado por outcomes comerciais

> **Status: 🟡 Proposto**  
> **Prioridade: P0**  
> **Domínio: Learning Loop**

## Problema

Feedback humano sobre score ensina preferência do consultor, mas o melhor sinal é o que o mercado fez. O sistema precisa distinguir necessidade percebida de propensão real de compra.

## Objetivo

Incorporar estados de outcome no aprendizado: `NO_REPLY`, `REPLIED`, `POSITIVE_REPLY`, `MEETING`, `PROPOSAL`, `WON`, `LOST` e motivos de perda quando disponíveis.

## Mudança proposta

Gerar features e estatísticas por sinal, faixa de score, nicho, canal e vertical. Não reescrever automaticamente regras com pouca evidência; produzir recomendações/priors versionados.

## Implementação sugerida

Integrar com o funil já existente. Manter feedback humano separado de feedback de mercado. Agregar por janela temporal e organização.

## Critérios de aceite

- Uma venda/reunião/resposta alimenta métricas de aprendizado.
- É possível comparar `P(outcome | signal)`.
- O sistema diferencia feedback humano de outcome real.

## Testes mínimos

- Outcome WON é associado ao snapshot de sinais do momento da prospecção.
- Mudanças posteriores no lead não reescrevem evidência histórica.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
