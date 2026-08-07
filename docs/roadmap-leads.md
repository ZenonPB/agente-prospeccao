# Roadmap — Leads, Scoring e Funil de Vendas Alphamec

> **Mapa-norte do sistema de prospecção.** Reúne, de forma detalhada: (1) as
> **soluções propostas** para os problemas de qualificação/scoring levantados nas
> últimas sessões e (2) a **análise da planilha inteligente do setor de vendas da
> Alphamec** (`docs/planilha_alphamec_atual.xlsx`) com o plano de trazê-la para o
> sistema — para finalmente largarmos as planilhas.
>
> Leitura recomendada antes: `docs/business-rules.md` (funil e regras) e
> `docs/architecture.md`. Atualize este arquivo a cada sessão em que algo for
> implementado.

---

## 1. Objetivo

O sistema já coleta leads (Places/CNAE/CSV), enriquece (técnico + cadastral),
pontua (0–100, LLM) e organiza no funil. Porém, na prática, a **ordenação de
prospecção** estava errada para campanhas que vendem **serviço digital (site)**:

- leads **com** site bonito/funcional saíam como os **melhores** (nota alta);
- leads **sem site próprio** (os verdadeiros compradores de um site) ficavam
  invisíveis (NOVO, score 0);
- os **pitches/assuntos** gerados repetiam "CTA de matrícula — alunos perdidos"
  para **qualquer** negócio (inclusive confeitaria).

Este documento registra as causas, as correções propostas e o plano para
transferir para o sistema os **KPIs e o fluxo de vendas** que hoje a Alphamec
apura manualmente na planilha.

---

# Parte A — Soluções para os problemas de scoring/qualificação

## A.0 Como o scoring funciona hoje

1. **Coleta** (`places_service.py`): grava `Lead.website` com a URL, mas se ela
   apontar para rede social (`is_social_domain`), salva `website=None`
   ("sem site próprio").
2. **Template de critérios** (`CampaignScoringTemplate`): cada campanha resolve
   um template de sinais `positive/negative/context` via `template_router.py`
   (exact → fuzzy → LLM → geração sob demanda via `template_generation_service`).
3. **Enriquecimento + scoring** (`enrichment_orchestrator.process_single_lead` e
   `scoring_service`): monta um prompt com contexto da campanha + sinais do
   template + facts (técnicos e cadastrais) e pede ao Groq (`llama-3.1-8b-instant`)
   um JSON explicável (score, fatores `+/-`, evidências, prioridade, pitch,
   assunto).
4. **Persistência**: `Lead.qualification_score`, `score_factors`, `evidence`,
   `priority`, `pitch_angle`, `suggested_subject`, e status
   `ANALISADO → QUALIFICADO (≥60) / DESQUALIFICADO (<60)`.

Os quatro problemas abaixo vêm de **falhas de entrada** (prompt/template/
classificação), não do modelo em si.

---

## A.1 P1 — Template de scoring "invertido" (presença online = sinal positivo)

**Sintoma:** leads com site bonito e funcional pontuando 85/74/60 (HOT) e
explicando "presença online alta" como fator que **aumenta** o score. Para quem
vende site, o correto é o inverso.

**Evidência no banco:** o template `Desenvolvimento Web para Clínicas de
Psicologia` da campanha de teste (`is_generated=True`) tem como primeiro
`positive_signals`:
`Presença Online — Clínica com site próprio ou perfil em redes sociais — weight: high`.
O motor de scoring segue o "critério orientador" e pontua conforme.

**Causa raiz:** o prompt de `template_generation_service.py` (que cria templates
sob demanda) **não informa a regra de inversão** para serviços digitais — o LLM
genérico trata "boa presença online" como qualidade da empresa, e não como
"quem já tem site maduro não é o comprador".

**Correção:** S1 (Parte B).

---

## A.2 P2 — Pitch/assunto "matrícula" copiado do exemplo do prompt

**Sintoma:** todo lead (clínica, doceria, confeitaria) tem `suggested_subject`
igual a `"Site sem CTA de matrícula — alunos perdidos na homepage"` e o
`pitch_angle` repete o mesmo gancho. Confirmado no banco: todos os leads com
pitch usam o mesmo texto de "matrícula/alunos".

**Causa raiz:** o `RESPONSE_SCHEMA_HINT` de `scoring_service.py` **contém
exemplos reais** para `pitch_angle` e `suggested_subject`:

