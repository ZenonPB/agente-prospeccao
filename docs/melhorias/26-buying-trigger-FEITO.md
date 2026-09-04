# Buying Trigger e Why Now

> **✅ FEITO — `buying_trigger_service.detect_buying_triggers()` converte intent events → triggers acionáveis (#26).**  
> **Prioridade: P1**  
> **Domínio: Intent / Outreach**

## Problema

Uma descrição genérica de necessidade não gera urgência nem personalização suficiente para abordagem.

## Objetivo

Persistir um `buying_trigger` e `why_now` quando houver evidência recente que conecte a empresa à oferta.

## Mudança proposta

Exemplo ERP: abriu segunda unidade → mais complexidade operacional. Engenharia: contratando projetista → provável aumento de demanda técnica. Landing: lançou novo serviço/campanha → precisa converter tráfego.

## Critérios de aceite

- Buying trigger só existe com evidência.
- `why_now` distingue fato de interpretação.
- Outreach pode citar o trigger sem inventar detalhes.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
