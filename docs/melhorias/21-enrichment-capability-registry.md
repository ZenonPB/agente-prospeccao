# Catálogo de capabilities de enriquecimento

> **Status: 🟠 Parcial — `enrichment_steps` do template segue como catálogo inicial; pre-scoring gate consome o perfil. Falta: capabilities com custo/pré-condições/signals produzidos.**  
> **Prioridade: P0**  
> **Domínio: Architecture / Enrichment**

## Problema

Steps fixos como `technical_site`, `cnpj_receita` e `business_social` são um bom começo, mas não escalam para diferentes fontes e verticais.

## Objetivo

Modelar enrichment como capacidades plugáveis com entradas, saídas, custos, pré-condições e signals produzidos.

## Mudança proposta

Capabilities possíveis: `company_registry`, `website_technical`, `website_semantic`, `maps_reputation`, `social_presence`, `decision_maker`, `company_linkedin`, `job_postings`, `news`, `procurement`, `public_tenders`, `technology_stack`, `location`.

## Critérios de aceite

- Capability declara quais signals produz.
- Planner consegue pular capability irrelevante.
- Falha de uma capability não corrompe signals de outras.

## Dependências

- Signal Registry
- ProspectingProfile

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
