# Roadmap Combinado — Agente de Prospecção Multi-Vertical + Inteligência Comercial

> **Documento único de referência** para o futuro do sistema. Substitui
> `multi-vertical-agent-plan.md` e `sales-intelligence-plan.md` (fusionados aqui).
>
> Objetivo: a plataforma vira a **máquina de prospecção B2B** da empresa —
> qualifica leads em **qualquer vertical** (sem hardcode), serve **consultores,
> analista, gestor e diretoria**, e produz **relatórios BI + PDF** para decisão.
>
> Criado em 2026-08-01. Atualizar status conforme cada item for entregue.

---

## 0. Convenções de trabalho (obrigatórias)

A cada unidade de trabalho (épico ou fatia):

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
3. **Escopos comuns**: `api`, `workers`, `web`, `db`, `auth`, `scoring`, `pipeline`,
   `analytics`, `pdf`, `docs`
4. **PR**: o autor do código **não** abre o PR — deixa branch pronta e funcionando;
   o dono do repo abre manualmente quando validar.
5. **Docs vivos**: ao fechar uma fatia, atualizar:
   - este arquivo (status da fatia)
   - `docs/context.md` (Estado atual + Próximo passo)
   - `docs/decisions.md` se houver ADR nova
6. **Nunca** commitar `.env`, chaves ou secrets. Nunca instalar deps sem perguntar.

---

## 1. Visão — O que o app deve ser futuramente

O sistema não é apenas "coletor de leads com score". Ele deve se tornar a
**camada de inteligência comercial** da empresa, usada diariamente por:

| Quem | O que faz no app |
|---|---|
| **Consultor de vendas** | Trabalha os leads no kanban, se auto-atribui, registra contato/reunião/proposta |
| **Analista de vendas** | Vê relatórios BI: quais leads convertem mais, mapa de oportunidades, desempenho por consultor; exporta PDF para a diretoria |
| **Gestor/Manager** | Vê desempenho da equipe, BI completo, delega/atribui leads |
| **Diretoria (consumidor final)** | Recebe o relatório PDF com KPIs da operação de prospecção |

### 1.1 Capacidades-alvo

1. **Prospecção multi-vertical sem hardcode** — qualquer serviço/segmento gera
   critérios de qualificação sob demanda (landing page p/ clínica, projeto de
   engenharia mecânica, consultoria, etc.).
2. **Qualificação contextual e explicável** — score 0–100 (≥60 QUALIFICADO),
   `priority` HOT/WARM/COLD, evidências, pitch e mensagem personalizados.
3. **Atribuição de leads a consultores** — cada lead tem um dono responsável
   (manual no kanban); dá para medir desempenho individual.
4. **Trilha de atividades** — quem atribuiu, quem mudou o status, quem marcou
   a reunião. Base para métricas e auditoria.
5. **Papéis de venda** — `CONSULTOR`, `ANALYST`, `MANAGER` por organização
   (além dos papéis de workspace `owner/admin/member` já existentes).
6. **BI / Relatórios** — leads que mais convertem, mapa de melhores oportunidades
   (heatmap por cidade + mapa interativo), funil, conversão por faixa de score,
   desempenho por consultor, evolução temporal.
7. **Exportação PDF** — relatório completo (detalhado) para encaminhar ao
   presidente (renderização visual rica via **weasyprint**).
8. **Pitch personalizado por lead** — pitch one-pager consolidado por lead.
9. **Qualificação profunda de site** — para lead de tecnologia/landing pages:
   ver se já tem site e qualificá-lo (novo/desatualizado, faltando algo,
   vulnerabilidades) — já parcialmente coberto pelo enriquecimento técnico.
10. **Fontes múltiplas de coleta** — Places + CSV + CNAE/Receita (para verticais
    industriais sem vitrine no Maps).
11. **Custo justo e escalável** — BYOK por organização ou pool com cotas.
12. **Aprendizado com resultado** — feedback conversão↔score recalibra a qualificação.

### 1.2 Não é / Não será

- Não é BI genérico (PowerBI/Tableau) — é BI **contextual da operação de prospecção**.
- Não é clone de Apollo.io — conceitualmente inspirado, funcionalmente brasileiro
  (CNPJ, WhatsApp, LGPD).
