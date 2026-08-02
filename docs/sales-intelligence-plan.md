# Visão & Plano — Inteligência Comercial para a Empresa

> Documento que descreve **o que o app deve ser futuramente** (visão) e **como chegar lá** (plano).
> É a referência de "para onde vamos" — o "como está hoje" está em `context.md` e o plano
> multi-vertical em `multi-vertical-agent-plan.md`.
>
> Criado em 2026-08-01 a partir de sessão de visão do produto.

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

1. **Atribuição de leads a consultores** — cada lead tem um dono responsável
   (manual no kanban); dá para medir desempenho individual.
2. **Trilha de atividades** — quem atribuiu, quem mudou o status, quem marcou
   a reunião. Base para métricas e auditoria.
3. **Papéis de venda** — `CONSULTOR`, `ANALYST`, `MANAGER` por organização
   (além dos papéis de workspace `owner/admin/member` já existentes).
4. **BI / Relatórios** — leads que mais convertem, mapa de melhores oportunidades
   (heatmap por cidade + mapa interativo), funil, conversão por faixa de score,
   desempenho por consultor, evolução temporal.
5. **Exportação PDF** — relatório completo (detalhado) para encaminhar ao presidente.
6. **Pitch personalizado por lead** — pitch one-pager consolidado por lead.
7. **Qualificação profunda de site** — para lead de tecnologia/landing pages:
   ver se já tem site e qualificá-lo (novo/desatualizado, faltando algo,
   vulnerabilidades) — já parcialmente coberto pelo enriquecimento técnico.

### 1.2 Não é / Não será

- Não é BI genérico (PowerBI/Tableau) — é BI **contextual da operação de prospecção**.
- Não substitui o vendedor — automatiza pesquisa/qualificação; o humano vende.
- Não é ferramenta de spam — LGPD, opt-out, análise passiva.

---

## 2. Estado atual (o que já existe e não precisa reconstruir)

| Capacidade da visão | Estado atual | Arquivo(s) |
|---|---|---|
| Coleta de leads | ✅ Google Places (query + cidade) | `places_service.py` |
| Qualificação com score 0–100 (≥60 QUALIFICADO) | ✅ Groq + templates contextuais | `scoring_service.py` |
| Pitch personalizado por lead | ✅ `pitch_angle`, `suggested_subject`, `evidence`, `executive_summary` | `scoring_service.py` |
| Qualificação de site (novo, faltando, vulnerabilidades) | ✅ SSL/CMS/SEO/performance/segurança (passivo) | `technical_enrichment_service.py` |
| Geração de mensagens de outreach | ✅ Sequência e-mail/WhatsApp (humano envia) | `outreach_service.py` |
| Funil básico | ✅ `GET /api/metrics` (funnel agregado) | `routes/metrics.py` |
| Multi-tenant / organizações | ✅ Org pessoal no registro + isolamento cross-tenant | Fase A (mergeada) |
| Funil de status completo | ✅ NOVO→…→REUNIAO_FEITA/PROPOSTA_ENVIADA/PERDIDO | `models.py` |

---

## 3. Plano de execução — Fase X "Inteligência Comercial"

Branch raiz sugerida: `feat/sales-intelligence`
Documentação de trabalho: este arquivo (status na seção 7).

```
X1 fundação ─► X2 papéis ─► X3 BI APIs ─► X4 PDF ─► X5 frontend ─► X6 pitch/site
(1 branch)   (1 branch)   (1 branch)    (1 branch) (1 branch)    (1 branch)
```

Cada bloco = **1 branch** + commits convencionais (`feat(scope): ...`). PR feito manualmente pelo dono.

---

### Bloco X1 — Fundação de dados: atribuição + trilha ⬜

Branch: `feat/sales-intel-assignment`

