# Contexto do projeto

> **LIVE · atualizado em 2026-09-18.** Baseline: `main@446ca886f4a22addc672df9355ea59972bc86e2a`.

## Produto

Prospect.ai é uma plataforma multi-workspace de inteligência comercial + CRM. O primeiro cliente operacional é a AlphaMec/Empresa Júnior. O núcleo permanece genérico: diferenças entre ofertas pertencem ao `OfferProfile` efetivo (Vertente), não ao core.

Fluxo alvo da 1.0:

`definir oferta → descobrir → reunir evidências → qualificar/explicar → identificar pessoa/contato → priorizar → trabalhar no CRM → fechar/perder → aprender`.

## Estado atual

Estão tecnicamente entregues: multi-workspace/RBAC, Company/Person/Lead/LeadOpportunity canônicos, Vertentes versionadas por organização, discovery federado, Brazil Company Registry, entity resolution, pre-scoring, enrichment, scoring/OfferMatcher, Public Web, People/Contact, Next Best Action, tasks/sequences/workflows, CRM 360/Kanban, historical importer, BI/Filter Context, outcomes/feedback e controlled learning.

As PRs #203–#207 fecharam o hardening estrutural recente do Registry: compatibilidade de identificador, staging e ativação transacional, membership por snapshot, health/provenance, write-amplification e `scope` persistido.

O Data Engine é **CODE COMPLETE / OPERATIONAL VALIDATION REQUIRED**. Não há ainda prova com snapshot oficial real no cenário congelado. Fixtures e benchmarks sintéticos não substituem essa etapa.

## Freeze AlphaMec 1.0

Não ampliar horizontalmente o produto antes de fechar o Golden Path. Escopo obrigatório restante:

1. piloto real do Data Engine;
2. consolidar Evidence Contract sem criar fonte paralela;
3. evoluir a inteligência existente para AI Commercial Analyst explicável por Vertente;
4. garantir persistência learning-ready;
5. E2E real de empresa → evidência → oportunidade → pessoa/contato → CRM;
6. corrigir P1/P2 reais;
7. hardening, deploy e smoke AlphaMec.

Ficam fora do caminho crítico: BigQuery produtivo, Autopilot, Relationship Intelligence/omnichannel avançado, Meeting/Proposal Intelligence, billing SaaS, scheduler nacional sofisticado e expansão não necessária de providers/Vertentes.

## Data Engine — próximo passo

Primeiro piloto: Landing Pages → clínicas de psicologia → Araraquara/SP → CNAE 8650-0/03 → ativas. Sem outreach, sem provider pago e com Commercial Dimensions em shadow.

Enquanto o operador estiver sem acesso ao computador, só podem ser concluídos honestamente contratos, testes/fixtures, revisão estática, documentação e preparação operacional. Compatibilidade do snapshot, cobertura real, tamanho/tempo real e qualidade real dependem dos arquivos oficiais.

O procedimento está em `docs/data-engine-real-pilot-runbook.md`.

## Invariantes

- tenant isolation é boundary de segurança;
- catálogo base + overlay publicado formam a Vertente efetiva;
- `UNKNOWN != FALSE`;
- FACT/INFERENCE/HYPOTHESIS não se confundem;
- provenance/confidence/timestamps são preservados;
- provider pago é opt-in e budget é fail-closed;
- Registry é universo de descoberta, não CRM;
- Company/Person/Lead/LeadOpportunity continuam canônicos;
- learning nunca publica silenciosamente;
- snapshot COMPLETED não é ACTIVE;
- snapshot filtrado precisa declarar seu scope;
- nenhuma métrica real é inferida de benchmark sintético.

## Regra de implementação

Branch curta, PR vertical, inventário antes de entidade nova, migrations aditivas, jobs longos fora de request, segurança/tenant tests, sem N+1, UI comercial sem jargão técnico e todos os gates verdes no mesmo HEAD.
