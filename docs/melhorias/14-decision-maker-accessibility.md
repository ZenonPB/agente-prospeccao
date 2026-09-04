# Acessibilidade do decisor como sinal de ranking

> **Status: 🟡 Proposto**  
> **Prioridade: P1**  
> **Domínio: Ranking / Contactability**

## Problema

Dois leads igualmente bons comercialmente podem ter valor operacional muito diferente se um permite identificar o comprador e o outro não.

## Objetivo

Modelar `decision_maker_accessibility`/`contactability` e usá-lo no Opportunity Score sem confundir facilidade de contato com necessidade.

## Mudança proposta

Sinais: profissional autônomo, sócio identificado, empresa pequena, nome do decisor encontrado, canal direto, canal roteável. A força do sinal varia por vertical.

## Critérios de aceite

- Acessibilidade é dimensão separada de need/fit.
- O score mostra por que foi considerado acessível.
- Lead bom mas difícil de contatar não é apagado, apenas priorizado de forma adequada.

## Testes mínimos

- Profissional autônomo com WhatsApp tende a ter alta accessibility.
- Empresa industrial pode manter alto ICP mesmo com accessibility baixa.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