```
"suggested_subject": "<... ex.: 'Site sem CTA de matrícula — alunos perdidos na homepage'>"
```

O modelo `llama-3.1-8b-instant` (pequeno) **copia o exemplo verbatim** em vez de
gerar conteúdo específico do lead. É o efeito clássico de "few-shot copy" em
modelo pequeno quando o schema traz exemplos com conteúdo detalhado.

**Correção:** S2 (Parte B).

---

## A.3 P3 — Domínios de ferramenta/marketplace tratados como "site próprio"

**Sintoma:** leads que usam **Canva** (`canva.link/...`) ou **link do WhatsApp**
(`api.whatsapp.com/send?phone=...`) para encomendas foram tratados como "têm
site". Foram analisados tecnicamente e pontuados com evidências inventadas
("sem CTA/e-commerce"), ficando 43–45 COLD — exatamente o público-alvo de um
site novo.

**Causa raiz:** `domain_utils._SOCIAL_DOMAINS` inclui `whatsapp.com`/`wa.me`,
mas **não** `api.whatsapp.com` (subdomínio), nem `canva.com`/`canva.link`, nem
marketplaces (ex.: `instadelivery.com.br`). Como `normalize_domain`/
`is_social_domain` checam só o host exato, essas URLs passam como site válido →
o lead é enriquecido como se tivesse site → a LLM "cria" o problema do site
imaginário.

**Correção:** S3 (Parte B).

---

## A.4 P4 — Lead sem site nunca pontuado em campanha web

**Sintoma:** os leads **sem site** da campanha ficam `NOVO`, `score=0`,
invisíveis na trilha — e para vendedor de site, quem **não tem site** é o
melhor prospect.

**Causa raiz (2 pontos):**
1. `pipeline_worker.py`: em campanha `WEB_PRESENCE` há o filtro
   `Lead.website.isnot(None)` — leads sem site saem do lote de análise. O mesmo
   acontece em `main.py` (`run_lead_enrichment_and_scoring`,
   `Lead.website.isnot(None)`).
2. Como não entram, o **caminho business de lead sem site** que já existe no
   orquestrador (item 4.2: "para quem vende sites, empresa sem site é
   público-alvo — faz scoring business") **não é alcançado** nesse fluxo.

**Correção:** S4 (Parte B).

---

# Parte B — Soluções propostas (detalhadas)

## B.1 S1 — Regra de inversão na geração de templates para serviços digitais

**Arquivo:** `services/workers/src/services/template_generation_service.py`

Adicionar ao `SYSTEM_PROMPT`/`build_prompt` a regra:

> "Se o serviço a ser vendido É digital (sites, landing pages, SEO, e-commerce,
> marketing digital), a **qualidade da presença digital atual do prospect é um
> sinal de oportunidade INVERTIDO**: presença ausente/fraca/desatualizada
> AUMENTA o score (é o comprador); presença madura/moderna DIMINUI.
> `positive_signals` devem descrever o que torna o prospect comprador (ex.:
> sem site próprio; usa Instagram/Canva; site antigo sem CTA), e
> `negative_signals` o que indica que ele já possui (ex.: site moderno,
> e-commerce integrado, SEO sólido)."

Efeito: templates gerados por IA em novas campanhas de serviço web já nascem com
a lógica correta.

---

## B.2 S2 — Prompt de scoring sem exemplos copiáveis + regra anti-cópia

**Arquivo:** `services/workers/src/services/scoring_service.py`

- No `RESPONSE_SCHEMA_HINT`, **remover os exemplos com conteúdo real** de
  `pitch_angle`, `suggested_subject` (e de `score_factors`/`evidence`),
  deixando placeholders neutros.
- Adicionar instrução explícita (no `SYSTEM_PROMPT` e antes do schema):

> "NÃO copie/repita exemplos deste schema. Gere texto **específico** do lead com
> base em `evidence[]`. Se o lead **não tem site próprio** (usa
> Instagram/Canva/WhatsApp ou não tem presença digital), o gancho e o assunto
> devem citar essa ausência/ferramenta como barreira concreta."

Efeito: elimina o pitch "matrícula" repetido e força contexto real do lead em
todos os textos gerados.

---

## B.3 S3 — Ampliar a classificação "sem site próprio"