- Não substitui o vendedor — automatiza pesquisa/qualificação; o humano vende e envia.
- Não é ferramenta de spam — LGPD, opt-out, análise passiva, humano no envio (default).
- Não faz enriquecimento ativo/invasivo — Lei 12.737/2012 respeitada (nunca probe,
  nunca testar auth, nunca injetar).

### 1.3 Modelo mental alvo (norte do produto)

```
Usuário/Org descreve oferta + ICP em linguagem natural
        ↓
Agente: fontes + perfil + template (ou gera) + query de coleta
        ↓
Coleta multi-fonte → enriquecimento adaptativo (site? CNPJ? contatos?)
        ↓
Score explicável no contexto DA oferta (com trilha de atividades)
        ↓
Atribuição ao consultor → outreach personalizado (humano no loop)
        ↓
Resultado real (ganhou/perdeu) → BI p/ analista/gestor → PDF p/ diretoria
        ↓
Feedback → calibra próximo ciclo
```

---

## 2. Estado atual (baseline 2026-08-01)

### 2.1 Já entregue (não precisa reconstruir)

| Capacidade | Estado | Arquivo(s) |
|---|---|---|
| Coleta via Google Places (query + cidade) | ✅ | `places_service.py` |
| Enriquecimento de site passivo (SSL, CMS, SEO, load, segurança) | ✅ | `technical_enrichment_service.py` |
| Enriquecimento cadastral CNPJ (Receita/BrasilAPI) + contatos + CompanyRecord | ✅ | `cnpj_service.py`, models |
| Scoring contextual 0–100 (≥60 QUALIFICADO) via Groq + templates | ✅ | `scoring_service.py` |
| Pitch por lead (`pitch_angle`, `suggested_subject`, `evidence`, `executive_summary`) | ✅ | `scoring_service.py` |
| Geração de mensagens de outreach (e-mail/WhatsApp) via Groq 70B — humano envia | ✅ | `outreach_service.py` |
| Sugestão de segmentos por IA (wizard) | ✅ | `segment_suggestion_service.py` |
| Funil básico `GET /api/metrics` | ✅ | `routes/metrics.py` |
| Multi-tenant: orgs + membership + isolamento cross-tenant + org pessoal no registro | ✅ | Fase A (mergeada, migration `9a7b6c5d4e3f2`) |
| Funil de status completo | ✅ | `models.py` (LeadStatus) |
| Templates seedados (9) | ✅ | `seeds/scoring_templates.py` |
| Frontend: dashboard, campanhas+wizard, oportunidades, kanban, config, auth, pipeline WS | ✅ | `apps/web/` |

### 2.2 Gaps que o roadmap ataca

| Gap | Impacto | Endereçado por |
|---|---|---|
| Template Genérico para vertical nova (match exato) | Score ruim em vertical nova | Item 1.2/1.3 (router + geração) |
| Sem atribuição/trilha de quem fez o quê | Sem desempenho por consultor, sem auditoria | Item 1.1 |
| Sem papéis de venda | Analista/consultor/gestor sem isolamento funcional | Item 2.1 |
| Sem BI/PDF | Diretoria sem visão executiva | Itens 2.2–2.4 |
| Só fonte Places | Verticais industriais não cobertas | Itens 3.1–3.2 |
| API keys em pool único | Quota esgota com uso compartilhado | Item 3.5 |
| Sem feedback score↔conversão | Qualificação não melhora com o tempo | Item 3.6 |
| UX de formulário, não de agente | Criar campanha é lento | Item 1.4 |

---

## 3. Fases de execução

```
FASE 1  Prospecção multi-vertical imediata  (1–2 sprints) → desbloqueia receita
   │
FASE 2  Inteligência comercial p/ a empresa (2–3 sprints) → analista/BI/PDF
   │
FASE 3  Ampliar fontes e fechar o loop      (3–4 sprints) → volume + aprendizado
```

Cada item = **1 branch** + commits convencionais. Critérios de aceite por fase.
PR feito manualmente pelo dono.

---

## FASE 1 — Prospecção multi-vertical imediata ⬜

> **Objetivo**: a empresa começa a prospectar o quanto antes, em **qualquer
> vertical**, com leads bem qualificados — e o histórico de atribuição começa a
> ser capturado desde o primeiro dia (dados não backfilláveis).
>
> **Sprint 1** = itens 1.1 + 1.2 + 1.3.

