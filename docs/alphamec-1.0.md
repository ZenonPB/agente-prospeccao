# AlphaMec 1.0 — baseline, freeze e reta final

> **LIVE · baseline 2026-09-18.** Base técnica: `main@446ca886f4a22addc672df9355ea59972bc86e2a` (merge da PR #207).
> Código, migrations e testes prevalecem se houver divergência.

## Objetivo da 1.0

Entregar à AlphaMec um fluxo operacional completo e confiável:

`definir o que vende → encontrar empresas → reunir evidências → explicar por que abordar → encontrar pessoa/contato → trabalhar no CRM → registrar outcome → aprender de forma controlada`.

A 1.0 entra em **feature freeze horizontal**: não ampliar o produto com capacidades paralelas antes de provar o Golden Path real. O foco passa de “construir mais módulos” para “fechar verticalmente o caminho que a AlphaMec realmente usa”.

## Baseline técnico

Já existe e não deve ser reconstruído em paralelo:

- multi-workspace, membership, RBAC e isolamento tenant;
- Company, Person, Lead e LeadOpportunity canônicos;
- Vertente = OfferProfile efetivo por organização;
- discovery federado e `cnae_discovery` com Registry opt-in/fallback/shadow;
- Brazil Company Registry com staging, ledger, manifest, scope, membership versionado e ativação explícita;
- entity resolution, aliases e provenance;
- pre-scoring, enrichment, scoring, OfferMatcher e snapshots;
- Public Web Intelligence passiva e segura;
- Commercial Dimensions em shadow;
- People/Contact Intelligence e waterfall com budget guard;
- Next Best Action, tarefas, sequences/workflows, Kanban e CRM 360;
- outcomes, feedback, analytics, controlled learning, replay, aprovação, publicação e rollback;
- UAT multi-workspace, production rehearsal e gates de CI.

“Implementado” ou “validado tecnicamente” não significa “validado operacionalmente”. Snapshot real, providers reais e outcomes reais continuam sendo evidência externa obrigatória quando aplicável.

## Estado do Data Engine no freeze

As PRs #203–#207 fecharam o hardening estrutural do Registry: compatibilidade de identificador, staging/ativação transacional, membership por snapshot, health/provenance, redução de write amplification e persistência explícita do escopo. O Data Engine está **CODE COMPLETE no contrato atual e OPERATIONAL VALIDATION REQUIRED**.

O bloqueador para declarar o Registry operacional é o primeiro snapshot oficial real + piloto controlado. Até isso ocorrer:

- Registry não é chamado de validado em produção;
- Commercial Dimensions continua shadow;
- não se promove BigQuery/remote discovery para provider produtivo;
- não se declara cobertura/precision/conversão real;
- não se inicia outreach no piloto do Registry.

## Escopo obrigatório restante para AlphaMec 1.0

### A. Real Data / Data Engine
Importar snapshot oficial, validar parser/layout/manifest, ativar recorte controlado, medir busca, revisar falsos positivos, duplicatas, CNAE principal/secundário, performance, armazenamento e provenance.

### B. Evidence Contract
Auditar e consolidar o contrato já existente para que fatos, inferências, hipóteses, confiança, origem e `observed_at` sejam rastreáveis ponta a ponta. Não criar `EvidenceV2` ou tabela paralela sem provar lacuna real.

### C. AI Commercial Analyst
Evoluir a inteligência existente, sem criar segundo motor, para produzir análise comercial estruturada e explicável por Vertente: aderência, hipóteses, contraevidências, unknowns, “por que esta empresa”, “por que esta oferta”, “por que agora” e ângulo recomendado. LLM entra depois de filtros baratos e recebe evidências, não conclusões fabricadas.

### D. Learning-ready persistence
Garantir que oportunidade/análise preserve versão da Vertente, evidências, versão de policy/prompt/model quando aplicável, timestamps, score/snapshot e attribution de outcomes. O controlled learning existente continua human-in-the-loop.

### E. Real E2E
Executar o Golden Path completo com empresas reais: discovery → evidence → análise → oportunidade → pessoa → contato → CRM. Outreach só entra depois da validação de dados e autorização operacional.

### F. Production hardening e deploy
Corrigir P1/P2 encontrados no E2E, validar migrations/backup/restore/secrets/quotas/budget/observabilidade, executar gates no mesmo HEAD e fazer smoke do ambiente AlphaMec.

## Fora do caminho crítico da 1.0

Ficam congelados salvo P1/P2 que bloqueie o Golden Path: BigQuery produtivo, novo Market Learning Engine, Autopilot, Relationship Intelligence, omnichannel avançado, WhatsApp automático, Meeting Intelligence, Proposal Intelligence, billing SaaS, scheduler nacional sofisticado, novos CRMs, novas Vertentes não necessárias ao piloto e redesign não bloqueante.

## Regra de decisão

Uma mudança entra antes da 1.0 somente se satisfizer pelo menos um critério:

1. desbloqueia o Golden Path AlphaMec;
2. corrige P1/P2 de segurança, integridade, tenancy ou dados;
3. torna o Data Engine real testável/operável;
4. preserva evidência necessária ao learning futuro;
5. reduz risco operacional de deploy sem criar subsistema paralelo.

Caso contrário, vai para pós-1.0.

## Sequência

1. fechar preparação offline do Data Engine;
2. executar piloto real em casa;
3. corrigir apenas achados reais P1/P2;
4. auditar Evidence → Scoring → OfferMatcher → Opportunity Snapshot;
5. consolidar AI Commercial Analyst;
6. fechar persistência learning-ready;
7. E2E real AlphaMec;
8. hardening, deploy e smoke;
9. uso real e coleta de outcomes.

A partir deste baseline, o objetivo não é aumentar a quantidade de features: é reduzir a distância entre código tecnicamente maduro e operação comercial comprovada.