**Arquivo:** `services/workers/src/services/domain_utils.py` (usado por
`places_service`, `pipeline_worker`, `main`, `contact_enrichment`, dedupe)

- Tratar como **"não é site próprio"**:
  - `canva.com`, `canva.link` (ferramenta de design);
  - WhatsApp: `api.whatsapp.com` e demais subdomínios de raízes sociais;
  - marketplaces/storefronts de terceiros (ex.: `instadelivery.com.br`) em uma
    lista própria.
- **Subdomínios**: checar se o host pertence a uma raiz social/ferramenta
  (ex.: `*.whatsapp.com`, `*.canva.com`) — hoje a checagem é só do host exato.
- Como `places_service` já usa `is_social_domain` para gravar `website=None` na
  coleta, ampliar o conjunto faz a coleta já classificar corretamente. Leads já
  coletados (teste) não são alterados automaticamente — ver B.5.

Efeito: ninguém mais é enriquecido/pontuado como "tem site" quando o "site" era
um link de Canva/WhatsApp/marketplace.

---

## B.4 S4 — Pontuar leads sem site também em campanhas web

**Arquivos:** `services/api/src/pipeline_worker.py` (filtro ~linha 347) e
`services/workers/src/main.py` (linha 109, `Lead.website.isnot(None)`)

- Remover o filtro `Lead.website.isnot(None)` em campanhas `WEB_PRESENCE`,
  incluindo leads sem site no lote de análise.
- O orquestrador já tem o caminho **business (item 4.2)**: quando o lead não tem
  site e `analysis_profile == WEB_PRESENCE`, chama `score_business_lead` (sem
  facts técnicos, usando categoria/cidade/estado + sinais do template).

Efeito: leads sem site ganham score e entram no funil; com os sinais corrigidos
(B.1/B.5) passam a pontuar alto e a ser priorizados.

> ⚠️ **Decisão de negócio (registrada):** muda a regra documentada "lead sem site
> fica NOVO e pula o técnico". Em campanhas web, **lead sem site passa a ser
> pontuado** pelo caminho business. Confirmado pelo dono do produto.

---

## B.5 S5 — Correção do template gerado da campanha (banco)

**Onde:** correção de dados (não é migration).

- Corrigir o template `Desenvolvimento Web para Clínicas de Psicologia`
  (`16b2e039-93c5-4574-83cd-bedd8b23d0ea`, `is_generated=True`):
  - remover `Presença Online` de `positive_signals`;
  - mover para `negative_signals` ("presença madura — site próprio moderno",
    weight high);
  - adicionar `positive_signals`: "Sem site próprio / usa redes sociais ou
    Canva" (high), "Site desatualizado sem CTA" (high) etc., alinhado ao seed
    "Desenvolvimento de Sites".
- **Política de reanálise:** **não reanalisar** os dados atuais (são de teste do
  sistema). A correção vale para **novas coletas e novas campanhas**. Quando a
  operação for real, usar `POST /api/campaigns/{id}/reanalyze`.

---

## B.6 Boa prática de regressão (antes do go-live)

- Smoke test de scoring com 3 leads: (a) confeitaria sem site (usa Canva) →
  deve pontuar `QUALIFICADO/HOT` com pitch citando ausência de site; (b) clínica
  com site bom → para campanha de site, `DESQUALIFICADO/COLD`; (c) qualquer lead
  → o pitch **não** pode conter "matrícula/alunos".
- Teste determinístico de `domain_utils`: `api.whatsapp.com`, `canva.link`,
  `instagram.com` → `normalize_domain()==None` e `is_social_domain()==True`.

---

# Parte C — Análise da planilha Alphamec

Arquivo: `docs/planilha_alphamec_atual.xlsx`.

A planilha é a base atual de operação do setor de vendas. **Não contém
fórmulas**; os indicadores são apurados manualmente pela analista e pela
diretora de vendas. São 8 abas: 7 por consultor (`GUI`, `LEO`, `Rapha`, `Maria`,
`Zenon`, `GUZZO`, `ARTHUR`) + 1 modelo vazio (`Cópia de Cópia de Cópia de padr`).

## C.1 Estrutura de cada aba (consultor)

Cada aba é uma **lista de leads** com o histórico de prospecção e pós-venda:

