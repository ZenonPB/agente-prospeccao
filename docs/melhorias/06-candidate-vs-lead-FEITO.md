# Separar Candidate de Lead

> **Status: ✅ FEITO — Candidate como estado no pipeline**: gate de promoção Candidate→Lead no discovery com descarte auditável e idempotente (`prescoring_discards`, migration `f1a2b3c4d5e6`). Entidade Candidate persistida/step separado fica para quando métricas de retrieval exigirem (docs 10/12).  
> **Prioridade: P0**  
> **Domínio: Data Model / Funnel**

## Problema

Empresa encontrada e oportunidade comercial estão sendo tratadas conceitualmente como a mesma coisa. Isso dificulta controlar custos, métricas de retrieval e critérios de promoção.

## Objetivo

Introduzir uma etapa explícita de `Candidate`, promovida para `Lead` somente após qualificação mínima.

## Mudança proposta

Candidate deve guardar identidade e sinais baratos: nome, IDs de fonte, domínio, social, telefone, rating, volume de avaliações, categoria, localização, `source_queries`, `discovery_score` e estado da coleta. Lead representa entidade já promovida para o funil comercial.

## Fluxo esperado

```text
Found company
    ↓
Candidate
    ↓ pre-score / dedup / exclusion
promote?
    ├─ não → archived/rejected candidate
    └─ sim → Lead
```

## Implementação sugerida

A migração pode iniciar logicamente antes de criar uma nova tabela: usar estado explícito no pipeline. Se criar entidade nova, manter ligação `candidate_id -> lead_id` e idempotência na promoção.

## Critérios de aceite

- Métricas distinguem encontrados, candidatos, enriquecidos, qualificados e prospectados.
- Promover o mesmo candidate duas vezes não cria leads duplicados.
- Candidato reprovado não entra no funil comercial.

## Testes mínimos

- Idempotência de promoção.
- Dedup entre múltiplas fontes antes da criação do Lead.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
