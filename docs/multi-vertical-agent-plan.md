# Plano — Agente de Prospecção Multi-Vertical & Multi-Usuário

> Documento de execução. Complementa `product-vision.md`, `evolution-analysis.md` e `roadmap.md`.
> Objetivo: transformar a plataforma em ferramenta usável por **você, amigos e a empresa**,
> qualificando leads em **qualquer vertical** (landing pages para clínicas, engenharia mecânica, etc.).
>
> Criado em 2026-08-01. Atualizar status conforme cada item for entregue.

---

## 0. Convenções de trabalho (obrigatórias)

A cada unidade de trabalho (épico ou fatia vertical):

1. **Branch nova** a partir de `main` atualizado:
   ```bash
   git checkout main && git pull
   git checkout -b <tipo>/<slug-curto>
   ```
2. **Commits convencionais** (Conventional Commits), um commit por mudança lógica:
   - `feat(escopo): ...` — funcionalidade
   - `fix(escopo): ...` — correção
   - `refactor(escopo): ...` — sem mudança de comportamento
   - `docs: ...` — só documentação
   - `chore: ...` — tooling, seeds, housekeeping
   - `test(escopo): ...` — testes
3. **Escopos comuns**: `api`, `workers`, `web`, `db`, `auth`, `scoring`, `pipeline`, `docs`
4. **PR**: o autor do código **não** abre o PR — deixa branch pronta e funcionando; o dono do repo abre manualmente quando validar.
5. **Docs vivos**: ao fechar uma fatia, atualizar:
   - este arquivo (status da fatia)
   - `docs/context.md` (Estado atual + Próximo passo)
   - `docs/decisions.md` se houver ADR nova
6. **Nunca** commitar `.env`, chaves ou secrets. Nunca instalar deps sem perguntar.

---

## 1. Estado atual (baseline 2026-08-01)

### O que já funciona

| Camada | Capacidade |
|---|---|
| Coleta | Google Places (query textual + cidade) |
| Enriquecimento | Site passivo (SSL, CMS, SEO, load) + CNPJ (Receita/BrasilAPI) |
| Scoring | Contextual via `CampaignScoringTemplate` + Groq 8B; score ≥60 → QUALIFICADO |
| Perfis | `web_presence` vs `business_opportunity` (template pode forçar) |
| Outreach | Geração de sequência (e-mail/WhatsApp) via Groq 70B — humano envia |
| Frontend | Dashboard, campanhas, oportunidades, kanban, auth, pipeline WS |
| Templates seed | Sites, SEO, Eng. Mecânica, Automação, Petshops, Academias, Farmácias, Consultoria, Genérico |

### O que impede multi-pessoa / multi-vertical de verdade

| Gap | Impacto |
|---|---|
| Isolamento de dados incompleto | JWT existe, mas leads/métricas/pipeline **não** filtram por dono — vazamento entre usuários |
| `Lead.place_id` unique global | Dois usuários não podem prospectar o mesmo place |
| Sem Organization/workspace | Amigos e empresa não compartilham com papéis |
| Match de template exato | “Landing pages para clínicas” cai no Genérico |
| Só fonte Places | Fraco para B2B industrial / serviços sem vitrine no Maps |
| API keys em pool único | Quota esgota com vários usuários |
| Sem feedback score↔conversão | Qualificação não melhora com uso |
| UX de “CRM de campanha”, não de agente | Usuário monta tudo à mão |

---

## 2. Norte do produto

```
Usuário/Org descreve oferta + ICP em linguagem natural
        ↓
Agente: fontes + perfil + template (ou gera) + query de coleta
        ↓
Coleta multi-fonte → enriquecimento adaptativo
        ↓
Score explicável no contexto DA oferta
        ↓
Outreach personalizado (humano no loop)
        ↓
Resultado real (ganhou/perdeu) → calibra próximo ciclo
```

**Não é spam. Não é Apollo clone.** É assistente B2B BR (CNPJ, WhatsApp, LGPD, passivo).

---

## 3. Fases de execução

Estimativas em **semanas de foco** (1 dev). Ordem é sequencial por dependência; fatias internas de uma fase podem paralelizar front/back se combinado.