### Item 1.1 — Atribuição de leads + trilha de atividades ⬜

Branch: `feat/sales-intel-assignment`
**Prioridade**: 1º sprint (dados de atribuição/atividade são "coleta agora ou nunca").

| Sub-item | O quê | Onde |
|---|---|---|
| 1.1.1 | `Lead.assigned_to_id` (FK `users.id`, nullable) + `Lead.assigned_at` | models + migration |
| 1.1.2 | Tabela `lead_activities` (`id`, `lead_id`, `user_id`, `action`, `status_from`, `status_to`, `detail`, `created_at`) | models + migration |
| 1.1.3 | `Conversion.user_id` (quem fechou) + `Conversion.assigned_to_id` (quem trabalhava o lead) | models + migration |
| 1.1.4 | `PATCH /api/leads/{id}/assign` — atribuir/desatribuir consultor (da mesma org); grava atividade `ASSIGNED`/`UNASSIGNED` | `routes/leads.py` |
| 1.1.5 | Gravação automática de atividades em mudanças de status (`STATUS_CHANGED`), geração de mensagens (`MESSAGE_GENERATED`), conversão (`CONVERTED`) | rotas + pipeline |
| 1.1.6 | Re-export de models no API (`LeadActivity`) | `services/api/src/db/models.py` |
| 1.1.7 | Tests: atribuição, trilha em mudança de status, isolamento por org | testes |

**Critérios de aceite 1.1**
- [ ] Lead pode ser atribuído/desatribuído a um consultor da mesma org
- [ ] Toda mudança de status gera registro na trilha (com quem/quando)
- [ ] Atribuição e status alimentam a base do BI (item 2.2)
- [ ] Isolamento: consultor de outra org não atribui/vê lead alheio

**Commits sugeridos**
- `feat(db): add lead assignment and activity trail`
- `feat(api): lead assign endpoint with activity logging`
- `test(api): assignment and activity trail isolation`

---

### Item 1.2 — Router de template de scoring ⬜

Branch: `feat/smart-template-router`
**Prioridade**: 1º sprint (melhora o sinal que o BI vai mostrar).

| Sub-item | O quê |
|---|---|
| 1.2.1 | Melhorar `load_scoring_template`: (1) exact match; (2) contains/token overlap; (3) se fraco, 1 call Groq 8B classificando entre labels existentes + `GENERATE_NEW`; (4) cache em memória por string normalizada |
| 1.2.2 | Reusar router também no match por `target_segment` (fallback comum) |
| 1.2.3 | Fallback seguro: se LLM falhar, volta ao Genérico com instruções reforçadas |

**Critérios de aceite 1.2**
- [ ] "Landing pages para clínicas de psicologia" roteia para Desenvolvimento de Sites (ou GENERATE_NEW)
- [ ] "Projetos de engenharia mecânica" roteia para Engenharia Mecânica (ignora SSL/SEO como primário)
- [ ] Cache evita chamadas repetidas de Groq para a mesma string

**Commits sugeridos**
- `feat(scoring): fuzzy and llm template router with cache`

---

### Item 1.3 — Geração de template sob demanda ⬜

Branch: `feat/template-on-demand`
**Prioridade**: 1º sprint (nada de vertical hardcoded).

| Sub-item | O quê |
|---|---|
| 1.3.1 | `TemplateGenerationService` (Groq 70B): devolve `positive_signals`, `negative_signals`, `context_signals`, `requires_technical_report`, `requires_business_data`, `extra_instructions` no schema do seed |
| 1.3.2 | Persistir em `campaign_scoring_templates` com flag `is_generated=True`, `organization_id` nullable (global vs org), vincular à campanha |
| 1.3.3 | Validação Pydantic rígida; fallback Genérico se JSON inválido |
| 1.3.4 | Reutilizar template gerado em campanhas seguintes da mesma org (match por label) |

**Critérios de aceite 1.3**
- [ ] Campanha de vertical nova sem template seedado gera template próprio automaticamente
- [ ] Template gerado persiste e é reutilizado
- [ ] LLM falha → fallback Genérico (não quebra o pipeline)

**Commits sugeridos**
- `feat(scoring): generate scoring templates on demand via llm`
- `feat(db): add is_generated and organization_id to templates`

