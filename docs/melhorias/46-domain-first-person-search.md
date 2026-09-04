# Buscar pessoas por domínio antes de localização

> **Status: 🟡 Proposto**  
> **Prioridade: P1**  
> **Domínio: Contacts / Retrieval**

## Problema

Nome da empresa + cidade pode ser ambíguo. Quando o domínio próprio é conhecido, ele é um identificador mais forte para localizar pessoas associadas à organização.

## Objetivo

Priorizar consultas `domain + target titles` e usar `company_name + location` como fallback.

## Mudança proposta

O resolver deve fornecer domínio canônico aos people providers. Localização permanece útil para desambiguação, mas não deve substituir um domínio confiável.

## Critérios de aceite

- People provider recebe domínio quando disponível.
- Localização permanece filtro auxiliar.
- Domínio de marketplace/social não é tratado como domínio próprio do lead.

## Dependências

- CompanyIdentityResolver
- Normalização de domínio existente

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
