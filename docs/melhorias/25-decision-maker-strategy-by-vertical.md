# Decision Maker Strategy por vertical

> **✅ FEITO — `DecisionMakerStrategy.resolve_contact_strategy(profile_key)` com mapa profile→ordered providers + channel priority .)***  
> **Prioridade: P0**  
> **Domínio: Vertical Intelligence / Contacts**

## Problema

Buscar 'qualquer pessoa' da empresa reduz precisão e desperdiça créditos, porque o cargo relevante depende do que está sendo vendido.

## Objetivo

Fazer cada ProspectingProfile declarar personas/cargos de compra e prioridades.

## Mudança proposta

Landing Pages: proprietário, sócio, fundador, marketing/comercial. ERP: dono/CEO/COO, operações, administrativo/financeiro, TI. Engenharia: diretor industrial, engenharia, manutenção, produção, compras técnicas.

## Contratos / modelo de dados

```json
{
  "decision_maker_roles": [
    {"role": "Gerente de Engenharia", "priority": 100, "buyer_role": "TECHNICAL_BUYER"}
  ]
}
```

## Critérios de aceite

- People Discovery recebe cargos-alvo do profile.
- A mesma pessoa pode ter buyer role diferente conforme a oferta.
- Fallback para sócio/dono é configurável.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