---

### Item 1.4 — Campanha por linguagem natural (agente) ⬜

Branch: `feat/nl-campaign-brief`
**Prioridade**: 2º sprint da Fase 1.

| Sub-item | O quê |
|---|---|
| 1.4.1 | `POST /api/campaigns/from-brief` body `{ "brief": "quero vender landing pages para clínicas de psicologia em Araraquara" }` |
| 1.4.2 | Retorno: `name`, `target_service`, `target_segment`, `target_city`, `target_state`, `analysis_profile`, `places_query`, `scoring_template_id` (ou flag de geração), `rationale` |
| 1.4.3 | `CampaignBriefService` (Groq 70B); validação Pydantic; **não** cria campanha até confirmar (ou cria em draft) |
| 1.4.4 | UI: textarea + "Gerar campanha" → review card editável → confirmar → opcional "Iniciar coleta" (rota `/campanhas/nova` com toggle Wizard \| Agente) |
| 1.4.5 | Sugestão de query Places otimizada a partir do brief (pipeline usa `places_query` se presente) |

**Critérios de aceite 1.4**
- [ ] Brief em PT-BR gera campanha revisável em < 10s
- [ ] Usuário edita campos antes de confirmar
- [ ] Coleta usa query coerente com o brief

**Commits sugeridos**
- `feat(api): parse natural-language campaign brief`
- `feat(web): natural-language campaign creation flow`
- `feat(pipeline): use agent-suggested places query`

---

### Item 1.5 — CRUD de templates + vínculo no wizard ⬜

Branch: `feat/template-crud-ui`
**Prioridade**: 2º sprint da Fase 1.

| Sub-item | O quê |
|---|---|
| 1.5.1 | `GET/POST/PATCH /api/scoring-templates` (globais + da org) |
| 1.5.2 | Editor de sinais (positive/negative/context + flags) no wizard de campanha, com preview |
| 1.5.3 | Vincular template escolhido à campanha (`scoring_template_id`) |
| 1.5.4 | Revisão humana de templates gerados (item 1.3) antes de uso em massa |

**Critérios de aceite 1.5**
- [ ] Wizard permite escolher/editar/vincular template
- [ ] Templates gerados aparecem com flag "gerado" para revisão

**Commits sugeridos**
- `feat(api,web): scoring template CRUD and campaign binding`

---

### Critérios de aceite Fase 1 (global)

- [ ] Campanha "landing pages para clínicas de psicologia em Araraquara" gera score com critérios relevantes
- [ ] Campanha de vertical nova gera template próprio automaticamente
- [ ] Todo lead é atribuível; toda mudança de status fica na trilha
- [ ] Brief em PT-BR cria campanha revisável em < 10s
- [ ] Nada hardcoded: a IA define os critérios da vertical

---

## FASE 2 — Inteligência comercial para a empresa ⬜

> **Objetivo**: analista enxerga e exporta; consultor trabalha o próprio funil;
> papéis isolam; diretoria recebe o PDF.

### Item 2.1 — Papéis de venda ⬜

Branch: `feat/sales-roles`
**Prioridade**: início da Fase 2 (pré-requisito do BI).

| Sub-item | O quê |
|---|---|
| 2.1.1 | `OrganizationMember.sales_role` — enum `CONSULTOR`/`ANALYST`/`MANAGER` (default CONSULTOR), **por organização** (não global) |
| 2.1.2 | Dependency `require_sales_role(min)` e `require_analyst()` |
| 2.1.3 | Regras: ANALYST/MANAGER leem tudo da org + BI + exportam PDF; CONSULTOR vê/edita só os próprios leads (ou não atribuídos) e pode se auto-atribuir |
| 2.1.4 | Endpoint para owner/admin definir `sales_role` de membro (`PATCH /api/orgs/{id}/members/{user_id}`) |

**Critérios de aceite 2.1**
- [ ] Analista acessa BI; consultor não acessa relatórios de outros
- [ ] Consultor não vê leads de outros consultores na listagem
- [ ] Owner/admin pode promover/demover papel
- [ ] `sales_role` é por organização (não vaza entre empresas)

**Commits sugeridos**
- `feat(db): add sales_role to organization_members`
- `feat(api): sales role dependencies and member role endpoint`
- `fix(api): scope lead visibility by sales role`

