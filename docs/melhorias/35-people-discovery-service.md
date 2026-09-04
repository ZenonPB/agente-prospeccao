# PeopleDiscoveryService com providers múltiplos

> **Status: 🟡 Proposto**  
> **Prioridade: P0**  
> **Domínio: Contacts / Discovery**

## Problema

Depender de uma única fonte para pessoas causa baixa cobertura, especialmente em PMEs brasileiras.

## Objetivo

Criar interface comum de discovery de pessoas e agregar evidências de múltiplos providers.

## Mudança proposta

Providers possíveis: site da empresa, CNPJ/QSA, base de pessoas autorizada, busca web, LinkedIn assistido/conforme integração permitida, Hunter/domain search e redes sociais públicas. Cada provider retorna nome, cargo, empresa, URLs, fonte e confiança.

## Contratos / modelo de dados

```json
{
  "name": "Carlos da Silva",
  "title": "Gerente Industrial",
  "company": "Metalúrgica XYZ",
  "linkedin_url": null,
  "email": null,
  "source": "company_website",
  "confidence": 0.86
}
```

## Critérios de aceite

- Providers compartilham contrato.
- Resultados são deduplicados por identidade.
- Falha em um provider não cancela os demais.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
