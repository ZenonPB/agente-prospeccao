# Padrões de Golden Lead por vertical

> **Status: 🟡 Proposto**  
> **Prioridade: P1**  
> **Domínio: Ranking / UX**

## Problema

O vendedor precisa reconhecer rapidamente combinações de sinais que historicamente representam oportunidades excepcionais.

## Objetivo

Permitir que cada vertical defina padrões compostos de `golden_lead` com explicação explícita, sem substituir o score dimensional.

## Mudança proposta

Exemplo Landing Page local: negócio independente + bom ticket + 20–300 avaliações + rating alto + Instagram + telefone/WhatsApp + sem site próprio + decisor acessível.

## Contratos / modelo de dados

```json
{
  "pattern": "landing_local_golden_v1",
  "matched": true,
  "evidence": ["NO_OWN_WEBSITE", "HAS_INSTAGRAM", "HIGH_LOCAL_TRACTION"]
}
```

## Critérios de aceite

- O padrão é configurável por vertical.
- A UI exibe quais condições foram satisfeitas.
- Falhar em uma condição não destrói o score geral.

## Testes mínimos

- Golden pattern só é marcado quando todas as condições obrigatórias forem evidenciadas.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
