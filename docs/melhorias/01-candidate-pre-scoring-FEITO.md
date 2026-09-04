# Candidate Pre-Scoring antes do enriquecimento pesado

> **Status: ✅ FEITO — pré-scoring determinístico sem LLM implementado** (`candidate_pre_scoring_service.py`): sinais FACT, pesos por template, gate no pipeline e descartes auditados em `prescoring_discards` (reason + upsert idempotente). Detalhes: `00-diagnostico-fase-1.md`. Evoluções futuras (métricas de retrieval, painel de descartes) seguem nos docs 10/12.  
> **Prioridade: P0**  
> **Domínio: Discovery / Ranking**

## Problema

A coleta atual pode promover resultados do Google Places diretamente para etapas caras. A relevância do Google não representa qualidade comercial: um estabelecimento pode aparecer bem ranqueado e ainda ser um prospect ruim para a oferta.

## Objetivo

Criar uma camada determinística, barata e explicável que ranqueie candidatos com dados já disponíveis antes de CNPJ, auditoria técnica, LLM e enriquecimento de contatos.

## Mudança proposta

Adicionar um `CandidatePreScoringService` que receba dados brutos de descoberta e devolva `discovery_score`, fatores positivos/negativos e motivo resumido. Os pesos devem ser configuráveis por vertical, não universais. Para Landing Pages, sinais iniciais podem considerar ausência de site próprio, Instagram, reputação Google, volume de avaliações, telefone, independência e qualidade aparente do site.

## Fluxo esperado

```text
Discovery provider
    ↓
Candidate normalizado
    ↓
CandidatePreScoringService
    ↓
ranking barato
    ↓
top candidatos / threshold
    ↓
enriquecimento pesado
```

## Contratos / modelo de dados

```json
{
  "candidate_id": "...",
  "discovery_score": 82,
  "score_factors": [
    {"signal": "NO_OWN_WEBSITE", "impact": 25, "evidence": "..."}
  ],
  "eligible_for_enrichment": true
}
```

## Implementação sugerida

Não chamar LLM no pre-score. Resolver pesos a partir do perfil/vertical da campanha. Persistir evidência suficiente para explicar por que um candidato foi promovido ou descartado. Coletar mais candidatos do que a quantidade final solicitada e só então cortar pelo ranking.

## Critérios de aceite

- O pipeline consegue coletar N candidatos e enriquecer somente uma fração configurável deles.
- O score é reproduzível para a mesma entrada e configuração.
- Cada impacto do score possui um sinal/evidência identificável.
- Landing Pages pode usar pesos diferentes de ERP e Engenharia.
- Candidatos descartados não consomem chamadas de enriquecimento pesado.

## Testes mínimos

- Sem site + Instagram + boa reputação deve superar sem site + zero presença digital em Landing Pages.
- Franquia/rede pode reduzir score quando a vertical configurar esse sinal.
- Mudança de pesos do perfil altera ranking sem mudar código do serviço.

## Riscos / considerações

- Não transformar os pesos iniciais em regras eternas; calibrar com outcomes reais.
- Evitar usar sinais que exigem enriquecimento caro nesta fase.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
