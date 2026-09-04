# Prospecting Hypothesis por lead

> **Status: 🟡 Proposto**  
> **Prioridade: P1**  
> **Domínio: AI Reasoning / Sales Enablement**

## Problema

Um score alto não ensina o vendedor a validar a oportunidade durante a conversa.

## Objetivo

Gerar uma hipótese comercial curta, baseada em fatos e inferências rotuladas, incluindo como validá-la.

## Mudança proposta

Formato: contexto factual → hipótese de dor/oportunidade → evidências → pergunta de validação. Ex.: operação CNC + vaga de projetista → hipótese de pico de demanda CAD → perguntar se detalhamento é 100% interno.

## Critérios de aceite

- Hipótese contém pelo menos uma evidência.
- A pergunta de validação é gerada para incertezas.
- A IA não apresenta hipótese como fato.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
