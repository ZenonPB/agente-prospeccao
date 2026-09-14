# OfferProfile — contrato e runtime

> **LIVE · atualizado em 2026-09-13.** O perfil de oferta é a fonte declarativa
> de inteligência específica de cada serviço. O engine deve permanecer genérico.

## Responsabilidade

Um `OfferProfile` descreve, conforme disponível:
- identidade da oferta (`key`, versão, archetype/vertical, nome/tagline);
- ICP, geografia e exclusões;
- estratégia/providers/budgets de discovery;
- pre-scoring e thresholds;
- enrichment e people discovery;
- sinais positivos/negativos/disqualifiers + pesos;
- intent/timing;
- decision makers/buyer roles;
- canais;
- qualificação;
- outreach/evidence requirements.

## Catálogo base e versões por workspace

`services/prospecting/default_profiles.py` constrói o catálogo base. Ele é
fallback e não deve ser mutado em runtime.

Publicações controladas são persistidas em `OfferProfileVersion` com
`organization_id`. Para cada `key`, a versão ativa do workspace sobrepõe a
mesma chave do catálogo base.

```text
base registry
   + active OfferProfileVersion(org)
   ↓
build_effective_registry(db, org)
   ↓
effective registry
```

Perfis publicados inválidos não entram silenciosamente no runtime.

## Runtime do pipeline

Antes do PR #172, partes do pipeline ainda chamavam `get_default_registry()` e
podiam usar o catálogo global mesmo quando o workspace possuía overlay
publicado. Isso era aceitável para compatibilidade inicial, mas bloqueava a
calibração final.

No PR #172:

1. `jobs_consumer` materializa `build_effective_registry` para o
   `organization_id` do job;
2. o registry é ligado à tarefa via `ContextVar`;
3. consumidores existentes de `get_default_registry()` recebem o registry
   efetivo durante aquele job;
4. ao sair do contexto, o catálogo base é restaurado;
5. jobs concorrentes não compartilham estado;
6. `build_effective_registry` usa sempre `get_base_registry()` para impedir que
   o overlay A seja reutilizado ao construir B;
7. falha ao montar o registry faz o job falhar fechado.

Esse mecanismo é de compatibilidade do runtime. Novos serviços que já possuem
`db + organization_id` podem preferir `build_effective_registry` ou
`get_effective_profile` explicitamente.

## Resolução de campanha

A campanha pode armazenar `offer_profile_key`. Quando ausente, o resolver usa
`target_service`/`target_segment` e pode cair em perfil genérico. Uma chave
explícita deve existir no registry efetivo da organização.

## Versionamento, snapshots e attribution

- cada oportunidade persiste `offer_key` e `offer_version`;
- re-scoring gera histórico em `LeadOpportunitySnapshot`;
- outcomes/conversões apontam para oportunidade/snapshot quando disponível;
- mudanças futuras no perfil não reescrevem o contexto histórico de uma venda;
- learning compara versões com amostra/evidência e publicação explícita.

## Vertente / CampaignScoringTemplate

`CampaignScoringTemplate` ainda existe por compatibilidade e por capacidades
operacionais como cadência/roteamento legado. A direção de consolidação é:

- ICP, sinais, pesos, thresholds, providers, buyer persona, timing e learning
  pertencem ao OfferProfile;
- cadência/operational playbook pode continuar separado enquanto houver regra
  clara e sem duas fontes conflitantes;
- não criar um segundo loop de calibração concorrente com OfferProfile.

Veja `roadmap.md` para o plano corrente.

## Segurança e testes obrigatórios

- profile de A nunca aparece em B;
- versões ativas são filtradas por `organization_id`;
- dois jobs concorrentes com overlays distintos enxergam registries distintos;
- saída de um contexto restaura o registry anterior;
- registry efetivo sempre começa no catálogo base, não no contexto corrente;
- nenhuma mudança de learning entra em produção sem aprovação/publicação.
