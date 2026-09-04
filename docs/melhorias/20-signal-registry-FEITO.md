# Signal Registry universal

> **Status: ✅ FEITO — registry universal com chaves canônicas `SignalKey`, metadados, fábrica com regras epistêmicas (FACT exige fonte+evidência) e merge de providers com dedup semântico de evidência.  
> **Prioridade: P0**  
> **Domínio: Architecture / Evidence**

## Problema

Sinais de negócio estão espalhados por templates, relatórios e prompts, dificultando reuso e consistência entre verticais.

## Objetivo

Criar um registro universal de sinais observáveis, com semântica, fonte, valor, confiança, data e evidência.

## Mudança proposta

Exemplos: `NO_WEBSITE`, `GOOGLE_REVIEW_COUNT`, `COMPANY_SIZE`, `CNAE`, `HAS_CUSTOMER_PORTAL`, `HAS_CNC`, `HIRING`, `EXPANDING`, `NEW_EQUIPMENT`, `DECISION_MAKER_FOUND`, `VERIFIED_EMAIL`. Verticais aplicam pesos/interpretações diferentes ao mesmo signal.

## Contratos / modelo de dados

```json
{
  "key": "NEW_BRANCH",
  "value": true,
  "source": "company_site",
  "confidence": 0.88,
  "observed_at": "2026-09-03T10:00:00Z",
  "evidence": "..."
}
```

## Critérios de aceite

- Signal possui fonte e confiança.
- Mesmo signal pode ter peso distinto por profile.
- Facts e inferências são distinguíveis.

## Testes mínimos

- Dois providers podem contribuir evidência para o mesmo signal sem duplicar semanticamente.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