---

### Item 2.2 — APIs de BI ⬜

Branch: `feat/analytics-api`
**Prioridade**: depende de 1.1 (dados) + 2.1 (papéis).

| Endpoint | Retorna |
|---|---|
| `GET /api/analytics/overview` | KPIs: funil, conversão (qualificado→reunião/fechado), taxa de resposta, leads por faixa de score |
| `GET /api/analytics/consultants` | **Por consultor**: prospecções, atribuídos, contatados, reuniões marcadas/feitas, propostas, convertidos, conversão % |
| `GET /api/analytics/leads-ranking` | Top leads por score / por conversão / por campanha (filtro período) |
| `GET /api/analytics/geo` | Agregação por cidade/UF: contagem, score médio, convertidos (para heatmap + mapa) |
| `GET /api/analytics/campaigns` | Desempenho por campanha: leads, qualificados, reuniões, conversão, ticket |
| `GET /api/analytics/timeline` | Evolução temporal (novos, reuniões, fechados por dia/semana) |

Todas **org-scoped** (herdam isolamento). ANALYST/MANAGER-only.

**Critérios de aceite 2.2**
- [ ] Métricas por consultor refletem atribuição + atividades reais
- [ ] Dados geo permitem montar heatmap por cidade e mapa por UF
- [ ] Filtro por período funciona em todos os endpoints

**Commits sugeridos**
- `feat(api): analytics endpoints (overview, consultants, ranking, geo, campaigns, timeline)`
- `feat(api): analytics service with org scoping`

---

### Item 2.3 — Exportação PDF (weasyprint) ⬜

Branch: `feat/analytics-pdf`
**Prioridade**: depende de 2.2.

| Sub-item | O quê |
|---|---|
| 2.3.1 | `GET /api/analytics/export/pdf?from=&to=` — relatório **completo/detalhado**: visão executiva, funil, por campanha, por consultor, top leads, evolução temporal |
| 2.3.2 | **Dependência nova**: `weasyprint` (HTML→PDF, renderização visual rica) — **pedir aprovação antes de instalar** |
| 2.3.3 | Template HTML com branding (cabeçalho com org, data, seções, tabelas, gráficos simples via CSS) |
| 2.3.4 | Cache do agregado (item 2.2) para não recalcular a cada export |
| 2.3.5 | Geração assíncrona se o relatório ficar pesado (job + notificação) |

**Critérios de aceite 2.3**
- [ ] PDF baixa com as seções do relatório completo
- [ ] Renderiza offline (sem depender de serviço externo)
- [ ] Apenas ANALYST/MANAGER/owner pode exportar

**Commits sugeridos**
- `feat(api,pdf): executive bi report export via weasyprint`
- `feat(api): analytics report aggregation with cache`

---

### Item 2.4 — Frontend: relatórios + kanban + mapa ⬜

Branch: `feat/analytics-web`
**Prioridade**: depende de 2.1+2.2+2.3.

| Sub-item | O quê |
|---|---|
| 2.4.1 | Nova rota `/relatorios` (guarda MANAGER/ANALYST): visão executiva, melhores leads, mapa, desempenho por consultor, timeline, filtro período, botão "Exportar PDF" |
| 2.4.2 | **Mapa** — heatmap por cidade (tabela/gráfico Recharts, já instalado) + mapa interativo **Leaflet** (dependência nova; pedir aprovação) |
| 2.4.3 | Kanban `/vendas`: menu "Atribuir a mim / para outro"; consultor vê só os próprios |
| 2.4.4 | Detalhe do lead: trilha de atividades (quem fez o quê) |

**Critérios de aceite 2.4**
- [ ] Analista vê todos os relatórios e exporta PDF
- [ ] Consultor vê kanban só com seus leads + pode se atribuir não atribuídos
- [ ] Mapa e heatmap renderizam com dados reais
- [ ] Trilha de atividades visível no detalhe do lead

**Commits sugeridos**
- `feat(web): analytics reports page`
- `feat(web): leaflet map and city heatmap`
- `feat(web): kanban assignment and lead activity timeline`

---

### Item 2.5 — Pitch one-pager + site audit ⬜

Branch: `feat/pitch-one-pager`
**Prioridade**: pode ser paralelo (reusa 1.1 para contexto).

