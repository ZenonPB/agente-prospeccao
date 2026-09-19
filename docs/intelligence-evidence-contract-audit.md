# Auditoria ponta a ponta — Intelligence Evidence Contract

> **LIVE/AUDITORIA · 2026-09-18.** Base auditada: `main@f61e7f0` após merge da PR #208.
> Objetivo: capinar o caminho de inteligência antes do AI Commercial Analyst, sem depender de dados reais.

## Fluxo auditado

`RegistryCandidate → entity resolution → Company/Lead → enrichment/web → Signal Registry → scoring → Opportunity Vector → OfferMatcher → LeadOpportunity → LeadOpportunitySnapshot → People/Contact → outcome/learning`.

## O que já é sólido

- `Signal Registry` já possui contrato epistêmico explícito: key/value/source/confidence/observed_at/evidence/evidence_refs/epistemic/contributing_sources.
- FACT sem fonte/evidência é rebaixado; UNKNOWN não aceita valor.
- scoring possui guards contra claims de site contraditórios e grounding determinístico de pitch.
- `LeadOpportunity` persiste score, versão da oferta, sinais matched/missing e breakdown.
- `LeadOpportunitySnapshot` é append-only e outcomes podem apontar para snapshot.
- OfferProfile publicado é versionado e possui snapshot completo no controlled learning.
- Commercial Dimensions continua shadow e tenta preservar UNKNOWN.
- tenant isolation e provider/budget boundaries já existem.

## Lacunas encontradas

### P1 — `profile_snapshot_hash` não representa o snapshot do perfil

Hoje `LeadOpportunityService._snapshot_row` calcula o hash apenas de
`{"offer_version", "profile_key"}`. Duas configurações diferentes com a mesma
identidade produziriam o mesmo hash. O comentário/modelo afirma “hash do
contexto/perfil”, portanto o contrato está mais forte que a implementação.

**Correção:** calcular o hash do `OfferProfile.to_dict()` efetivo usado na
avaliação e carregá-lo até a persistência. Se o perfil exato não puder ser
resolvido, não fabricar um hash forte; usar `None`/estado explicitamente
desconhecido.

### P1 — Snapshot não captura o contexto de evidência estruturada do lead

O OfferMatcher trabalha majoritariamente com strings de sinais e o snapshot
grava `row.evidence` como lista de strings. O Signal Registry, por outro lado,
já sabe representar epistemic/source/confidence/observed_at. Assim, é possível
reconstruir “quais sinais casaram”, mas não necessariamente “qual observação
originou o sinal e quando”.

**Correção:** sem criar EvidenceV2, adicionar ao snapshot um envelope de contexto
estruturado derivado das fontes canônicas já persistidas (`lead.evidence`,
`discovery_provenance`, `evidence_score` e sinais estruturados disponíveis),
com schema/version explícitos. O snapshot deve ser imutável e participar do hash.

### P2 — Evidence de scoring perde metadados epistêmicos

`AIScoringService._normalize_response` reduz evidence para
`type/severity/title/description/source`. Mesmo que um producer devolva
confidence/observed_at/epistemic/evidence_refs, esses campos são descartados.

**Correção:** aceitar/preservar metadados válidos e classificar com prudência:
saída textual da LLM nunca vira FACT apenas porque escreveu “FACT”. FACT precisa
estar ligado a evidência determinística de entrada; caso contrário é
INFERENCE/HYPOTHESIS.

### P2 — `score_vector` mistura valor e observabilidade

O shadow precisou de `shadow_derive_input` porque zeros de fallback não têm
provenance suficiente para distinguir “medido 0” de “não medido”. Isso é dívida
real antes de um Analyst mais sofisticado.

**Correção:** não alterar o vetor produtivo agora. Introduzir contrato auxiliar
de observabilidade/versionamento no snapshot/análise, e migrar produtores
gradualmente. Nunca inferir observação pela presença da chave.

### P2 — análise LLM não possui versão persistida completa

O modelo atual conhece `GROQ_MODEL` em runtime e o vetor tem formula_version,
mas a trilha histórica da oportunidade não garante model/prompt/policy version
da análise que gerou os campos textuais.

