# Ordem de enriquecimento definida pela oferta

> **Status: ✅ FEITO — ordem declarada pela oferta via `enrichment_steps` + `enrichment_strategy` (skip/stop_after) no capability registry; steps irrelevantes pulados com motivo; falha de uma capability não corrompe as demais.  
> **Prioridade: P0**  
> **Domínio: Vertical Intelligence / Enrichment**

## Problema

Uma sequência fixa de enrichment não serve igualmente para Landing Pages, ERP e Engenharia. O dado mais útil e barato muda conforme a oferta.

## Objetivo

Fazer o perfil da vertical definir capacidades, ordem, gates e condições de parada do enrichment.

## Mudança proposta

Exemplos: Landing Page → Maps/social/site rápido → scoring → contato; ERP → company registry/CNAE/porte → site semântico/stack → scoring → decisor; Engenharia → CNPJ/CNAE/atividade industrial → sinais de intenção → decisor.

## Implementação sugerida

Generalizar `enrichment_steps` para um `enrichment_strategy` ordenado/condicional. Preservar compatibilidade com os steps existentes durante migração.

## Critérios de aceite

- Perfis distintos executam ordens distintas no mesmo engine.
- Steps irrelevantes são pulados.
- A execução permanece auditável.

## Testes mínimos

- Engenharia não executa auditoria SEO por padrão.
- Landing Page consegue executar sem consulta cadastral quando configurada.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
