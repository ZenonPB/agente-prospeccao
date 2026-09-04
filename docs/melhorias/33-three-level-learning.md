# Aprendizado em três níveis: global, vertical e organização

> **Status: 🟡 Proposto**  
> **Prioridade: P1**  
> **Domínio: Learning Architecture**

## Problema

Aprendizado somente por template × organização é seguro, mas impede reaproveitar padrões realmente universais e separar conhecimento de vertical de preferências locais.

## Objetivo

Estruturar regras/priors em camadas `GLOBAL`, `VERTICAL` e `ORGANIZATION`, com precedência clara e isolamento.

## Mudança proposta

Global contém fatos metodológicos estáveis; Vertical contém padrões da oferta; Organization contém desempenho e preferências locais. Mudanças mais específicas sobrepõem as gerais sem editar a origem.

## Critérios de aceite

- Dados de uma organização não contaminam outra.
- É possível auditar de qual camada veio uma regra.
- Conflitos têm precedência determinística.

## Riscos / considerações

- Aprendizado global deve exigir evidência muito maior e revisão conservadora.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