| Sub-item | O quê |
|---|---|
| 2.5.1 | `GET /api/leads/{id}/pitch` — **pitch one-pager** consolidado (pitch_angle + evidence + primary_need + score + recomendações) → reutilizável em PDF/WhatsApp/e-mail |
| 2.5.2 | Site audit legível para leads web: "site novo/desatualizado, faltando X, vulnerabilidades Y" — **apresentação/exportação** do que já existe (sem novo enriquecimento) |
| 2.5.3 | Expor pitch/site audit no detalhe do lead e no relatório PDF |

**Critérios de aceite 2.5**
- [ ] Pitch one-pager gera para qualquer lead com scoring
- [ ] Site audit legível apresenta os dados técnicos já coletados
- [ ] Conteúdo exportável no PDF do relatório

**Commits sugeridos**
- `feat(api): lead pitch one-pager endpoint`
- `feat(api): readable site audit from collected data`

---

### Critérios de aceite Fase 2 (global)

- [ ] Analista vê todos os relatórios e exporta PDF; consultor não vê leads alheios
- [ ] Desempenho por consultor reflete atribuição + trilha reais
- [ ] Mapa (heatmap + Leaflet) e ranking renderizam com dados reais
- [ ] PDF detalhado baixa com as seções completas
- [ ] Pitch e site audit disponíveis por lead

---

## FASE 3 — Ampliar fontes e fechar o loop ⬜

> **Objetivo**: cobertura além do Places, custo justo, aprendizado com resultado.

### Item 3.1 — Import CSV ⬜

Branch: `feat/csv-import`

| Sub-item | O quê |
|---|---|
| 3.1.1 | `POST /api/campaigns/{id}/import` multipart (company_name, website, phone, city, state, cnpj opcional) → leads NOVO |
| 3.1.2 | Validação linha a linha + relatório de erros |
| 3.1.3 | Dedupe por (org, website/cnpj/place_id) |
| 3.1.4 | UI: upload no detalhe da campanha |

**Critérios**: importar lista própria; dedupe funcional; leads entram no pipeline normalmente.

### Item 3.2 — Descoberta por CNAE/Receita ⬜

Branch: `feat/cnae-discovery`

| Sub-item | O quê |
|---|---|
| 3.2.1 | `cnae_discovery_service.py` — descobrir empresas por CNAE + município (BrasilAPI/CNPJá/dataset a definir) |
| 3.2.2 | Job type `LEAD_COLLECTION` com payload `source=cnae` |
| 3.2.3 | **Perguntar deps/API antes de integrar** |

**Critérios**: campanha industrial nasce de CNAE sem Places.

### Item 3.3 — Enriquecimento adaptativo ⬜

Branch: `feat/adaptive-enrichment`

| Sub-item | O quê |
|---|---|
| 3.3.1 | Orchestrator escolhe steps: site? CNPJ? contatos? conforme flags do template |
| 3.3.2 | Eventos WS por step |
| 3.3.3 | Não gastar HTTP de site se `requires_technical_report=false` |

**Critérios**: pipeline não desperdiça chamadas; eventos por step.

### Item 3.4 — Hunter / e-mail de decisor ⬜

Branch: `feat/hunter-enrichment`

| Sub-item | O quê |
|---|---|
| 3.4.1 | `contact_enrichment_service.py` (Hunter.io) — enriquecer `Contact` com e-mail + confidence |
| 3.4.2 | Respeitar regra ≥50 p/ outreach; cotas; BYOK se habilitado |
| 3.4.3 | **Perguntar deps/API antes de integrar** |

**Critérios**: decisor com e-mail + confidence; regras respeitadas.

### Item 3.5 — BYOK e cotas por org ⬜

Branch: `feat/org-byok`

| Sub-item | O quê |
|---|---|
| 3.5.1 | Tabela `organization_secrets` (criptografado at rest) para `GOOGLE_API_KEY`/`GROQ_API_KEY` |
| 3.5.2 | Settings resolvem por org no worker; senão usa pool com quota diária |
| 3.5.3 | UI em Configurações da org |

**Critérios**: org com BYOK não consome quota do pool (ou consome contabilizado).

### Item 3.6 — Feedback conversão → score ⬜

Branch: `feat/conversion-feedback`