```
Fase A (P0) ──► Fase B (P0/P1) ──► Fase C (P1) ──► Fase D (P2) ──► Fase E (P2/P3)
 multi-tenant     templates          agente NL        fontes          feedback +
 isolamento       inteligentes       campanha         extras          cadência
 ~1–2 sem         ~1–1.5 sem         ~1 sem           ~1.5–2 sem      ~1.5–2 sem
```

---

## Fase A — Multi-tenant e isolamento (P0) ⬜

**Por quê primeiro:** sem isso, abrir para amigos/empresa é inseguro e os dados se misturam.

**Branch sugerida:** `feat/org-multi-tenant`

### A1. Modelo Organization + Membership ⬜

| Item | Detalhe |
|---|---|
| **O quê** | Tabelas `organizations`, `organization_members` (role: `owner` \| `admin` \| `member`) |
| **Como** | Migration Alembic nova; model em `services/workers/src/database/models.py`; reexport API |
| **Campos org** | `id`, `name`, `slug`, `created_at` |
| **Membership** | `org_id`, `user_id`, `role`, unique `(org_id, user_id)` |
| **Onboarding** | No `register`: criar org pessoal automática (`"{name}'s workspace"`) + membership owner |
| **Commit** | `feat(db): add organizations and memberships` |

### A2. Ownership em Campaign / Job / Lead ⬜

| Item | Detalhe |
|---|---|
| **O quê** | `Campaign.organization_id` (FK, not null após backfill); leads herdam via campaign |
| **Como** | Migration: add nullable → backfill a partir de `campaign.user_id` → set not null; índice |
| **Lead** | Manter `campaign_id`; **não** duplicar `user_id` no lead se sempre via campaign — filtrar por join |
| **place_id** | Trocar unique global por `UniqueConstraint("organization_id", "place_id")` — exige `organization_id` no Lead **ou** constraint via subquery/partial. Preferência: `Lead.organization_id` denormalizado no insert (preenchido na coleta) para índice simples |
| **Commit** | `feat(db): scope campaigns and leads to organization` |

### A3. Isolamento na API ⬜

| Item | Detalhe |
|---|---|
| **O quê** | Toda listagem/detalhe/mutate filtra pela org do usuário atual |
| **Como** | Helper `get_user_org_ids(user)` + dependency `require_org_access(campaign_id\|lead_id)`; aplicar em `leads.py`, `campaigns.py`, `metrics.py`, `pipeline.py` |
| **Métricas** | `GET /api/metrics` só dados da org ativa |
| **Pipeline** | Job associado a campaign da org; WS só se job da org |
| **Commit** | `fix(api): enforce organization isolation on all routes` |

### A4. Org ativa no frontend ⬜

| Item | Detalhe |
|---|---|
| **O quê** | Header/switcher de workspace (mesmo que 1 org no MVP); token/JWT pode carregar `org_id` ativo ou header `X-Organization-Id` |
| **Como** | Preferir claim JWT `org_id` no login + endpoint `POST /api/auth/switch-org` se multi-org; store Zustand |
| **UI** | Configurações: nome da org; (depois) convites |
| **Commit** | `feat(web): organization context and workspace switcher` |

### A5. Convites (mínimo viável) ⬜

| Item | Detalhe |
|---|---|
| **O quê** | Owner/admin convida por e-mail → membership `member` |
| **Como** | Tabela `invites` (token, email, org_id, role, expires); e-mail via serviço existente (console fallback); `POST /api/orgs/{id}/invites`, `POST /api/invites/accept` |
| **Commit** | `feat(api,web): organization invites` |

### Critério de aceite Fase A

- [ ] Usuário A não lista/vê leads nem campanhas do usuário B (orgs distintas)
- [ ] Dois orgs podem ter o mesmo `place_id` sem erro de unique
- [ ] Registro cria org + membership
- [ ] Métricas e pipeline respeitam org
- [ ] Testes API cobrindo isolamento (pelo menos 2 cenários)

### Quando

**Início imediato** após merge deste plano. Bloqueia B–E para uso multi-pessoa real.

---

## Fase B — Templates inteligentes multi-vertical (P0/P1) ⬜

