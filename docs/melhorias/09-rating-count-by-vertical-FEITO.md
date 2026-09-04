# Interpretar volume de avaliações por vertical

> **Status: 🟡 Proposto**  
> **Prioridade: P1**  
> **Domínio: Signals / Local Business**

## Problema

`userRatingCount` é útil como proxy de tração, mas a interpretação não é monotônica nem universal. Poucas avaliações podem indicar pouca demanda; milhares podem indicar rede/grande operação.

## Objetivo

Transformar rating count em sinal contextual por vertical, usando faixas configuráveis e não uma regra global.

## Mudança proposta

Criar buckets por perfil. Exemplo inicial para psicologia: 0–4 fraco, 5–19 médio, 20–49 bom, 50–149 muito bom, 150–400 ótimo, 400+ revisar porte/rede. Esses valores são ponto de partida e devem ser aprendidos.

## Implementação sugerida

Representar faixas no perfil e produzir um signal normalizado, mantendo valor bruto. Nunca descartar o valor original.

## Critérios de aceite

- Buckets podem variar entre verticais.
- O raw `rating_count` continua persistido.
- O pre-score usa a interpretação configurada.

## Testes mínimos

- Mesma contagem pode gerar classificação diferente em restaurante e psicologia.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