| Sub-item | O quê |
|---|---|
| 3.6.1 | Ao marcar PROPOSTA/REUNIAO/PERDIDO/Conversion, registrar outcome (usa trilha do 1.1) |
| 3.6.2 | Dashboard "taxa de acerto do score" (conversão por faixa de score) |
| 3.6.3 | v2: ajuste de threshold por org com base nos resultados |

**Critérios**: dashboard mostra conversão por faixa; base para calibrar.

### Item 3.7 — Cadência de follow-up + envio ⬜

Branch: `feat/outreach-cadence`

| Sub-item | O quê |
|---|---|
| 3.7.1 | Sequência dia 0/3/7/14 (regras já existentes em business-rules) |
| 3.7.2 | Job scheduler (APScheduler ou cron + Job table) |
| 3.7.3 | **Humano-no-loop default**; envio automático (Resend) só com flag opt-in da org; opt-out LGPD |

**Critérios**: follow-ups agendados respeitam opt-out e LGPD; humano por padrão.

### Item 3.8 — Playbooks por vertical ⬜

Branch: `feat/vertical-playbooks`

| Sub-item | O quê |
|---|---|
| 3.8.1 | Biblioteca de hooks, assuntos, objeções por template/serviço |
| 3.8.2 | JSONB em template ou tabela `playbooks`; outreach_service injeta no prompt |

**Critérios**: mensagens variam por vertical com hooks/objeções reais.

---

## 4. Ordem de branches / PRs (checklist operacional)

| # | Branch | Item | Depende de | PR (manual) |
|---|---|---|---|---|
| 1 | `feat/sales-intel-assignment` | 1.1 | — | após testes atribuição |
| 2 | `feat/smart-template-router` | 1.2 | — (pode ir junto) | após validar roteamento |
| 3 | `feat/template-on-demand` | 1.3 | 1.2 | após validar geração |
| 4 | `feat/nl-campaign-brief` | 1.4 | 1.3 | após validar brief |
| 5 | `feat/template-crud-ui` | 1.5 | 1.3 | após validar wizard |
| 6 | `feat/sales-roles` | 2.1 | 1.1 | após validar papéis |
| 7 | `feat/analytics-api` | 2.2 | 1.1 + 2.1 | após validar métricas |
| 8 | `feat/analytics-pdf` | 2.3 | 2.2 | após validar PDF |
| 9 | `feat/analytics-web` | 2.4 | 2.1+2.2+2.3 | após validar UI |
| 10 | `feat/pitch-one-pager` | 2.5 | 1.1 | a qualquer momento |
| 11 | `feat/csv-import` | 3.1 | 1.1 | quick win |
| 12 | `feat/cnae-discovery` | 3.2 | 3.3 parcial | |
| 13 | `feat/adaptive-enrichment` | 3.3 | 1.3 | |
| 14 | `feat/hunter-enrichment` | 3.4 | 3.5 opcional | |
| 15 | `feat/org-byok` | 3.5 | 1.1 | |
| 16 | `feat/conversion-feedback` | 3.6 | 1.1 + volume | |
| 17 | `feat/outreach-cadence` | 3.7 | 3.5 opcional | |
| 18 | `feat/vertical-playbooks` | 3.8 | 1.3 | |

---

## 5. Dependências novas (aprovação obrigatória antes de instalar)

| Dependência | Finalidade | Layer | Risco | Quando |
|---|---|---|---|---|
| `weasyprint` | PDF visual rico (HTML→PDF) | backend | médio (deps de sistema no Windows) | Item 2.3 |
| `leaflet`/`react-leaflet` | Mapa interativo | frontend | baixo | Item 2.4 |
| `APScheduler` (ou cron) | Cadência de follow-up | backend | baixo | Item 3.7 |
| Hunter.io (API) | E-mail de decisor | externa | baixo (cotas) | Item 3.4 |
| BrasilAPI/CNPJá (CNAE) | Descoberta por CNAE | externa | baixo | Item 3.2 |
| Resend (envio) | Envio automatizado (opt-in) | externa | baixo | Item 3.7 |

**Regra**: nada é instalado/integrador sem o dono aprovar.

---

## 6. Riscos e guardrails