| Item | O quê | Onde |
|---|---|---|
| X1.1 | `Lead.assigned_to_id` (FK users, nullable) + `Lead.assigned_at` | models + migration |
| X1.2 | Tabela `lead_activities` (`lead_id`, `user_id`, `action`, `status_from`, `status_to`, `detail`, `created_at`) | models + migration |
| X1.3 | `PATCH /api/leads/{id}/assign` — atribuir/desatribuir consultor | `routes/leads.py` |
| X1.4 | Mudanças de status/mensagem/conversão gravam `lead_activities` | rotas + pipeline |
| X1.5 | `Conversion.user_id` (quem fechou) | models + migration |

Critério de aceite:
- [ ] Lead pode ser atribuído a um consultor da mesma org
- [ ] Toda mudança de status gera registro na trilha (com quem/quando)
- [ ] Consultor vê seus leads atribuídos

---

### Bloco X2 — Papéis de venda ⬜

Branch: `feat/sales-intel-roles`

| Item | O quê |
|---|---|
| X2.1 | `OrganizationMember.sales_role` — enum `CONSULTOR`/`ANALYST`/`MANAGER` (default CONSULTOR), **por organização** |
| X2.2 | Dependency `require_sales_role(min)` e `require_analyst()` |
| X2.3 | Regras: ANALYST/MANAGER leem tudo da org + BI + exportam PDF; CONSULTOR vê/edita só os próprios leads (ou não atribuídos) e pode se auto-atribuir |
| X2.4 | Endpoint para owner/admin definir `sales_role` de membro |

Critério de aceite:
- [ ] Analista acessa BI; consultor não acessa relatórios de outros
- [ ] Consultor não vê leads de outros consultores na listagem
- [ ] Owner/admin pode promover/demover papel

---

### Bloco X3 — APIs de BI ⬜

Branch: `feat/sales-intel-analytics`

| Endpoint | Retorna |
|---|---|
| `GET /api/analytics/overview` | KPIs: funil, conversão (qualificado→reunião/fechado), taxa de resposta, leads por faixa de score |
| `GET /api/analytics/consultants` | **Por consultor**: prospecções, atribuídos, contatados, reuniões marcadas/feitas, propostas, convertidos, conversão % |
| `GET /api/analytics/leads-ranking` | Top leads por score / por conversão / por campanha (filtro período) |
| `GET /api/analytics/geo` | Agregação por cidade/UF: contagem, score médio, convertidos (para heatmap + mapa) |
| `GET /api/analytics/campaigns` | Desempenho por campanha: leads, qualificados, reuniões, conversão, ticket |
| `GET /api/analytics/timeline` | Evolução temporal (novos, reuniões, fechados por dia/semana) |

Todas **org-scoped** (herdam isolamento). ANALYST/MANAGER-only.

Critério de aceite:
- [ ] Métricas por consultor refletem atribuição + atividades reais
- [ ] Dados geo permitem montar heatmap por cidade e mapa por UF

---

### Bloco X4 — Exportação PDF ⬜

Branch: `feat/sales-intel-pdf`

| Item | O quê |
|---|---|
| X4.1 | `GET /api/analytics/export/pdf?from=&to=` — relatório **completo/detalhado**: visão executiva, funil, por campanha, por consultor, top leads, evolução temporal |
| X4.2 | **Nova dependência** — `reportlab` (puro Python) ou `weasyprint` (HTML→PDF, mais bonito; pedir aprovação antes de instalar) |
| X4.3 | Cache do agregado para não recalcular a cada export |

Critério de aceite:
- [ ] PDF baixa com as seções do relatório completo
- [ ] Renderiza offline (sem depender de serviço externo)

---

### Bloco X5 — Frontend: relatórios, kanban, detalhe ⬜

Branch: `feat/sales-intel-web`

| Item | O quê |
|---|---|
| X5.1 | Nova rota `/relatorios` (guarda MANAGER/ANALYST): visão executiva, melhores leads, mapa, desempenho por consultor, timeline, filtro período, botão "Exportar PDF" |
| X5.2 | **Mapa** — heatmap por cidade (tabela/gráfico Recharts, já instalado) + mapa interativo **Leaflet** (dependência nova; pedir aprovação) |
| X5.3 | Kanban `/vendas`: menu "Atribuir a mim / para outro"; consultor vê só os próprios |
| X5.4 | Detalhe do lead: trilha de atividades (quem fez o quê) |