| Col | Campo                          | Tipo / valor                              | Obs                          |
|-----|--------------------------------|-------------------------------------------|------------------------------|
| A   | `LEAD`                         | Nome do contato decisor                    |                              |
| B   | `Empresa`                      | Nome do cliente                            |                              |
| C   | `Prospecção`                   | Data de início (serial Excel 46xxx = 2026) |                              |
| D   | `PITCH ENVIADO`                | flag 0/1                                   |                              |
| E   | `PITCH`                        | Data de envio do pitch                     |                              |
| F/G/H | `1º/2º/3º Follow-up`         | Datas da cadência                          |                              |
| I   | `RESPONDEU?`                   | dropdown `SIM,NÃO`                         |                              |
| J   | `CARGO`                        | dropdown `GERENTE,DIRETOR,CEO`             |                              |
| K   | `Observações lead`            | texto livre                                |                              |
| L   | `Status`                       | dropdown `RD,ORÇAMENTO,RP`                 | funil de negociação          |
| M   | `DATA status`                  | data da última mudança de status           |                              |
| N   | `CONTRATO FINAL`              | dropdown `APROVADO,REPROVADO,EM ANÁLISE`   |                              |
| O   | `ANOTAÇÕES`                   | texto livre                                |                              |
| P   | `DATA CONTATO PÓS-VENDA`      | data do 1º contato pós-venda               |                              |
| Q   | `Follow-up` (pós-venda)        | encaminhamento pós-venda                   |                              |
| R   | `PÓS VENDA POR`               | dropdown `WhatsApp,E-mail`                 | canal do pós-venda           |
| S   | `Link ou Telefone ou e-mail`  | canal de contato do lead                   |                              |

**Variações por aba:** a aba `ARTHUR` tem um `4º Follow-up` extra e a posição das
colunas desloca (Status em M, contrato em P, etc.); as demais seguem o padrão.
O modelo (`PAD`) está vazio e é a referência de estrutura.

**Vocabulário (dropdowns) extraído:**
- `RESPONDEU?`: `SIM,NÃO`
- `CARGO`: `GERENTE,DIRETOR,CEO`
- `Status`: `RD,ORÇAMENTO,RP`
- `CONTRATO FINAL`: `APROVADO,REPROVADO,EM ANÁLISE`
- `PÓS VENDA POR`: `WhatsApp,E-mail`

## C.2 Como os cálculos de rendimento são feitos hoje

Sem fórmulas, os indicadores são contados manualmente (filtro/contagem):

- Nº de leads por consultor (linhas da aba);
- % de pitch enviado (contagem de `D=1`);
- % de resposta (`I=SIM` sobre pitches enviados);
- distribuição de `Status` (`RD` / `ORÇAMENTO` / `RP`);
- nº de contratos `APROVADO` / `REPROVADO` / `EM ANÁLISE`;
- canal de contato/pós-venda (`WhatsApp` / `E-mail`);
- tempo de cadência (datas de pitch → follow-ups → resposta);
- notas (`K`/`O`) para acompanhamento manual.

## C.3 Plano de adaptação ao sistema (fase futura)

A etapa final deste roadmap — para abandonarmos a planilha.

### Mapeamento campo a campo

| Planilha                                 | Sistema (modelo atual)                                | Status            |
|------------------------------------------|-------------------------------------------------------|-------------------|
| A `LEAD` (decisor)                        | `Contact` (`name`, `role`/`role_label`)               | ✅ existe         |
| B `Empresa`                               | `Lead.company_name`                                   | ✅ existe         |
| C `Prospecção` (data)                     | `Lead.created_at`                                     | ✅ existe         |
| D `PITCH ENVIADO` + E `PITCH` (data)      | `FollowUp(step=OPENING)`: `status`/`sent_at`          | ✅ existe (cadência) |
| F/G/H follow-ups (1º/2º/3º)               | `FollowUp(step=FOLLOWUP_1/FOLLOWUP_2/CLOSING)`        | ✅ existe (cadência) |
| I `RESPONDEU?`                            | `Message.responded_at`/`is_response`; `Lead.status=RESPONDIDO` | ✅ existe |
| J `CARGO`                                 | `Contact.role`                                        | ✅ existe         |
| K `Observações lead`                      | `Lead.notes`                                          | ✅ existe         |
| L `Status` (RD/ORÇAMENTO/RP)              | `Lead.negotiation_stage` (enum `RD/ORCAMENTO/RP`) + `PATCH /leads/{id}/negotiation` | ✅ implementado (2026-08-06) |
| M `DATA status`                           | `lead_activities` (STATUS_CHANGED) / `Lead.outcome_date` | ✅ existe |
| N `CONTRATO FINAL` (APROVADO/REPROVADO)   | `Lead.contract_outcome` (enum `APROVADO/REPROVADO/EM_ANALISE`); conversão marca `APROVADO` | ✅ implementado (2026-08-06) |
| O `ANOTAÇÕES`                             | `Lead.notes` (junto de K)                             | ✅/🔶            |
| P/Q/R/S pós-venda                         | **módulo pós-venda (não existe ainda no sistema)**    | 🔶 novo módulo    |

