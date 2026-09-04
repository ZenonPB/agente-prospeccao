# Google Places com busca multi-query

> **Status: 🟡 Proposto**  
> **Prioridade: P0**  
> **Domínio: Discovery / Google Places**

## Problema

Paginar profundamente uma única consulta tende a degradar relevância e diminuir diversidade. Consultas diferentes para subnichos podem revelar conjuntos de empresas distintos.

## Objetivo

Aumentar recall e diversidade executando várias consultas relacionadas à campanha, deduplicando por identidade do negócio antes do ranking.

## Mudança proposta

Uma campanha deve gerar/receber várias `search_queries`. O coletor executa cada consulta com limite conservador de páginas, registra `source_query` e agrega candidatos por `place_id`/identidade.

## Fluxo esperado

```text
Campaign Brief
    ↓
search_queries[]
    ↓
Google Places (query A, B, C...)
    ↓
dedup
    ↓
CandidatePreScoring
    ↓
top candidatos
```

## Implementação sugerida

Manter limite de páginas por query; ampliar cobertura por variedade semântica, não por paginação cega. Registrar quais queries encontraram cada candidato e usar isso como evidência de especialidade/subnicho.

## Critérios de aceite

- Uma campanha aceita múltiplas queries.
- O mesmo Place não vira duplicata.
- É possível auditar `source_queries` de cada candidato.
- A quantidade final é selecionada após agregação e ranking.

## Testes mínimos

- Duas queries que retornam o mesmo `place_id` produzem um candidato.
- Queries de subnicho permanecem associadas ao candidato.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
