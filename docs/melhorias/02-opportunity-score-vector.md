# Separar oportunidade em múltiplas dimensões de score

> **Status: 🟠 Parcial — contrato pronto: `leads.score_vector` (JSONB) persistido quando presente, clamp 0-100 e `overall` derivado; `qualification_score` legado intocado. Falta: LLM/pipeline produzir as dimensões; pesos de agregação por vertical.**  
> **Prioridade: P0**  
> **Domínio: Scoring**

## Problema

Uma nota única de qualificação mistura necessidade, capacidade de compra, maturidade digital, intenção e facilidade de contato. Isso dificulta explicar por que um lead é bom e pode privilegiar necessidade técnica sem representar propensão de compra.

## Objetivo

Representar a oportunidade como vetor de dimensões independentes e derivar um `overall_score` configurável por vertical.

## Mudança proposta

Introduzir, no mínimo, `need_score`, `commercial_fit_score`, `digital_maturity_score` e `contactability_score`. Na evolução universal, incorporar também `icp_fit`, `intent`, `buying_power` e `timing`. O score final deve ser calculado por estratégia da vertical.

## Contratos / modelo de dados

```json
{
  "need": 91,
  "commercial_fit": 80,
  "digital_maturity": 84,
  "contactability": 72,
  "overall": 84,
  "formula_version": "landing-page-v1"
}
```

## Implementação sugerida

Manter compatibilidade com `qualification_score` enquanto a migração ocorre: ele pode ser preenchido pelo `overall`. Registrar `formula_version`/perfil usado para auditoria. Não permitir que a LLM produza uma nota opaca sem dimensões.

## Critérios de aceite

- A API/UI expõe dimensões além do score final.
- Os pesos variam por vertical/perfil.
- O usuário consegue identificar lead com alto fit e baixa contactabilidade.
- O score legado continua disponível durante migração.

## Testes mínimos

- Comparar ranking com pesos de Landing Page e ERP para o mesmo lead.
- Garantir faixa 0–100 para cada dimensão.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
