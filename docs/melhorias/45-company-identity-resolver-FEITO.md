# CompanyIdentityResolver e aliases da empresa

> **Status: 🟡 Proposto**  
> **Prioridade: P0**  
> **Domínio: Identity Resolution**

## Problema

APIs de pessoas e email falham quando recebem razão social longa, sufixos jurídicos ou nomes divergentes entre Maps, CNPJ, domínio e outras fontes.

## Objetivo

Criar uma identidade canônica da empresa com razão social, nome fantasia, nome normalizado, domínio e aliases por fonte.

## Mudança proposta

Preferir domínio próprio e CNPJ como identificadores fortes quando disponíveis. Remover ruído jurídico apenas para busca, nunca alterando o dado cadastral original.

## Contratos / modelo de dados

```json
{
  "legal_name": "ABC INDUSTRIA E COMERCIO DE MAQUINAS LTDA",
  "trade_name": "ABC Máquinas",
  "normalized_name": "ABC Máquinas",
  "domain": "abcmaquinas.com.br",
  "aliases": ["ABC Maquinas", "ABC Industrial"]
}
```

## Implementação sugerida

Resolver conflitos entre CNPJ, place_id, domínio e aliases com confiança. Domínios de marketplace/social não podem ser aceitos como domínio próprio.

## Critérios de aceite

- Busca de pessoas recebe domínio/nome normalizado.
- Razão social original permanece persistida.
- Aliases de diferentes fontes são vinculados à mesma identidade quando evidência suficiente existir.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