**Correção:** antes do AI Commercial Analyst, definir `analysis_metadata`
versionado: analyzer_version, model/provider quando usado, prompt/policy
version, generated_at, offer_key/version/profile hash e evidence-context hash.
Não persistir secret nem prompt inteiro por padrão.

### P2 — duas famílias de “evidence”

Existem `Lead.evidence` (evidência do scoring), `discovery_provenance`,
`evidence_score`, Signal Registry e `LeadOpportunityRow.evidence` (strings de
sinais). Os nomes sugerem equivalência que não existe.

**Correção:** documentar semântica e criar adapters puros para um
`EvidenceContext` de leitura; não renomear tabelas nem fazer big-bang.

## Contrato alvo antes do AI Commercial Analyst

Uma análise deve conseguir responder de forma reproduzível:

1. qual organização/lead/company/oportunidade;
2. qual Vertente e versão;
3. hash do snapshot REAL do OfferProfile;
4. qual fórmula/analyzer/policy/model;
5. quais observações estavam disponíveis;
6. status epistêmico de cada afirmação;
7. source/reference, confidence e observed_at;
8. quais sinais foram matched/missing e por quê;
9. quais unknowns permaneceram;
10. qual snapshot originou eventual outcome.

## Estratégia de implementação

Não criar novo motor. Fazer micro-PRs:

- **A1:** corrigir hash real do OfferProfile + regressões;
- **A2:** adapter `EvidenceContext` puro + validação/normalização, sem migration se possível;
- **A3:** snapshots incluem evidence context + metadata versionada; migration aditiva apenas se JSONB existente não comportar contrato com clareza;
- **A4:** scoring preserva epistemic metadata e não promove LLM a FACT;
- **A5:** auditoria de Opportunity Vector observability/UNKNOWN;
- **A6:** contrato do AI Commercial Analyst sobre essas estruturas.

Cada fatia deve preservar ranking/funil e Commercial Dimensions shadow.


## Implementado nesta branch

- A1: `profile_snapshot_hash` agora tenta representar o conteúdo real do OfferProfile efetivo; resolução impossível permanece UNKNOWN.
- A2: `EvidenceContext v1` normaliza fontes existentes sem criar nova fonte de verdade e possui hash determinístico.
- A3 parcial sem migration: novos snapshots incorporam `EvidenceContext` em `signals_snapshot`, preservando o shape legado de `evidence_snapshot`; context hash participa da identidade do snapshot.
- A4: scoring preserva confidence/observed_at/evidence_refs/epistemic quando válidos e impede que claim do modelo se autopromova a FACT.
- A6 preparatório: `commercial-analysis-input-v1` define input grounded/versionado do futuro Analyst, sem chamar LLM e sem alterar ranking.

## Ainda não implementado deliberadamente

- nenhuma chamada nova de LLM;
- nenhum ranking novo;
- nenhuma promoção de Commercial Dimensions;
- nenhuma migration;
- nenhuma mudança de outreach;
- nenhuma BigQuery/provider novo;
- nenhuma tentativa de validar qualidade com dados sintéticos como se fossem reais.

O próximo passo de código, depois de gates verdes, é implementar o **output
contract** do Commercial Analyst + validator/grounding determinístico e só então
um provider LLM atrás de feature flag/budget guard.


## Commercial Analysis Output v1

A etapa seguinte foi implementada em contrato puro, ainda sem chamar provider:

- `commercial-analysis-output-v1` separa `why_company`, `why_offer`, `why_now`,
  `counter_evidence`, `unknowns`, `opportunity_hypotheses` e abordagem sugerida;
- cada claim possui epistemic/confidence/evidence_refs;
- referências que não existem no EvidenceContext de entrada são removidas;
- FACT exige referência previamente classificada como FACT;
- hipótese comercial nunca é promovida a FACT;
- input contract desconhecido falha fechado;
- output registra analyzer/policy/provider/model, Vertente/versão,
  evidence_context_hash, generated_at e analysis_hash;
- nenhuma dessas estruturas altera ranking, score ou Commercial Dimensions.

### Próxima fronteira

Somente após este contrato passar nos gates: adapter de provider LLM + prompt
versionado + parser estrito, atrás de feature flag/access policy/budget guard.
A persistência do output deve ser aditiva e ligada ao snapshot da oportunidade,
preservando outcome attribution. Não ligar geração automática em massa antes do
piloto controlado.
