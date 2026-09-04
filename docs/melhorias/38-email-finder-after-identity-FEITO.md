# Email Finder somente após resolução de identidade

> **Status: 🟡 Proposto**  
> **Prioridade: P0**  
> **Domínio: Contacts / Email**

## Problema

Tentar descobrir email antes de saber nome/cargo reduz precisão e pode gastar cota com contatos genéricos.

## Objetivo

Usar email/domain search como etapa posterior: nome conhecido → finder por nome + domínio; nome desconhecido → domain search/people discovery para identificar candidatos primeiro.

## Mudança proposta

O pipeline deve preferir consulta por pessoa e domínio. Contatos genéricos (`contato@`, `comercial@`) continuam úteis, mas devem ser classificados como institucionais, não como contato direto de decisor.

## Critérios de aceite

- O pipeline prefere nome+domínio quando disponível.
- Emails genéricos continuam possíveis, mas são classificados como institucionais.
- Créditos são consumidos de forma seletiva.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
