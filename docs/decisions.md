# Decisões arquiteturais atuais

> **ADR/DECISÃO · atualizado em 2026-09-13.** ADRs históricos em `docs/adr/`
> permanecem imutáveis. Este arquivo registra as decisões transversais vigentes.

## D01 — Multi-workspace é boundary de segurança

`organization_id` faz parte do contrato de autorização. Recursos raiz são
carregados por id + organização, relações são revalidadas e UUID conhecido de
outro tenant não concede visibilidade. CONSULTOR ainda tem escopo de carteira.

## D02 — Company/Person/Lead são entidades distintas

- Company = conta canônica;
- Person = pessoa canônica;
- Lead = contexto de prospecção/venda/campanha;
- LeadOpportunity = oferta específica aplicável ao Lead.

Não colapsar esses conceitos para simplificar tela/import.

## D03 — OfferProfile é a fonte declarativa da inteligência da oferta

ICP, sinais, pesos, thresholds, discovery strategy, enrichment, buyer persona,
intent/timing e regras específicas da oferta vivem no OfferProfile.

## D04 — OfferProfile publicado por workspace precisa chegar ao runtime inteiro

Catálogo base é fallback; versão ativa da organização é overlay. PR #172 usa
registry efetivo + `ContextVar` do job para compatibilidade com consumidores
legados sem estado global mutável.

## D05 — Learning é human-in-the-loop

Outcome/feedback produzem análise/proposta. Produção muda somente após aprovação
e publicação versionada. Rollback restaura snapshot exato.

## D06 — Timeline é derivada, não uma nova fonte de verdade

Telas 360 normalizam Activity/Task/Outcome/Sequence/Workflow/Feedback existentes.
Não criar tabela Timeline só para UI.

## D07 — CRM interno é canônico; adapters externos são integrações

Pipedrive/HubSpot/Salesforce não comandam silenciosamente o estado interno. Sync
é idempotente, conservador, org-scoped e auditável.

## D08 — Não criar Proposal/Contract/Note sem ciclo de vida comprovado

Enquanto status/atividade/outcome/Lead.notes atendem, não adicionar entidades
apenas para paridade visual com CRM externo. UAT decide a necessidade.

## D09 — Jobs longos não rodam presos ao request

Pipeline é agendado em `Job`, consumido com claim concorrente seguro e expõe
progresso/estado persistido. Restart/stale job têm tratamento explícito.

## D10 — Providers externos são opt-in e governados por custo/quota

Discovery/enrichment usa adapters/federation. Provider caro deve vir após gates
baratos. Telemetria de status/latência/custo/cobertura é obrigatória.

## D11 — UNKNOWN não é FALSE

Ausência de evidência não é evidência negativa. FACT, INFERENCE, HYPOTHESIS e
UNKNOWN permanecem separados no motor e na explicação ao usuário.

## D12 — Outcome é atribuído à oportunidade correta

Uma Company/Lead pode ter múltiplas ofertas. Conversão/outcome deve guardar
`lead_opportunity_id`, versão/snapshot quando disponível. Métrica sem attribution
é explicitamente `unattributed`.

## D13 — Planilha histórica é entrada de migração, não fonte operacional

Importação deve ter preview, mapping, validação, dedupe, confirmação,
idempotência e relatório. Depois da migração, o CRM interno é fonte de verdade.

## D14 — CI do mesmo HEAD é gate de merge

Não aceitar suíte vermelha por ser “pré-existente”. Corrigir ou provar isolamento
correto do teste. Backend, migrations/Postgres, E2E e web precisam estar verdes
no commit que será mergeado.

## D15 — Documentação tem hierarquia explícita

`docs/README.md` classifica LIVE, RUNBOOK e ADR. Histórico de fases antigas
vive no git, não na pasta; estado atual fica nos LIVE docs.
