# Separar ICP Fit de Intent

> **✅ FEITO — `buying_trigger_service.icp_vs_intent()` distingue ICP (fixo) de Intent (evento) (#19).**  
> **Prioridade: P0**  
> **Domínio: Scoring / Intent**

## Problema

Uma empresa pode ter fit estrutural excelente, mas nenhum motivo para comprar agora. Misturar fit e timing faz leads estáticos dominarem a fila.

## Objetivo

Persistir `icp_fit` e `intent_score` separadamente e usá-los no Opportunity Score.

## Mudança proposta

ICP representa compatibilidade estrutural com a oferta; Intent representa sinais recentes/observáveis de necessidade ou mudança. Exemplos: nova filial, contratação, expansão, novo equipamento, novo serviço, campanha, licitação.

## Critérios de aceite

- ICP alto e intent baixo são representáveis.
- Intent possui evidência e timestamp.
- Ranking pode priorizar timing sem apagar fit.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
