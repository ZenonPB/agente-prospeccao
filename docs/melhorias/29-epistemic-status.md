# Status epistêmico para fatos, inferências e hipóteses

> **Status: 🟡 Proposto**  
> **Prioridade: P0**  
> **Domínio: Evidence / AI Safety**

## Problema

O agente pode misturar informação observada com inferência de segmento, fazendo o vendedor acreditar em fatos inexistentes.

## Objetivo

Classificar toda afirmação relevante como `FACT`, `INFERENCE`, `HYPOTHESIS` ou `UNKNOWN`, com confiança e fonte quando aplicável.

## Mudança proposta

Introduzir um contrato comum de evidência. Facts exigem fonte observável; Inference deriva de fatos existentes; Hypothesis é uma possibilidade a validar; UNKNOWN deve permanecer desconhecido.

## Contratos / modelo de dados

```json
{
  "statement": "Pode operar com processos manuais",
  "epistemic_status": "HYPOTHESIS",
  "confidence": 0.42,
  "evidence_refs": []
}
```

## Implementação sugerida

Facts precisam de evidência observável. Inference deriva de sinais existentes. Hypothesis deve ser validada em contato. UNKNOWN não deve ser preenchido por conveniência do prompt.

## Critérios de aceite

- A UI/prompt consegue distinguir os quatro estados.
- Facts sem fonte válida são rejeitados/rebaixados.
- Pitch não transforma hipótese em alegação factual.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
