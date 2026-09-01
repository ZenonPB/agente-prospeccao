# Feedback loop de scoring — "IA que aprende com o time"

> Plano vivo da feature de feedback humano sobre o score da IA. Atualizar este
> documento a cada fase concluída. Status geral: **Fase 1 concluída · Fase 2 a fazer**.

## Objetivo

Permitir que o time corrija o score dado pela IA (ex.: "IA deu 85, mas o site é
bom/atualizado — deveria ser ~40") e que essas correções **calibrem a IA ao
longo do tempo**. Não há retreino de modelo (Groq é API fechada): o
"aprendizado" é memória contextual — feedback vira regras explícitas por
vertical/organização, injetadas no prompt de scoring.

## Arquitetura da solução

```
Usuário discorda do score (UI)
        │  score sugerido + motivo em texto livre
        ▼
ScoringFeedback (tabela)  ──►  correção imediata no lead (opcional, auditable
        │                        via LeadActivity SCORE_FEEDBACK)
        ▼  (N feedbacks acumulados por template/org)
Compilação LLM (modelo barato de classificação)
        │  3–6 regras objetivas, ex.: "sites atualizados pesam MENOS em
        │  campanhas de redesign; sites amadores pesam MAIS"
        ▼
TemplateLearning (tabela, por template × organização)
        │
        ▼
build_prompt() injeta as regras como "Ajustes aprendidos com o time"
        │
        ▼
Scoring futuro calibrado → botão "Aplicar aprendizado e reavaliar" reusa o
fluxo de reanálise existente.
```

### Decisões de desenho (o porquê)

- **Regras, não overrides cegos**: o feedback nunca substitui o score de outros
  leads automaticamente; entra como contexto de calibração e a LLM continua
  decidindo — explicável e reversível (regra pode ser descartada).
- **`TemplateLearning` separado do template**: templates globais (seed) são
  compartilhados entre orgs; o aprendizado de uma org NÃO edita o global — fica
  org-scoped na tabela de learning.
- **Cap de regras (~10)**: ao ultrapassar, as antigas são compactadas pela LLM
  para não estourar o prompt.
- **Trilha de auditoria**: todo feedback gera `LeadActivity` (`SCORE_FEEDBACK`)
  com o texto do usuário — o porquê nunca se perde.
- **Multi-tenant**: tudo org-scoped (`organization_id` em todas as tabelas).

## Fases

### Fase 1 — Coletar feedback (concluída)

- [x] Modelo `ScoringFeedback` + enums (`FeedbackDirection`, `FeedbackStatus`)
      em `services/workers/src/database/models.py` (fonte única).
- [x] Migration Alembic nova (`c3d4e5f6a7b9_score_feedback.py`) — incl. novo valor
      `SCORE_FEEDBACK` na enum `lead_activity_action`.
- [x] API: `POST /api/leads/{lead_id}/score-feedback` (campos: `suggested_score`,
      `reason`, `apply_to_lead`) e `GET /api/leads/score-feedback` (lista org-scoped,
      filtros `campaign_id`/`status`). Router registrado ANTES do router de leads
      (evita captura de `/score-feedback` pelo `/{lead_id}`).
- [x] UI: botão "Discordar do score" no menu (⋯) do card do kanban → diálogo
      com score sugerido (slider 0–100) + motivo livre (remontado por `key` por lead).
- [x] Testes `tests/test_score_feedback.py` (4): corrige score + reclassifica no
      topo do funil, não reclassifica pós-contato, direção MUITO_ALTO/BAIXO,
      rejeição de score igual.

### Fase 2 — A IA aprender (a fazer)

- [ ] Tabela `TemplateLearning` (`template_id`, `organization_id`,
      `instructions` JSONB, `updated_at`) + migration.
- [ ] Compilação: N feedbacks pendentes de um template → LLM resume em regras →
      `TemplateLearning` (endpoint manual "Sintetizar aprendizados" primeiro;
      automático depois, se fizer sentido).
- [ ] `build_prompt()` (scoring_service) aceita `learned_instructions` e injeta
      o bloco de calibração.
- [ ] `pipeline_worker` busca as regras da org ao montar o prompt de scoring.
- [ ] Botão "Aplicar aprendizado e reavaliar" na campanha (reusa reanalyze).
- [ ] Testes: compilação (mock LLM), injeção no prompt, cap/compaction.

### Fase 3 — Visibilidade (a fazer)

- [ ] Painel "Aprendizados da IA" (por campanha ou configurações): feedbacks
      dados, regras ativas, descartar regra.
- [ ] BI: desvio médio |score IA − score consultor| ao longo do tempo — mede a
      convergência ("sistema vivo").

## Guardrails

1. Score 0–100 e regra de negócio `>= 60 → QUALIFICADO` permanecem leis; a
   correção imediata de um lead só muda `status` se ele ainda estiver no topo
   do funil (NOVO/ANALISADO/QUALIFICADO/DESQUALIFICADO).
2. A correção imediata NÃO recalcula `priority` (decisão da LLM).
3. Feedback é insumo; regra compilada é contexto — nunca comando determinístico
   de score no código.
4. Sem custo surpresa: compilação usa `GROQ_MODEL_CLASSIFY` + cota da org.

## Como acompanhar

- Este documento: marcar itens ao concluir.
- Código: branch `fix/kanban-criterios-ux` → PR para `main`.
- Testes: `python -m pytest tests -q` (raiz) — arquivos `test_score_feedback*`.
