# Métricas Precision@K para qualidade do ranking

> **Status: 🟡 Proposto**  
> **Prioridade: P1**  
> **Domínio: BI / Evaluation**

## Problema

Avaliar apenas se o score 'parece correto' não mede o objetivo comercial: colocar os melhores leads no topo da fila.

## Objetivo

Adicionar Precision@10, @25 e @50 para reply, positive reply, meeting e won, por campanha, vertical, nicho e organização.

## Mudança proposta

O denominador é o top K do ranking no momento da seleção; o numerador é quantos desses leads atingiram o outcome em uma janela definida.

## Implementação sugerida

Salvar snapshot/posição do ranking para evitar hindsight bias. Expor séries temporais para comparar versões do scoring.

## Critérios de aceite

- Métrica pode ser calculada para diferentes outcomes.
- A posição original do lead é preservada.
- É possível comparar versões do ranking.

## Testes mínimos

- Top 10 com 3 reuniões retorna Precision@10(meeting)=0.30.
- Leads fora do top K não entram no denominador.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
