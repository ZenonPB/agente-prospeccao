# Controlled Learning

> **LIVE · atualizado em 2026-09-14.** O learning é deliberadamente
> human-in-the-loop. Nenhuma mudança de scoring/oferta entra em produção por
> efeito colateral de feedback, outcome ou relatório de calibração.

## Fluxo canônico

```text
CommercialOutcome atribuído + feedback humano
        ↓
relatório de calibração por oferta
        ↓
gates mínimos de amostra + wins + atribuição
        ↓
candidato conservador de OfferProfile
        ↓
replay histórico no mesmo conjunto observado
        ↓
CommercialComparison conclusiva
        ↓
aprovação humana explícita + evidência
        ↓
ControlledLearningProposal com snapshot candidato imutável
        ↓
publicação humana explícita
        ↓
OfferProfileVersion ativa no workspace
        ↓
build_effective_registry(org)
        ↓
próximos jobs do pipeline
        ↓
rollback para snapshot histórico, se necessário
```

## Invariantes

- aprendizado é isolado por `organization_id`;
- apenas `CommercialOutcomeRow` atribuído a `lead_opportunity_id` entra no replay de calibração;
- proposta não altera o registry ativo;
- sinal ausente permanece `UNKNOWN`; o replay não converte ausência em `FALSE`;
- publicação gera versão/auditoria e mantém snapshot imutável;
- se a comparação possui candidato persistido, a publicação aceita somente aquele snapshot exato;
- só uma versão ativa da mesma oferta por workspace;
- rollback restaura snapshot conhecido, não recalcula uma aproximação;
- histórico de oportunidades/outcomes preserva a versão usada na época;
- amostra insuficiente bloqueia a proposta automática de calibração;
- feedback humano é evidência contextual, não comando automático de produção;
- associação estatística nunca é apresentada como causalidade.

## Calibração e replay — Bloco C

`LearningCalibrationService` fecha o ciclo técnico antes incompleto.

O relatório por oferta mede:

- oportunidades com outcome efetivamente atribuído;
- taxa de atribuição do conjunto de outcomes;
- respostas, reuniões e wins por sinal observado;
- feedback de utilidade e correções humanas de score como contexto adicional;
- tamanho de amostra e número de wins.

Por padrão, uma oferta só fica elegível para geração de candidato quando há pelo
menos 20 oportunidades observadas, no mínimo `max(2, ceil(n*0.10))` wins e pelo
menos 80% dos outcomes atribuídos. Esses valores são gates de segurança do
produto, não promessa estatística universal; continuam visíveis no relatório e
podem ser endurecidos quando houver volume real maior.

O candidato altera apenas pesos de sinais positivos existentes e limita cada
mudança a ±25% por ciclo. Ele não inventa sinais, não promove hipótese a fato e
não publica nada. Em seguida o replay reavalia o perfil atual e o candidato sobre
o mesmo histórico factual e calcula, no `top_k` configurado:

- precision de reply;
- precision de meeting;
- precision de win;
- recall de meeting;
- recall de win;
- score médio e movimentações de ranking.

A comparação só é persistida como candidata à mudança quando o replay produz
veredito conclusivo a favor da nova versão sem regressão material nos gates de
proteção. Resultado inconclusivo ou pior mantém o perfil atual.

## Aprovação, publicação e rollback

A aprovação de `CommercialComparison` continua restrita a manager. A aprovação
gera uma `ControlledLearningProposal`, que agora carrega também o snapshot exato
do candidato avaliado pelo replay.

Publicar é uma segunda ação explícita. O servidor não confia em um profile
substituído pelo browser: se existe snapshot candidato persistido, qualquer
payload diferente é rejeitado. A versão publicada vira `OfferProfileVersion`
tenant-scoped e o pipeline passa a consumi-la via `build_effective_registry`.

Rollback é igualmente explícito e reativa um `OfferProfileVersion` histórico
persistido. O conteúdo não é recalculado.

## Coaching comercial — Bloco C

`CommercialCoachingService` transforma os dados operacionais já canônicos em
coaching sem criar uma segunda fonte de verdade. Ele usa:

- responsável atual do `Lead`;
- `LeadActivity` para primeiro contato e proposta enviada;
- `CommercialOutcomeRow` para reply/meeting/win;
- `next_action_at` para follow-ups vencidos.

Os diagnósticos atualmente cobrem follow-up SLA, associação entre primeiro
contato em até 24h e reuniões, e conversão reunião → proposta. Recomendações só
aparecem quando existe amostra mínima para a regra correspondente e incluem a
evidência numérica que as originou. A interface e a API marcam explicitamente
que associação observada não prova causalidade.

## Runtime efetivo

Antes de `run_pipeline`, o job materializa `build_effective_registry(db,
organization_id)` e liga o registry à tarefa via `ContextVar`. Assim discovery,
pre-scoring, enrichment, scoring, matcher e resolução de decisor que usam o
registry durante o job recebem o overlay publicado daquela organização.

Jobs concorrentes de A e B não compartilham o mesmo contexto. A construção do
registry também sempre parte do catálogo base, impedindo contaminação entre
tenants.

## Fontes de feedback

- `LeadUsefulnessFeedback`: útil/não útil + motivo fechado;
- `ScoringFeedback`: correção humana do score + justificativa;
- `CommercialOutcomeRow`: resultado real atribuído à oportunidade/oferta/versão;
- sinais de provider/cobertura/custo: úteis para estratégia, sem reescrever
  silenciosamente pesos comerciais.

## Gates formais do Bloco C

O CI possui um gate PostgreSQL real específico que prova, no mesmo cenário:

1. calibração somente com outcomes atribuídos e isolamento contra outro tenant;
2. geração de candidato versionado;
3. replay histórico com melhoria mensurável no ranking;
4. aprovação humana da comparação;
5. persistência do snapshot candidato na proposta;
6. publicação sem permitir troca silenciosa do candidato;
7. consumo pelo registry efetivo do tenant correto;
8. rollback ao baseline conhecido;
9. coaching tenant-scoped com recomendação ligada a evidência.

## O que permanece fora deste bloco

Bloco C fecha o produto técnico de learning/calibração/coaching. Ele **não**
substitui o Bloco D: ainda é necessária validação operacional real multi-workspace
e campanhas reais da AlphaMec para medir conversão no mundo real. CI verde prova
invariantes de software e comportamento sobre dados de teste; não prova aumento
de contratos.

## O que não fazer

- editar `default_profiles.py` como reação automática a feedback;
- usar `CampaignScoringTemplate` como segundo loop concorrente de learning;
- publicar alteração sem evidência e aprovação;
- misturar outcomes de oportunidades diferentes do mesmo lead;
- comparar versões sem preservar a versão usada em cada observação;
- transformar associação de coaching em afirmação causal.
