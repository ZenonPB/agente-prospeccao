# Prioridade de canal por vertical

> **Status: 🟡 Proposto**  
> **Prioridade: P1**  
> **Domínio: Outreach / Contacts**

## Problema

Considerar email como único sucesso subestima leads acionáveis. O melhor canal varia por tipo de negócio e comprador.

## Objetivo

Adicionar `preferred_channels` ao profile e ranquear canais disponíveis por adequação, confiança e tipo de contato.

## Mudança proposta

Exemplo: pequenos negócios locais podem priorizar WhatsApp/Instagram; ERP B2B e Engenharia podem priorizar email, LinkedIn e telefone corporativo.

## Critérios de aceite

- Profile define prioridade de canais.
- Lead sem email pode continuar ACTIONABLE.
- O canal escolhido é justificado por disponibilidade e estratégia.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