Critério de aceite:
- [ ] Analista vê todos os relatórios e exporta PDF
- [ ] Consultor vê kanban só com seus leads + pode se atribuir não atribuídos
- [ ] Mapa e heatmap renderizam com dados reais

---

### Bloco X6 — Pitch one-pager e site audit ⬜

Branch: `feat/sales-intel-pitch`

| Item | O quê |
|---|---|
| X6.1 | `GET /api/leads/{id}/pitch` — **pitch one-pager** consolidado (pitch_angle + evidence + primary_need + score + recomendações) → reutilizável em PDF/WhatsApp/e-mail |
| X6.2 | Site audit legível para leads web: "site novo/desatualizado, faltando X, vulnerabilidades Y" — **apresentação/exportação** do que já existe (sem novo enriquecimento) |
| X6.3 | Expor pitch/site audit no detalhe do lead e no relatório PDF |

Critério de aceite:
- [ ] Pitch one-pager gera para qualquer lead com scoring
- [ ] Site audit legível apresenta os dados técnicos já coletados

---

## 4. Dependências novas (precisam de aprovação antes de instalar)

| Dependência | Finalidade | Layer | Risco |
|---|---|---|---|
| `reportlab` | Geração de PDF puro Python | backend | baixo |
| *ou* `weasyprint` | HTML→PDF mais bonito | backend | médio (deps de sistema no Windows) |
| `leaflet`/`react-leaflet` | Mapa interativo no frontend | frontend | baixo |

**Nada é instalado sem o dono aprovar** (regra do projeto).

---

## 5. Riscos e guardrails

| Risco | Mitigação |
|---|---|
| Consultor vê dados de outros | Filtro estrito por `assigned_to_id` + testes de isolamento |
| Analista exporta dados sensíveis | PDF org-scoped; papéis validados no backend (não só na UI) |
| Atribuição duplicada / corrida | Constraint/verificação no `assign`; registrar na trilha |
| Enriquecimento de site sai do escopo passivo | Reutilizar dados já coletados; **nunca** adicionar probe ativo |
| PDF pesado/lento | Cache do agregado; geração assíncrona se necessário |
| Papel definido globalmente vaza entre empresas | `sales_role` é por `organization_members`, não global |

---

## 6. Ordem de branches / PRs (checklist)

| # | Branch | Bloco | Depende de | PR (manual) |
|---|---|---|---|---|
| 1 | `feat/sales-intel-assignment` | X1 | — | após testes atribuição |
| 2 | `feat/sales-intel-roles` | X2 | X1 | após testes papéis |
| 3 | `feat/sales-intel-analytics` | X3 | X1+X2 | após validação métricas |
| 4 | `feat/sales-intel-pdf` | X4 | X3 | após validar PDF |
| 5 | `feat/sales-intel-web` | X5 | X2+X3 | após validar UI |
| 6 | `feat/sales-intel-pitch` | X6 | X1 (pitch) | a qualquer momento |

---

## 7. Rastreio rápido de status

| Bloco | Status | Notas |
|---|---|---|
| X1 Fundação (atribuição + trilha) | ⬜ Não iniciado | Base de tudo |
| X2 Papéis de venda | ⬜ Não iniciado | CONSULTOR/ANALYST/MANAGER |
| X3 APIs de BI | ⬜ Não iniciado | overview/consultants/ranking/geo/campaigns/timeline |
| X4 Exportação PDF | ⬜ Não iniciado | reportlab ou weasyprint |
| X5 Frontend (relatórios/kanban/mapa) | ⬜ Não iniciado | Leaflet + Recharts |
| X6 Pitch one-pager + site audit | ⬜ Não iniciado | Reusa scoring/enriquecimento |

Atualizar esta tabela a cada merge.
