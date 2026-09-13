# Controlled Learning

> **LIVE · atualizado em 2026-09-13.** O learning é deliberadamente
> human-in-the-loop. Nenhuma mudança de scoring/oferta entra em produção por
> efeito colateral de feedback ou outcome.

## Fluxo canônico

```text
feedback + CommercialOutcome
        ↓
análise / comparação por oferta + versão
        ↓
CommercialComparison / evidência
        ↓
proposta de alteração
        ↓
aprovação humana explícita
        ↓
OfferProfileVersion publicada no workspace
        ↓
build_effective_registry(org)
        ↓
próximos jobs do pipeline
```

## Invariantes

- aprendizado é isolado por `organization_id`;
- proposta não altera o registry ativo;
- publicação gera versão/auditoria e mantém snapshot imutável;
- só uma versão ativa da mesma oferta por workspace;
- rollback restaura snapshot conhecido, não recalcula uma aproximação;
- histórico de oportunidades/outcomes preserva a versão usada na época;
- amostra insuficiente deve ser sinalizada, não transformada em certeza;
- feedback humano é evidência, não comando automático de produção.

## Runtime efetivo

A publicação só é útil se o pipeline realmente consumir a versão ativa do
workspace. O PR #172 fecha essa lacuna: antes de `run_pipeline`, o job materializa
`build_effective_registry(db, organization_id)` e liga o registry à tarefa via
`ContextVar`. Assim discovery, pre-scoring, enrichment, scoring, matcher e
resolução de decisor que usam `get_default_registry()` durante o job recebem o
overlay publicado daquela organização.

Jobs concorrentes de A e B não compartilham o mesmo contexto. A construção do
registry também sempre parte do catálogo base, impedindo contaminação entre
tenants.

## Fontes de feedback

- `LeadUsefulnessFeedback`: útil/não útil + motivo fechado;
- `ScoringFeedback`: correção humana do score + justificativa;
- `CommercialOutcomeRow`: resultado real atribuído à oferta/versão;
- sinais de provider/cobertura/custo: úteis para estratégia, sem reescrever
  silenciosamente pesos comerciais.

## Antes da calibração final

1. PR #172 verde e mergeado;
2. provar overlays distintos em workspaces concorrentes;
3. consolidar dashboards de feedback/outcomes por oferta/versão;
4. definir amostra mínima e intervalos/qualidade suficientes;
5. UAT com AlphaMec;
6. apenas então aprovar ajustes de pesos/thresholds no fluxo versionado.

## O que não fazer

- editar `default_profiles.py` como reação automática a feedback;
- usar `CampaignScoringTemplate` como segundo loop concorrente de learning;
- publicar alteração sem evidência e aprovação;
- misturar outcomes de oportunidades diferentes do mesmo lead;
- comparar versões sem preservar a versão usada em cada observação.