**Por quê:** sem match/geração boa, cada vertical nova degrada para Genérico.

**Branch sugerida:** `feat/smart-scoring-templates`

### B1. Router de template (fuzzy + LLM) ⬜

| Item | Detalhe |
|---|---|
| **O quê** | Dado `target_service` + `target_segment`, escolher o melhor template seed **ou** Genérico com instruções reforçadas |
| **Como** | Em `load_scoring_template` / novo `template_router.py`: (1) exact match; (2) contains/token overlap; (3) se score baixo, 1 call Groq classificando entre labels existentes + “GENERATE_NEW”; (4) cache em memória por string normalizada |
| **Commit** | `feat(scoring): route campaign to best scoring template` |

### B2. Geração de template sob demanda ⬜

| Item | Detalhe |
|---|---|
| **O quê** | Se router pedir GENERATE_NEW: LLM devolve `positive_signals`, `negative_signals`, `requires_technical_report`, `extra_instructions` no schema do seed |
| **Como** | `TemplateGenerationService`; persistir em `campaign_scoring_templates` com flag `is_generated=True`, `organization_id` nullable (global vs org); vincular à campanha |
| **Validação** | Schema Pydantic rígido; fallback Genérico se JSON inválido |
| **Commit** | `feat(scoring): generate scoring templates on demand via LLM` |

### B3. CRUD de templates na API + UI ⬜

| Item | Detalhe |
|---|---|
| **O quê** | Listar templates ativos (globais + da org); editar sinais; vincular no wizard de campanha |
| **Como** | `GET/POST/PATCH /api/scoring-templates`; step no wizard “Critérios de qualificação” com preview |
| **Commit** | `feat(api,web): scoring template CRUD and campaign binding` |

### B4. Seeds de verticais faltantes (opcional paralelo) ⬜

| Item | Detalhe |
|---|---|
| **O quê** | Templates manuais de alta qualidade para nichos recorrentes do time |
| **Exemplos** | Landing pages / clínicas de saúde; Arquitetura/engenharia civil; Contabilidade; Jurídico; Educação |
| **Como** | Estender `DEFAULT_TEMPLATES` + `python -m src.seeds.scoring_templates` |
| **Commit** | `chore(workers): seed additional vertical scoring templates` |

### Critério de aceite Fase B

- [ ] Campanha “Landing pages para clínicas de psicologia em Araraquara” **não** usa critérios de Eng. Mecânica e **não** fica cega no Genérico sem signals úteis
- [ ] Campanha “Projetos de engenharia mecânica” ignora SSL/SEO como primário
- [ ] Template gerado persiste e reutiliza em campanhas seguintes da org
- [ ] Wizard permite escolher/vincular template

### Quando

Logo após A2/A3 estáveis (templates org-scoped dependem de org). Router global pode começar em paralelo a A4/A5.

---

## Fase C — Agente em linguagem natural (P1) ⬜

**Por quê:** experiência de “agente de prospecção”, não de formulário longo.

**Branch sugerida:** `feat/nl-campaign-agent`

### C1. Endpoint de interpretação de intent ⬜

| Item | Detalhe |
|---|---|
| **O quê** | `POST /api/campaigns/from-brief` body: `{ "brief": "quero vender landing pages para clínicas de psicologia em Araraquara" }` |
| **Retorno** | `name`, `target_service`, `target_segment`, `target_city`, `target_state`, `analysis_profile`, `places_query`, `scoring_template_id` (ou generate flag), `rationale` |
| **Como** | Serviço `CampaignBriefService` (Groq 70B); validação Pydantic; **não** cria campanha até confirm — ou cria em draft |
| **Commit** | `feat(api): parse natural-language campaign brief` |

### C2. UI “Descreva o que quer vender” ⬜

| Item | Detalhe |
|---|---|
| **O quê** | Alternativa ao wizard 4 steps: textarea + “Gerar campanha” → review card editável → confirmar → opcional “Iniciar coleta” |
| **Como** | Rota `/campanhas/nova` com toggle Wizard \| Agente; reusa create campaign + start pipeline |
| **Commit** | `feat(web): natural-language campaign creation flow` |

