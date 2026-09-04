# CNAE/CNPJ como provider de discovery para B2B industrial

> **Status: 🟡 Proposto**  
> **Prioridade: P0**  
> **Domínio: Discovery / Engineering**

## Contexto atual

O repositório já possui fundação relacionada a `cnae_discovery_service.py`; confirmar o contrato atual antes de criar um provider paralelo.

## Problema

Engenharia Mecânica precisa encontrar fabricantes, usinagens, caldeirarias e operações industriais que podem ter pouca visibilidade no Google Maps.

## Objetivo

Promover o serviço de descoberta por CNAE/CNPJ a provider nativo do Discovery Planner, não apenas enrichment posterior.

## Mudança proposta

Usar filtros geográficos, CNAEs compatíveis, situação cadastral e dados básicos para gerar Candidates. Em seguida enriquecer site/semântica, intenção e decisores.

## Critérios de aceite

- Uma campanha de Engenharia consegue criar candidatos sem Places.
- Candidates mantêm CNPJ e origem do filtro.
- Empresas inativas são excluídas quando a fonte permitir.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
