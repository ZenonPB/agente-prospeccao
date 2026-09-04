# Mostrar 'por que prospectar' diretamente no card

> **Status: 🟡 Proposto**  
> **Prioridade: P1**  
> **Domínio: Frontend / Explainability**

## Problema

O consultor perde tempo abrindo detalhes para entender por que um lead foi priorizado.

## Objetivo

Exibir no card um resumo curto, factual e acionável: score/prioridade, principais evidências, ausência crítica e melhor ângulo de abordagem.

## Mudança proposta

Usar dados já produzidos por `evidence`, score factors, opportunity dimensions e prospecting hypothesis. O resumo deve conter no máximo alguns sinais fortes e não inventar fatos.

## Critérios de aceite

- Card apresenta 3–5 sinais explicativos.
- Afirmações são rastreáveis a evidências.
- A abordagem sugerida é coerente com a vertical.

## Testes mínimos

- Sem evidência de WhatsApp, o card não pode afirmar WhatsApp disponível.
- Lead sem site mostra ausência como fato somente quando verificada.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