### C3. Sugestão de query Places a partir do brief ⬜

| Item | Detalhe |
|---|---|
| **O quê** | Query otimizada (“clínica de psicologia em Araraquara SP”) + hints de tipo |
| **Como** | Campo no retorno do brief; pipeline usa `places_query` se presente |
| **Commit** | `feat(pipeline): use agent-suggested places query` |

### Critério de aceite Fase C

- [ ] Brief em PT-BR gera campanha revisável em &lt; 10s
- [ ] Usuário edita campos antes de confirmar
- [ ] Coleta usa query coerente com o brief

### Quando

Depende de B1 (template no brief). Pode começar UI mock assim que A estiver ok.

---

## Fase D — Fontes de coleta e enriquecimento (P2) ⬜

**Por quê:** Places sozinho não cobre todas as verticais.

**Branch sugerida:** `feat/multi-source-leads` (ou branches por fonte)

### D1. Import CSV ⬜

| Item | Detalhe |
|---|---|
| **O quê** | Upload CSV (company_name, website, phone, city, state, cnpj opcional) → leads NOVO na campanha |
| **Como** | `POST /api/campaigns/{id}/import` multipart; validação linha a linha; dedupe por (org, website\|cnpj\|place_id) |
| **Commit** | `feat(api,web): CSV lead import per campaign` |

### D2. Busca por CNAE / Receita (em lote) ⬜

| Item | Detalhe |
|---|---|
| **O quê** | Para verticais industriais: descobrir empresas por CNAE + município (fonte a definir: BrasilAPI, CNPJá, dataset local) |
| **Como** | Novo `cnae_discovery_service.py`; job type `LEAD_COLLECTION` com payload `source=cnae`; **perguntar deps/API** antes de integrar |
| **Commit** | `feat(workers): CNAE-based lead discovery` |

### D3. Hunter.io / e-mail de decisor (quando key disponível) ⬜

| Item | Detalhe |
|---|---|
| **O quê** | Enriquecer Contact com e-mail + confidence (regra business-rules ≥50 p/ outreach auto) |
| **Como** | `contact_enrichment_service.py`; respeitar cotas; BYOK se Fase E de keys |
| **Commit** | `feat(workers): Hunter contact enrichment` |

### D4. Enriquecimento adaptativo no orchestrator ⬜

| Item | Detalhe |
|---|---|
| **O quê** | Pipeline escolhe steps: site? CNPJ? contatos? conforme template flags |
| **Como** | Estender `process_single_lead` / `pipeline_worker` com steps opcionais e eventos WS por step |
| **Commit** | `feat(pipeline): adaptive enrichment steps from template` |

### Critério de aceite Fase D

- [ ] Campanha industrial pode nascer de CNAE ou CSV sem Places
- [ ] Campanha local retail continua Places-first
- [ ] Orchestrator não gasta HTTP de site se `requires_technical_report=false`

### Quando

Após C em uso real (saber quais fontes o time mais pede). CSV é quick win e pode pular à frente se necessário.

---

## Fase E — Custos, feedback e cadência (P2/P3) ⬜

### E1. BYOK e cotas por organização ⬜

| Item | Detalhe |
|---|---|
| **O quê** | Org pode cadastrar `GOOGLE_API_KEY` / `GROQ_API_KEY` próprias (criptografadas at rest); senão usa pool com quota diária |
| **Como** | Tabela `organization_secrets` (encrypted); settings resolver por org no worker; UI em Configurações |
| **Commit** | `feat(api,workers): per-org API keys and quotas` |

### E2. Feedback de conversão → score ⬜

| Item | Detalhe |
|---|---|
| **O quê** | Ao marcar PROPOSTA/REUNIAO/PERDIDO/Conversion, registrar outcome; job periódico ou batch recalibra pesos / reporta bias |
| **Como** | Usar `conversions` + status; dashboard “taxa de acerto do score”; v1 = analytics only; v2 = ajuste de threshold por org |
| **Commit** | `feat(api,web): conversion feedback and score analytics` |

### E3. Cadência de follow-up + envio ⬜

