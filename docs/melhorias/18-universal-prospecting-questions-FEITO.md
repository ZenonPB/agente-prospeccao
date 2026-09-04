# Seis perguntas universais do agente de prospecção

> **Status: 🟡 Proposto**  
> **Prioridade: P1**  
> **Domínio: Agent Reasoning**

## Problema

Sem um contrato de raciocínio comum, cada vertical tende a virar um conjunto isolado de prompts e exceções.

## Objetivo

Padronizar o planejamento da prospecção em seis perguntas universais.

## Mudança proposta

O agente deve resolver, com evidência: (1) quem pode precisar da oferta; (2) quais sinais públicos indicam necessidade; (3) quais sinais indicam capacidade de compra; (4) qual evento aumenta probabilidade de compra agora; (5) quem decide/influencia; (6) qual argumento e próximo passo são adequados.

## Implementação sugerida

Usar essas perguntas na geração/validação de ProspectingProfile e no planejamento da campanha. Respostas desconhecidas devem permanecer UNKNOWN, não ser preenchidas por alucinação.

## Critérios de aceite

- Todo profile consegue responder às seis perguntas.
- Ausência de evidência não vira fato.
- As respostas alimentam discovery, scoring e outreach.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
