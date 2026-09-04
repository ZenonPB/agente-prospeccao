# Intent Engine para sinais de compra

> **Status: 🟡 Proposto**  
> **Prioridade: P0**  
> **Domínio: Intent / Differentiation**

## Problema

Fit estrutural não responde à pergunta mais valiosa para prospecção: por que abordar esta empresa agora?

## Objetivo

Criar `IntentSignalService`/Intent Engine que detecte eventos recentes e gere signals temporais com evidência.

## Mudança proposta

Eventos iniciais: `NEW_BRANCH`, `HIRING`, `NEW_PRODUCT`, `EXPANSION`, `NEW_EQUIPMENT`, `NEW_FACTORY`, `PROCUREMENT_NOTICE`, `JOB_POSTING`, `WEBSITE_REDESIGN`, `NEW_SERVICE`, `MANAGEMENT_CHANGE`. Cada vertical atribui relevância diferente.

## Critérios de aceite

- Cada intent signal tem timestamp, fonte, confiança e evidência.
- Sinal expira ou perde peso com o tempo.
- A vertical controla o peso do evento.

## Testes mínimos

- Vaga de projetista pesa forte em Engenharia e quase zero em Landing Page.
- Evento antigo perde influência conforme política configurada.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
