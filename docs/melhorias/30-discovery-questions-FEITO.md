# Perguntas de qualificação definidas pela vertical

> **Status: 🟡 Proposto**  
> **Prioridade: P1**  
> **Domínio: Vertical Intelligence / Sales Enablement**

## Problema

O agente encontra e pontua leads, mas pode não orientar o consultor sobre o que precisa ser descoberto para confirmar a oportunidade.

## Objetivo

Adicionar `discovery_questions` aos profiles e usar as perguntas em mensagens, ligações e reuniões.

## Mudança proposta

ERP: estoque, orçamento, integrações, portal. Engenharia: projetos CAD internos/terceirizados, gargalo, dispositivos/gabaritos. Landing: origem dos leads, anúncios, destino do tráfego e agendamento.

## Critérios de aceite

- Cada profile pode declarar perguntas por buyer role/estágio.
- Perguntas usadas na prospecção são registráveis no playbook.
- Não tratar resposta presumida como evidência.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
