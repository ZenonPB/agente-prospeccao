# Decision Maker Resolution Pipeline

> **Status: 🟡 Proposto**  
> **Prioridade: P0**  
> **Domínio: Contacts / Identity**

## Problema

O pipeline de contato tende a procurar email/LinkedIn cedo demais. Sem resolver primeiro quem é a pessoa certa, a cobertura de contato direto permanece baixa e créditos são gastos em pessoas irrelevantes.

## Objetivo

Mudar o objetivo de 'achar qualquer contato' para `empresa → cargo-alvo → pessoa → canais → verificação`.

## Mudança proposta

Criar pipeline com `TargetRoleResolver`, `PeopleDiscovery`, `PersonIdentityResolver`, `ContactDiscovery`, `ContactVerification` e `DecisionMakerScore`.

## Fluxo esperado

```text
Company
  ↓
Target Role Resolver
  ↓
People Discovery
  ↓
Person Identity Resolution
  ↓
Contact Discovery
  ↓
Contact Verification
  ↓
Decision Maker Ranking
```

## Critérios de aceite

- Contatos são sempre ligados a uma pessoa/cargo ou marcados como institucionais.
- Busca de email direto só ocorre depois de identidade suficiente quando possível.
- Top decisores são ranqueados por fit e confiança.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
