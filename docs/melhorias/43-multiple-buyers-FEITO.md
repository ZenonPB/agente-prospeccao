# Múltiplos decisores e Buyer Roles

> **Status: 🟡 Proposto**  
> **Prioridade: P0**  
> **Domínio: B2B Buying Committee**

## Problema

Vendas de ERP e Engenharia raramente dependem de uma única pessoa. Salvar apenas um `decision_maker` perde a estrutura real do comitê de compra.

## Objetivo

Permitir múltiplas pessoas por lead e classificar `ECONOMIC_BUYER`, `TECHNICAL_BUYER`, `CHAMPION`, `INFLUENCER`, `GATEKEEPER`.

## Mudança proposta

ERP pode ter dono/CFO como econômico, TI como técnico e operações como champion. Engenharia pode ter diretor industrial como econômico, gerente de engenharia como técnico e manutenção/produção como champion.

## Critérios de aceite

- Um lead suporta múltiplas pessoas e buyer roles.
- A mesma pessoa pode acumular roles.
- Outreach pode selecionar persona conforme etapa da venda.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