> Detalhe importante: `RD` (reunião de demonstração), `ORÇAMENTO` e `RP`
> (reunião de proposta) são estágios do funil **interno** da Alphamec que
> acontecem entre "respondeu" e "fechou" — não têm 1:1 com o funil atual do
> sistema. Foram mapeados para `Lead.negotiation_stage`, gravados quando o
> lead está em `RESPONDIDO/REUNIAO_MARCADA/REUNIAO_FEITA/PROPOSTA_ENVIADA`
> (branch `feat/negotiation-funnel`, migration `f5a6b7c8d9e0`).

### Entregáveis planejados

1. **Dashboard de rendimento por consultor** (usar o que já existe em
   `GET /api/analytics/consultants`) com os KPIs da planilha:
   - leads em carteira; % pitch enviado; % resposta; % em RD/ORÇAMENTO/RP;
   - % contrato APROVADO; ticket médio (`Conversion.contract_value`);
   - tempo de cadência (pitch→resposta) e tempo de fechamento
     (`Conversion.time_to_close_days`);
   - canal de contato (WhatsApp/e-mail); rankings por conversão.
2. **Tela por consultor** (equivalente à aba da planilha): funil filtrado por
   pessoa, trilha de atividades, filtros por status/data/campanha.
3. **Pós-venda automatizado**: follow-up de pós-cliente usando o mesmo motor do
   scheduler de cadência (follow_ups) + registro do canal.

---

# Parte D — Priorização

1. **[Alta] B.3 (domain_utils) + B.4 (pontuar sem site)** — corrige a lista de
   oportunidades e valoriza o alvo certo (quem não tem site).
2. **[Alta] B.2 (prompt sem exemplos)** — elimina pitches errados em todo o
   sistema.
3. **[Média] B.1 (regra de inversão na geração) + B.5 (template da campanha)** —
   garante campanhas novas corretas.
4. **[Baixa/fase] C.3 (dashboard, funil de negociação, pós-venda)** — módulo
   para largar a planilha.
5. **Antes do go-live**: rodar B.6 (regressão) e reanalisar quando a operação
   for real.

---

# Decisões registradas

- ✅ **Não reanalisar** os dados atuais (são para teste do sistema). As correções
  entram em efeito em novas coletas e novas campanhas; quando a operação for
  real, usamos `reanalyze`.
- ✅ **canva, WhatsApp (`api.whatsapp.com`), marketplaces = "sem site próprio"**.
- ✅ **Pontuar leads sem site** em campanhas `WEB_PRESENCE` — são o alvo em venda
  de site.
- ✅ **Funil de negociação (`RD/ORÇAMENTO/RP`) e resultado de contrato**
  (`APROVADO/REPROVADO/EM ANÁLISE`) implementados como `Lead.negotiation_stage`
  e `Lead.contract_outcome` (2026-08-06).
- 🔶 **Módulo de pós-venda** a criar (`DATA CONTATO PÓS-VENDA`, `PÓS VENDA POR`).

---

## Como manter

- Ao implementar cada solução, mova do "Proposto" para "Implementado" e anote o
  commit/hash.
- Atualize o `docs/context.md` (Estado atual e Próximo passo imediato) no fim de
  cada sessão que toque este tema.
- Este documento é complemento de `docs/roadmap-vendas.md` (visão de produto),
  com foco **executável** em leads/scoring/funil.

---

# Parte E — Status de implementação (2026-08-05)

Branch: `fix/roadmap-leads-scoring`. Todas as soluções do roadmap foram
aplicadas. Os quatro problemas de qualificação (P1–P4) estão **corrigidos**.