| Risco | Mitigação |
|---|---|
| LLM gera template lixo | Schema rígido + fallback Genérico + revisão humana no wizard (1.5) |
| Custo Groq sobe (router+generate+brief) | 8B no router; 70B só generate/brief; cache + rate limit por org |
| Vazamento cross-tenant | Filtros estritos + testes de isolamento por papel |
| Histórico de atribuição perdido | Item 1.1 no 1º sprint (não backfillável) |
| Consultor vê dados de outros | Filtro por `assigned_to_id` + testes |
| Analista exporta dados sensíveis | PDF org-scoped; papéis validados no backend (não só na UI) |
| Migration quebra unique | Backfill antes de dropar constraints; dual-write no insert |
| Lei 12.737 / LGPD | Passivo sempre; opt-out; sem probe/auth test; humano no envio |
| PDF pesado/lento | Cache do agregado; geração assíncrona se necessário |
| Papel global vaza entre empresas | `sales_role` por `organization_members`, não global |
| Deps novas | **Sempre perguntar** antes de `pip`/`npm` install |

---

## 7. Definição de pronto (empresa prospectando)

A empresa **começa a prospectar com qualidade** quando 1.1 + 1.2 + 1.3 estiverem
em produção: qualquer vertical é qualificada com critérios próprios e o histórico
de atribuição já é coletado.

A plataforma fica **pronta para o uso pleno da empresa** quando:

1. Cada pessoa/empresa tem workspace isolado (org + papéis).
2. Brief em linguagem natural cria campanha coerente em qualquer vertical.
3. Score e evidências fazem sentido para o serviço vendido (não só para sites).
4. Dá para importar lista própria além do Places.
5. Custos de API não quebram o uso compartilhado (BYOK ou cota).
6. Analista vê BI e exporta PDF; consultor trabalha o próprio funil.
7. Humano permanece no envio de mensagens (default); LGPD/opt-out respeitados.

---

## 8. Rastreio rápido de status

| Item | Status | Notas |
|---|---|---|
| 1.1 Atribuição + trilha | ⬜ Não iniciado | Base de tudo; 1º sprint |
| 1.2 Router de template | ⬜ Não iniciado | fuzzy + LLM + cache |
| 1.3 Geração de template | ⬜ Não iniciado | nada hardcoded |
| 1.4 Campanha por linguagem natural | ⬜ Não iniciado | brief PT-BR |
| 1.5 CRUD de templates + wizard | ⬜ Não iniciado | revisão humana |
| 2.1 Papéis de venda | ⬜ Não iniciado | CONSULTOR/ANALYST/MANAGER |
| 2.2 APIs de BI | ⬜ Não iniciado | 6 endpoints |
| 2.3 Exportação PDF (weasyprint) | ⬜ Não iniciado | relatório detalhado |
| 2.4 Frontend relatórios/kanban/mapa | ⬜ Não iniciado | Leaflet + Recharts |
| 2.5 Pitch one-pager + site audit | ⬜ Não iniciado | reusa scoring/enriquecimento |
| 3.1 Import CSV | ⬜ Não iniciado | quick win |
| 3.2 Descoberta CNAE | ⬜ Não iniciado | fontes industriais |
| 3.3 Enriquecimento adaptativo | ⬜ Não iniciado | steps conforme template |
| 3.4 Hunter / e-mail decisor | ⬜ Não iniciado | cotas + confidence |
| 3.5 BYOK e cotas | ⬜ Não iniciado | custo justo |
| 3.6 Feedback conversão → score | ⬜ Não iniciado | aprende com resultado |
| 3.7 Cadência + envio | ⬜ Não iniciado | humano no loop |
| 3.8 Playbooks por vertical | ⬜ Não iniciado | hooks/objeções |

Atualizar esta tabela a cada merge.

---

## 9. Próxima ação concreta (sprint 1)

**Item 1.1 — atribuição + trilha** na branch `feat/sales-intel-assignment`:

1. `git checkout main && git pull`
2. `git checkout -b feat/sales-intel-assignment`
3. Models: `Lead.assigned_to_id/assigned_at`, `LeadActivity`, `Conversion.user_id/assigned_to_id`
4. Migration Alembic nova (nunca editar existentes)
5. `PATCH /api/leads/{id}/assign` + gravação automática de atividades
6. Testes de isolamento e trilha
7. Commits convencionais granulares
8. Não abrir PR até o dono validar localmente
