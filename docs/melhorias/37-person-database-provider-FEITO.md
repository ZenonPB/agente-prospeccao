# Provider de base de pessoas por domínio e cargo

> **Status: 🟡 Proposto**  
> **Prioridade: P1**  
> **Domínio: Contacts / External Providers**

## Problema

Email finders funcionam melhor quando a pessoa já é conhecida; falta uma etapa própria para descobrir pessoas associadas a um domínio e cargos-alvo.

## Objetivo

Integrar opcionalmente provider de people search que aceite domínio, titles/seniority e localização, devolvendo candidatos antes de revelar/enriquecer contatos.

## Mudança proposta

O provider deve ser encapsulado por interface, com quota/custo. Revelar email/telefone somente para candidatos de alta prioridade.

## Critérios de aceite

- Busca por domínio/cargo retorna candidatos normalizados.
- Consumo de créditos de enrichment ocorre apenas para pessoas selecionadas.
- Provider externo pode ser desligado sem quebrar pipeline.

## Riscos / considerações

- Respeitar termos de uso, LGPD e permissões da integração.
- Não acoplar arquitetura a um fornecedor específico.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
