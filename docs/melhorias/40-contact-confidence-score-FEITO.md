# ContactConfidenceScore e IdentityConfidence

> **Status: 🟡 Proposto**  
> **Prioridade: P0**  
> **Domínio: Contacts / Ranking**

## Problema

Campo binário 'tem email' não representa qualidade do contato nem certeza de que a pessoa ainda trabalha na empresa.

## Objetivo

Separar `decision_maker_fit`, `identity_confidence` e `contact_confidence`.

## Mudança proposta

Exemplos de evidência: email corporativo verificado, cargo atual confirmado, mesma pessoa encontrada em múltiplas fontes, perfil/biografia coerente, telefone corporativo. Penalizar email inferido não verificado e vínculo desatualizado.

## Critérios de aceite

- Scores são independentes.
- Cada score é explicável por fatores.
- Contato de alta confiança pode ser priorizado sem alterar ICP da empresa.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
