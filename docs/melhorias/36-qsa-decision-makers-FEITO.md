# QSA como fonte de sócios e decisores econômicos

> **Status: 🟡 Proposto**  
> **Prioridade: P0**  
> **Domínio: Contacts / Brazil**

## Problema

Em clínicas, escritórios, empresas familiares e pequenas indústrias, o decisor pode não ter LinkedIn atualizado, mas sócios/administradores podem estar disponíveis em dados cadastrais.

## Objetivo

Usar QSA para descobrir `LEGAL_DECISION_MAKER`/possível `ECONOMIC_BUYER` e depois resolver presença e contatos dessa pessoa.

## Mudança proposta

Não assumir que todo sócio é o melhor contato operacional. Classificar sócio como persona econômica/legal e deixar a vertical decidir prioridade versus gerente técnico/operacional.

## Critérios de aceite

- QSA gera pessoas com fonte cadastral.
- Sócio não é automaticamente marcado como technical buyer.
- Landing Page pode priorizar sócio; Engenharia pode priorizar gerente técnico.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