| Item | Detalhe |
|---|---|
| **O quê** | Sequência dia 0/3/7/14 (já em business-rules); opcional envio Resend; opt-out |
| **Como** | Job scheduler (APScheduler ou cron + Job table); **humano-no-loop default**; envio automático só com flag opt-in da org |
| **Commit** | `feat(workers): outreach cadence jobs` |

### E4. Playbooks por vertical ⬜

| Item | Detalhe |
|---|---|
| **O quê** | Biblioteca de hooks, assuntos, objeções por template/serviço |
| **Como** | JSONB em template ou tabela `playbooks`; outreach_service injeta no prompt |
| **Commit** | `feat(scoring,outreach): vertical playbooks` |

### Critério de aceite Fase E

- [ ] Org com BYOK não consome quota do pool (ou consome de forma contabilizada)
- [ ] Dashboard mostra conversão por faixa de score
- [ ] Follow-ups agendados respeitam opt-out e LGPD

### Quando

E1 o quanto antes se amigos começarem a usar (custo). E2–E4 após volume real de leads.

---

## 4. Ordem de branches / PRs (checklist operacional)

| # | Branch | Fase | Depende de | PR (manual) |
|---|---|---|---|---|
| 0 | `docs/multi-vertical-agent-plan` | Docs | — | este plano |
| 1 | `feat/org-multi-tenant` | A1–A5 | #0 | após testes isolamento |
| 2 | `feat/smart-scoring-templates` | B1–B4 | A2 (org em template opcional); B1 pode ir sem A | |
| 3 | `feat/nl-campaign-agent` | C1–C3 | B1, A3 | |
| 4 | `feat/csv-lead-import` | D1 | A3 | quick win |
| 5 | `feat/cnae-discovery` | D2 | A3, D4 parcial | |
| 6 | `feat/adaptive-enrichment` | D4 | B | |
| 7 | `feat/org-byok-quotas` | E1 | A | |
| 8 | `feat/conversion-feedback` | E2 | A, volume | |
| 9 | `feat/outreach-cadence` | E3 | E1 opcional | |

---

## 5. Riscos e guardrails

| Risco | Mitigação |
|---|---|
| Migration quebra `place_id` unique | Backfill `organization_id` em leads **antes** de dropar unique; dual-write no insert |
| LLM gera template lixo | Schema rígido + Genérico fallback + review humano no wizard |
| Custo Groq explode com router+generate+brief | Cache de roteamento; 8B no router; 70B só brief/generate; rate limit por org |
| Vazamento cross-tenant | Testes automatizados de isolamento; code review focado em queries sem `org_id` |
| Lei 12.737 / LGPD | Manter análise passiva; opt-out; sem probe/auth test; sem scrape agressivo |
| Deps novas (Hunter, Resend, crypto) | **Sempre perguntar** antes de `pip`/`npm` install |

---

## 6. Definição de pronto (produto)

A plataforma está “pronta para amigos e empresa” quando:

1. Cada pessoa/empresa tem workspace isolado (com convites).
2. Brief em linguagem natural cria campanha coerente em qualquer vertical razoável.
3. Score e evidências fazem sentido **para o serviço vendido** (não só para sites).
4. Dá para importar lista própria além do Places.
5. Custos de API não quebram o uso compartilhado (BYOK ou cota).
6. Humano permanece no envio de mensagens (default).

---

## 7. Próxima ação concreta

**Começar Fase A — fatia A1+A2** na branch `feat/org-multi-tenant`:

1. `git checkout main && git pull`
2. `git checkout -b feat/org-multi-tenant`
3. Models + migration organizations / members / `organization_id` em campaigns e leads
4. Backfill + unique `(organization_id, place_id)`
5. Commits convencionais granulares
6. Só então A3 (filtros API)

Não abrir PR até o dono validar localmente.

---

## 8. Rastreio rápido de status

| Fase | Status | Notas |
|---|---|---|
| A Multi-tenant | ⬜ Não iniciado | Bloqueador P0 |
| B Templates smart | ⬜ Não iniciado | |
| C Agente NL | ⬜ Não iniciado | |
| D Fontes | ⬜ Não iniciado | CSV pode adiantar |
| E Feedback/custo/cadência | ⬜ Não iniciado | |

Atualizar esta tabela a cada merge.