## Implementado

- ✅ **S1 (P1) — regra de inversão para serviços digitais**: adicionada ao
  `SYSTEM_PROMPT` de `template_generation_service.py`. Novos templates gerados
  por IA já nascem com `positive` = comprador (sem site/Instagram/Canva) e
  `negative` = presença madura.
- ✅ **S2 (P2) — prompt sem exemplos copiáveis**: removidos do
  `RESPONSE_SCHEMA_HINT` de `scoring_service.py` os exemplos reais
  (`pitch_angle`/`suggested_subject` "matrícula/alunos") e adicionada regra
  **anti-copy** + gancho obrigatório para lead sem site no `SYSTEM_PROMPT`.
- ✅ **S3 (P3) — domínios de ferramenta/marketplace = "sem site próprio"**:
  `domain_utils.py` passa a tratar `canva.com`/`canva.link`, `api.whatsapp.com`
  (via **subdomínio de raiz social**) e marketplaces (`instadelivery.com.br`,
  iFood, etc.) como sem site próprio, tanto em `normalize_domain` quanto em
  `is_social_domain`. `places_service` (coleta) e `csv_import_service` já usam
  essas funções, então novas coletas classificam corretamente.
- ✅ **S4 (P4) — pontuar leads sem site**: removido o filtro
  `Lead.website.isnot(None)` do `pipeline_worker.py` (campanhas `WEB_PRESENCE`)
  e de `main.py`/`run_lead_enrichment_and_scoring`. O orquestrador roteia lead
  sem site para o scoring business (item 4.2).
- ✅ **S5 — resolvida via reset do banco**: o template `is_generated=True`
  corrompido da campanha de teste (`Desenvolvimento Web para Clínicas de
  Psicologia`, com "Presença Online" como positive signal) foi eliminado. O banco
  foi **resetado por completo** e reaplicado `alembic upgrade head` +
  `python -m src.seeds.scoring_templates` (9 templates). O seed "Desenvolvimento
  de Sites" já usa lógica correta (ausência = positivo, presença madura =
  negativo). **Nenhum dado foi reanalisado** (decisão registrada mantida).

## Verificação

- **B.6 — smoke teste**: (a) confeitaria sem site (Canva) → `85 HOT`, pitch
  "não tem site próprio... pedidos dependem do Instagram"; (b) clínica com site
  moderno → `40 COLD` para campanha de site; (c) nenhum pitch contém
  "matrícula/alunos".
- **Testes determinísticos** de `domain_utils`: `api.whatsapp.com`,
  `canva.link`, `canva.com`, `instadelivery.com.br` → `normalize_domain=None` /
  `is_social_domain=True`; sites reais continuam normalizados.

## Commits

- `43d874c` — fix(scoring): apply roadmap-leads S1-S4 (inversion rule,
  anti-copy prompt, no-site scoring).
- `fa59c36` — merge do PR #47 em `main` (S1–S4 no branch principal).

## Gaps residuais fechados (2026-08-05, branch `fix/lead-scoring-residuals`)

Após o merge, dois pontos do roadmap ainda não estavam cobertos no `main`:

- **B.3 no caminho CSV**: `csv_import_service` só usava `normalize_domain` (dedupe) e
  gravava `website` como veio — lead via CSV com `canva.link`/`api.whatsapp.com`/
  `instadelivery.com.br` era tratado como "tem site" (P3 reincidia). Novo helper
  `normalize_import_website()` anula via `is_social_domain` (espelha `places_service`).
  Coberto por `test_normalize_import_website_*` em `tests/test_csv_import.py`.
- **S5 sem reset do banco**: script `services/workers/src/scripts/fix_generated_web_templates.py`
  (idempotente; dry-run por padrão, aplicar com `--apply`) detecta templates
  `is_generated=True` com "presença online/site próprio" como sinal positivo (assinatura
  pré-S1), realinha as campanhas ao seed global "Desenvolvimento de Sites" e exclui o
  template corrompido — sem alterar leads. Para a operação real, reavaliar com
  `POST /api/campaigns/{id}/reanalyze`. Testes em `tests/test_fix_web_templates.py`.

**Verificação**: smoke determinístico (CSV + domínios S3) e detecção do script OK;
`py_compile` dos arquivos tocados OK.
