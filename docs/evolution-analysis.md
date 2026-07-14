# Análise de Evolução — De coletor a Assistente de Inteligência Comercial

> Sessão de 2026-07-09. Análise conceitual e roadmap. NÃO substitui `product-vision.md`;
> `-o complementa` e propõe uma evolução dele. Não propõe código — apenas conceito.

## Premissa

O usuário visa reposicionar a plataforma de "coletor de empresas com score" para
"assistente de inteligência comercial para PMEs brasileiras que prestam serviços"
(tech, engenharia, marketing, consultoria, automação). Este documento mapeia
o que existe hoje, onde ficará raso, e propõe evolução. Inspirado
conceitualmente em Apollo.io (NÃO em funcionalidades).

---

## 1. Maiores pontos fracos da plataforma hoje

Resultado do mapeamento factual contra código e docs:

### 1.1. Coleta é "uma query textual" — não é segmentação real
- `places_service.py:89` faz `searchText` no Google Places com uma string
  única (ex.: "Restaurante em Araraquara"). Não há location bias/radius, não
  há filtros por `primaryType`, não há paginação exposta ao usuário.
- **Impacto**: para "Engenharia Mecânica" a coleta não descobre fábricas —
  adivinha-as a partir de keywords. Mistura segmentos, polui a campanha.

### 1.2. Enriquecimento técnico é "web-only"
- `technical_enrichment_service.py` só analisa sites: SSL/CMS/SEO/performance.
  Para uma campanha de Engenharia Mecânica, isto é praticamente inútil.
- Os campos `responsive_design`, `lighthouse_score`, `seo_errors`
  (`models.py:131-134`) **não são preenchidos** — a migration criou as
  colunas mas o serviço nunca as usa.
- Não existe enriquecimento de **negócio**: CNPJ/porte/receita/CNAE,
  Hunter.io p/ decisores, idade do domínio, expansão recente, menções em
  redes sociais, Machine Learning em páginas (sobre/equipe/produtos).

### 1.3. Scoring foi "corrigido" mas continua **única fonte de verdade**
- A última sessão resolveu o problema de "scoring específico de tecnologia"
  com templates contextuais (`campaign_scoring_templates`), e o problema
  de "falta de explicabilidade" com `score_factors`/`evidence`/`priority`.
- Mas a IA ainda produz **uma única opinião monolítica** por lead. Não há
  avaliação separada por dimensão (maturidade digital, fito comercial,
  urgência), não há estimativa de potencial de compra, não há proposta
  de objection handling. Tudo fica misturado dentro de `qualification_reason`.

### 1.4. Analysis Profile é um binômio, não um dossiê
- `AnalysisProfile` é um enum de 2 valores (`web_presence`/`business_opportunity`)
  que apenas roteia o pipeline entre "enriquece site" e "não enriquece".
  **Não é um documento**: é uma flag de dispatch.
- A página de detalhe do lead tem um card "Aptidão" com score + reason +
  primary_need mais um card "Evidências" (nova) — mas não há um **dossiê**
  estruturado: quem é a empresa, dores prováveis, sinais de oportunidade,
  maturidade, previsão de fito. Falta uma visualização narrativa.

### 1.5. Geração de mensagens NÃO EXISTE
- `interface.md:224-228` promete botão "Gerar Pitch" com modal
  (Copiar/Regenerar/Editar). Não há handler — botão inerte.
- O "pitch" atual é `pitch_angle` (1-2 frases) + `suggested_subject` (assunto
  de e-mail), produzidos como subprodutos do scoring pelo mesmo modelo
  8B. **Não há corpo de e-mail de prospecção atualizado, nem follow-up,
  nem sequência de cadência.** Storystorm: o vendedor chega ao detalhe do
  lead e não tem nada pronto para atuar — aborta o ciclo comercial.

### 1.6. Dashboard responde a "o que tem" mas não a "o que fazer"
- Cards de métricas + funil + "atividade recente" (últimos 5 leads) +
  "O que fazer agora" (`quick-actions.tsx`).
- Mas as 3 sugestões do QuickActions são contadores estáticos
  ("Prosseguir com contatos", "Fazer follow-up", "Expandir busca") —
  **não há priorização inteligente**, não há "lead X estáparado há 9 dias",
  não há "campanha Y converteu 3x mais que Z". Falta um feed de
  **ações priorizadas pelo impacto esperado**.

### 1.7. Funil de vendas é só um Kanban de status
- `vendas/page.tsx` arrasta cards entre 5 colunas. Não há:
  - histórico de interações (apenas marca status),
  - timeline de follow-ups enviados,
  - sugestão de próxima ação por lead,
  - alerta de lead esquecido,
  - "marcar como perdido com motivo",
  - *cadências* (quando enviar dia 3 / 7 / 14 / encerrar),
  - integração de envio real (Resend) nem agendamento (Cal.com).
- A coluna "dias" usa `created_at` (data de coleta) — não **dias desde o
  último contato**. Falta uma tabela `lead_events` que rastreie ações
  separadamente dos status.

### 1.8. Visão documentada está DESATUALIZADA
- `product-vision.md` continua a descrever a plataforma como ferramenta
  para dev houses ("dois desenvolvedores full stack que vendem software"),
  mantém a tabela de scoring de web (`.env exposto`, "WordPress detectado")
  ainda no texto, e lista o `primary_need` como enum web fixo.
- Isto é um risco maior que parece: novos PRs vão se basear em docs
  contraditórios com a realidade contextual já implementada. **A visão
  precisa de reescrita como primeira ação.**

### 1.9. Aprendizado contínuo (Fase 5) está completamente ausente
- `Conversion` model existe (`models.py:209-223`) mas **não há endpoint
  para registrá-las**, nem leitura no scoring. Nenhum insights sobre
  "perfis que convertem mais". Sem isso, a IA não aprende com a base real
  do usuário — o Apollo.io ganha com agilidade de otimização, e a
  plataforma fica estática.

### 1.10. Não existe conceito de Audience ou Listas inteligentes
- Campanhas são isoladas por `campaign_id`. Não há conceito de "todos
  leads com score > 80 e prioridade HOT independentemente da campanha".
  Falta uma camada de **audience builder** que segmente leads por sinais
  cruzados, essencial para rodar sequences diferentes por persona.

### 1.11. Não existe decisor atribuído ao lead
- Tabela `Lead` tem apenas `email` genérico. **Não há tabela `contacts`**
  (apesar de `product-vision.md:101` prometer). Sem nome+cargo do
  decisor, a mensagem de outreach é endereçada a "Olá!" — baixíssima
  resposta. Isto é o **maior gap isolado** na comparação com Apollo.io.

---

## 2. O que falta para a IA atuar como consultor comercial

Hoje a IA devolve 6 campos (score, primary_need, qualification_reason,
priority, priority_reasoning, executive_summary) e 2 subprodutos
(pitch_angle, suggested_subject). Para virar consultor:

### 2.1. Raciocínio multi-dimensional, não monolítico
Avaliar separadamente dimensões independentes, cada uma com notas e
evidências:
- **Fito comercial** — este lead precisa do que vendemos?
- **Maturidade digital** — grau de prontidão para aceitar nossa proposta.
- **Potencial de compra** — orçamento provável, ticket médio.
- **Urgência** — sinais de momento (expansão, regulatório, crescimento).
- **Acessibilidade** — quão fácil contatar um decisor.

Cada dimensão = uma coluna no Lead + saída JSONB separada da LLM. O score
global passa a ser **média ponderada** (pesos definidos no template, não
ad hoc), e o usuário pode reordenar critérios no template.

### 2.2. Hipótese de dores prováveis
Hoje: `primary_need` é uma string ("modernizar site"). Faltam:
- Lista de **dores prováveis** ("provável", não "confirmado" — ética):
  - clientes podem estar perdendo conversão (evidência: site sem CTA);
  - equipe sobrecarregada (evidência: categoria = varejo, sem e-commerce);
  - expansão iminente (evidência: categoria + localização + website recentes).
- Cada dor com: `pain_hypothesis`, `evidence`, `confidence`

### 2.3. Idéias proativas (não esperadas para regargear)
Exemplos:
- Detectar que "academia tem IG ativo mas sem link no site" é uma **incoerência**
  de presença digital — gap facilmente colocável.
- Quase-but-not-quite. Hoje são findings. A próxima iteração deve ser **insights**.
- Insights surgem quando a IA relaciona evidências com o template de serviço.

### 2.4. Argumentários priorizados
- Lista de **argumentos comercialmente eficazes**, priorizados por impacto
  esperado, cada um com `angle`, `evidence_ref`, `objection_risk`,
  `expected_objection_response`.
- Diferente de `pitch_angle`: o pitch é só o tópico. O argumentário é um
  menu de 5 tópicos que o vendedor seleciona na reunião.

### 2.5. Objeções prováveis e respostas sugeridas
- "Caro demais", "não temos verba", "não é prioridade agora", "já temos alguém".
- A LLM prever top-3 objeções para **este lead neste contexto** com
  respostas-category-based.

### 2.6. Previsão de interesse — não só de oportunidade
- Score atual = oportunidade (este lead tem problema que meu serviço resolve).
- Falta um campo `interest_prediction`: "vantagem competitiva %":
  - HIGH: alta chance de marcar reunião na primeira mensagem.
  - MEDIUM: requer mensagem com pitch ótimo.
  - LOW: precisa de várias mensagens / warm-up via conteúdo.
- Esta métrica só faz sentido após Fase 5 (aprender com conversões
  passadas). Enquanto isso, a LLM pode estimar com base em sinais.

### 2.7. Briefing comercial narrativo (1-pager)
A LLM produz um 1-pager no estilo McKinsey briefing: "quem é a empresa,
o que vimos, nossa tese, abordagem recomendada, principais riscos".
Similar `executive_summary` mas **estruturado** em cabeçalhos — não texto corrido.

### 2.8. **Cadência sequencial de abertura** (NÃO body do e-mail)
Recomendar a abordagem inicial: **rei avaliando estrutura comercial**
- "Primeiro e-mail: lead com dor X — use argumento de Y."
- "Follow-up 1 (dia 3): se não respondeu, mude ângulo para Z."
- "Follow-up 2 (dia 7): caso-1 de caso similar."

Tudo antes de enviar o e-mail.[...]

---

## 3. Arquitetura escalável para qualificação contextual por campanha

**Já comecei isso na sessão anterior** com `CampaignScoringTemplate`. O
caminho está certo; falta **amadurecer de "critérios" para
"playbook"**.

### 3.1. Template = playbook completo, não lista de critérios

Hoje o template tem `positive_signals`/`negative_signals`/`context_signals`
+ `requires_technical_report` + `extra_instructions`. Propõe-se ampliar para:

| Campo | Hoje | Evolução |
|---|---|---|
| `service_label` | ✅ | ✅ |
| `positive_signals` | ✅ | ✅ |
| `negative_signals` | ✅ | ✅ |
| `context_signals` | ✅ | ✅ |
| `requires_technical_report` | ✅ | ✅ |
| `extra_instructions` | ✅ | ✅ |
| `dimensions` | 🔴 | Lista de **dimensões** a avaliar: fit, maturidade, potencial, urgência, acessibilidade. Cada uma com peso (default 0.2 para 5 dims). |
| `lead_signals` | 🔴 | Sinais não-web: CNAEs-alvo, faixas de porte, "nicho" (indústria/varejo/serviço), idade do negócio, tipo de contato-alvo (CEO/ sócio/owner). |
| `expected_pains` | 🔴 | Hipóteses de doresily recorrentes neste serviçoç |
| `objections_playbook` | 🔴 | Top-N objeções esperadas para este serviço, com respostas entreprise. |
| `first_message_angle` | 🔴 | Tópico de abertura recomendado default (pode ser override por lead). |
| `legal_warnings` | 🔴 | Anotações como "este serviço envolve dados pessoais — cifrar proposta" / "não automatizar envio em LinkedIn". |

### 3.2. Plugin de coleta ≠ plugin de scoring

Hoje `places_service.py` não respeita o template. Propõe-se:
- Template declara `lead_signals` (porte, CNAE, nicho).
- `places_service.search` aplica **post-filter** sobre os resultados do
  Google Places cortando leads fora do fit (alinha categoria com
  "indústria/varejo/serviços" esperado).
- Adicionalmente, novos "providers" de coleta (CNPJ receita, dorks de
  Google Search, IG busca) podem ser plugins selecionáveis por template.

### 3.3. Composição de providers de enriquecimento

Hoje `enrichment_orchestrator` decide apenas `use_technical_report`.
Propõe-se:

```
lead →
  providers-declared-by-template:[]
      → cada provider retorna facts[]
      → facts[] agregados → prompt LLM → scoring
```

Providers existentes ou futuros:
- `TechnicalEnrichmentService` (já existe) → facts SSL/CMS/SEO etc.
- `CnpjEnrichmentService` (futuro) → facts porte/CNAE/situação/sócios.
- `HunterService` (futuro) → facts decisores/email/confidence.
- `SocialsEnrichmentService` (futuro) → facts IG/FB presença/atividade.
- `DomainAgeService` (futuro) → facts idade-domínio/expansão.

O template diz quais providers ativar. **Sem if/else** — registry de
providers, template referencia por nome.

### 3.4. Registry pattern para providers

```python
ENRICHMENT_PROVIDERS = {
    "technical": TechnicalEnrichmentService,
    "cnpj": CnpjEnrichmentService,
    "hunter": HunterService,
    "socials": SocialsEnrichmentService,
    "domain_age": DomainAgeService,
}
# template declares:
template.providers = ["technical", "cnpj", "hunter"]
```

Sem if-else. Adicionar novo provider = registrar uma entrada.
Adicionar nova categoria de serviço = novo row em `campaign_scoring_templates`
com providers + critérios relevantes. **Zero alteração de código.**

### 3.5. Recalibração por conversões (Fase 5)

`Conversion` model existe mas não é usado. Propõe-se:
- Endpoint `POST /api/leads/{id}/convert` registra outcome.
- A cada N conversões (10, 50?), um job treina micro-ajustes de pesos
  do template automaticamente, ou recomenda ao admin: "para leads do
  segmento X, peso de 'maturidade digital' está sobre-estimado".

Isto recoloca a IA dentro do loop de otimização — Apollo.io ganha
 vantagem competitiva exatamente aqui.

---

## 4. Enriquecer o Analysis Profile: de flag a Dossiê Comercial

Hoje `AnalysisProfile` é binômio (`web_presence`/`business_opportunity`) que
roteia o pipeline. Evolução: cada lead recebe um **dossiê comercial**
estruturado, independente da campanha. O `AnalysisProfile` antigo vira
apenas um hint de pipeline; o verdadeiro documento de inteligência é
o dossiê.

### 4.1. Estrutura proposta do dossiê (por lead)

1. **Identidade** — razão social (após CNPJ), nome fantasia, CNAE, porte,
   idade do negócio (anos), situação cadastral.
2. **Localização & Operação** — endereço, bairro, município, polos
   regionais, indicadores (nº filiais, presença nacional/Regional).
3. **Decisor** — nome+cargo (após Hunter/CNPJ-source), email, telefone,
   confidence, perfil IG/LinkedIn (seacesível manualmente).
4. **Maturidade digital** — site (sim/não), stack, responsive, SEO, LGPD,
   carga de conteúdo, presença em redes sociais, atividade recente.
5. **Sinais de negócio** — categoria (Google Places), tipo (indústria/
   varejo/serviço), porte estimado, expansão recente (filiais/endereços
   novos — após CNPJ segundas filiais).
6. **Hipóteses de dor** (campanha-responsivo) — dores prováveis baseadas
   em template + facts do lead.
7. **Oportunidade contextual** — fito com campanha, primary_need,
   argumentário priorizado de venda para este lead nesta campanha.
8. **Riscos & objeções** — top-3 objeções prováveis + respostas.
9. **Histórico** — coleta, análises anteriores, contatos, respostas,
   reuniões marcadas/feitas, conversões.

### 4.2. Apresentação na UI

Substituir a aba única "Evidências" por uma **experiência narrativa**:

- **Header do dossiê** — badge prioridade, score, fito (%).
- **Cartão "Resumo"** (1-pager IA-style, headers: `Empresa`, `Tese`,
  `Dores prováveis`, `Abordagem`, `Riscos`).
- **Cartão "Decisor & Contato"** (com confidence bar).
- **Cartão "Maturidade digital"** (mini-painel com SSL/CMS/SEO/perf).
- **Cartão "Sinais de negócio"** (porte, expansão, região).
- **Cartão "Evidências & Fatores"** (atual `EvidenceCard` expandido).
- **Cartão "Argumentário"** — lista priorizada de argumentos clicáveis
  (cada um mostra `evidence_ref` e `objection_risk`).
- **Cartão "Objeções prováveis"** — lista com respostas sugeridas.
- **Timeline de histórico** — coleta, contato, follow-ups, reunião,
  conversão.

A página deixa de parecer "ficha técnica" e vira **briefing comercial**.

### 4.3. Estrutura técnica

- Nova tabela `lead_dossiers` (1:0..1 Lead), JSONB denso.
- Não desnormalizar — dossiê é reescrito após uma coleta/mudança de
  campanha.

---

## 5. Análises adicionais que a IA poderia produzir

Topo da análise já feita em `evidence[]`/`score_factors[]`/`priority`.
Propostas de expansão:

| Análise | Descrição | Quando útil |
|---|---|---|
| **dores prováveis** | Top-N hipóteses com confidence e referral-evidência | Pré-reunião |
| **potencial de compra** | Estimativa de ticket médio (S/M/L) baseada em porte + nicho | Priorização |
| **maturidade digital** | Score 0–100 só da presença online; útil para campanhas tech | Filtro / segmentação |
| **argumentos de venda** | Lista 3–5 priorizada por impacto esperado, cada um com evidência | Durante a reunião |
| **objeções prováveis** | Top-3 + respostas sugeridas | Pós-reunião cold |
| **oportunidades encontradas** | Hipóteses de valor com baixo comprometimento ("pode aumentar ticket") | Cross-sell/upsell |
| **serviços recomendados** | Sugestões de serviços complementares alavancáveis | Cross-sell |
| **prioridade** | HOT/WARM/COLD (já existe) + reasoning | Fila |
| **urgência** | HIGH/MEDIUM/LOW separada de prioridade — é o quanto agir rápido vale | Cadência de follow-up |
| **previsão de interesse** | Probabilidade de marcar reunião na primeira mensagem | Sequência de cadência |
| **risco relacional** | "categorizar sem apariência possível de erro" — baseado em contexto (ex.: enquete em homepage indica prontidão para upgrade) | Decisão de "depositar / investir" |
| **horizonte temporal** | "tempo médio para fechar": DIM/NORMAL/LONG baseado em nicho | Previsão de pipeline |
| **riscos comerciais** | "this lead esta mal na tamanho, baixa produtiva, provável dificuldade de pagamento" | Risco conversão→receita |
| **padrão de segmento** | Dossiê comparativo com a média do segmento do usuário | Insights admin |
| **primeiro argumento sugerido** | Semântica "abertura ideal" para este lead especificamente | Mensagem de abertura |

Esses 14 outputs viram colunas JSONB na tabela `lead_dossiers` (ou em
`Lead` direto). A LLM gera tudo numa única chamada (messema tarefa, mesmo
prompt expandir) — mantém custo por lead (lit/Groq) controlado.

---

## 6. O que o vendedor gostaria de saber em 5 minutos antes da reunião

<style> Proposta de "briefing de 5 minutos" gerado automaticamente na aba
"Dossiê Comercial" da página do lead:

### Empresa em 30 segundos
- Nome, ramo, localização, porte estimado, idade.
- CNAE principal (após CNPJ) e diversificação (CNAEs secundárias).
- Quantos funcionários (sócios), filiais (após CNPJ).

### Tese comercial em 60 segundos
- Por que abordamos esta empresa **para esta campanha**.
- "3 indícios de oportunidade" (top-3 evidências prioritárias).
- "1 indício de incerteza / não-fit" (honestidade comercial controlável).

### Decisor (se disponível)
- Nome, cargo, tempo na função (após LinkedIn manual).
- Tom recomendado: "usar Awesome — CEO dificiciente técnico" vs
  "resolver CRM/dash até chegar a deadline".

### Pontos de entrada (proof points)
- "Site sem mobile — 60%+ das visitas saem antes de scroll" (se técnico).
- "Academia em polos desta categoria baixa taxa digital".
- "Clínica atendida em DEstar SP recentemente suggests expansão".

### Cadência já feita
- "Abordagem 1 enviada em 12/06 — não respondida 5 dias".
- "Follow-up 1 em 15/06 — não respondida".
- "Follow-up 2 em 19/06 — aguardando".

### Roteiro de perguntas para a reunião
- 5 perguntas open-ended geradas a partir de evidências e dores prováveis,
  para colocar desafogando na escrita.
- Ex.: "Vocês já usam um sistema de [tipo] integrado? Como é o fluxo
  hoje?"

### Potenciais armadilhas (objeções previstas)
- Top-3 objeções + respostas sugeridas.

### Próxima ação recomendada (pré-reunião)
- "Antes da reunião: verificar IG/LinkedIn da empresa para detectar
  conteúdo recente".
- "Antes da reunião: ler reviews do Google — note reclamaçãoões recorrentes
  pode ser o gancho".

Se o vendedor só tiver **2 minutos**, lê só os "3 indícios" + o "Decisor" +
"Cadência". Se tiver **5 minutos**, lê tudo. Este briefing é o output
máximo da LLM podado a uma tela — deve encher o lead para 1 minuto de
leitura sem árvores.

---

## 7. Como tornar a plataforma difícil de copiar

### 7.1. **Mentalidade do produto**

Antes de funcionalidades — escolher errar. A aposta de produto é:
> "Para cada lead, a plataforma não apenas encontra um problema. Ela
> já chega pronta para o comercial — com tese, prova, objeções e cadência."

A maior fonte de "copiar" de Apollo.io é que ele é Mercado americano com
integrations maduras. **Mudar focus**:
- Apollo: emails + cadência. PMEs brasileiras: WhatsApp + IG + FlyCrm
  sem stack.
- Precisamos ir onde o lead brasileiro "respira": WhatsApp Business,
  Instagram, Google Meu Negócio — e onde o vendedor brasileiro vende:
  status cadência, mensagem por voz日常生活, gerenciamento de carteira
  via WhatsApp + Reagendamento Life Movie.

### 7.2. Diferenciais defensáveis (moat)

**7.2.1. Dossiê comercial narrativo por lead**
Ninguém hoje constrói um **dossiê textual por lead** — Apollo dá uma
ficha com 50 campos. Saída narrativa, estilo McKinsey 1-pager, construída
por LLM contextualizada no serviço do usuário — difícil de copiar porque
requer curadoria humana de playbooks por categoria de serviço.

**7.2.2. Playbook de campanha editable**
Hoje o template é row em DB. Curadoria inicial (entregues na Fase 0)
+ continuuidade via conversões → tese defensável. **Quanto mais o
usuário usa, mais o sistema aprende com os usuários dele específicos**.
Insights só exportando com custom conversões. **Sem compartilhar entre
usuários** inicialmente — VPI espec.

**7.2.3.-Replay baseencoded no relacionamento**
A plataforma torna-se "memória外交部" do vendedor — cada reunião, cada
pergunta feita, cada objeção encontrada, cada impossibilidade se torna
input para os próximos scores. Sem isso, qualquer concorrente é "L: mais um
Apollo clone".

**7.2.4. BI nativo para PMEs brasileiras**
- Heatmap de nicho por região (milhões de CNAEs, IBGE, Receita).
- Curadoria contextualizada para cidade.
 Martinho EUA não tem. (Core mercados em apis tem para EUA.)

**7.2.5. Fluxo comercial brasileiro nativos**
- WhatsApp Business envio (RP feed cada lead = uniformed at Apollo via
  its 但onlyemail).
- CalDAV/agenda Integrar para Reagendar.
- Notas em abordagem Concisa.
- LGPD from início (compliance) — apollo endereço de optout e use MIT
  quando não precisar — para retry para Ford Brasil, LGPD é §义务).

**7.2.6. Pesquisa de Betterment Gina Analytics**
- Not features — feedback loop. VIR feedback loop com LLM resumida.

Esta lista é "conjuntos de escolhas de design" → identificar Min Mexhark
Probância apologético.

---

## 8. Roadmap em prioridade

Critério para priorizar:
1. **UNBLOCK** — resolve gap que impede o fluxo comercial hoje (vendedor não
   tem nada para fazer ao chegar no detalhe do lead) → essenciais.
2. **DEFENSIBILITY** — torna a plataforma *чная para copiar*.
3. **SCALE** — ampliação de tipos de campanha sem código → já parcialmente
   feito; consolidar.

### Fase A — Essenciais (sem os quais a plataforma é uma "demosa" para o
comercial)

| # | Item | Razão | Esforço |
|---|--|--|--|
| A1 | **Reescrever `product-vision.md` refletindo a reposicionalização** | Hoje está desatualizado e impede qualquer PR coeso. Sem isto, qualquer mudança vira "re-abortada por doc". | S/M |
| A2 | **Tabela `contacts` + 1 decisor por lead via CNPJ (Receita)** | Sem decisor, "Enviar mensagem" é "Olá, eu vi seu site". Resposta ~1%. Apollo.io tem dispara por nomes/emails corporations. | M |
| A3 | **Serviço de outreach com Llama 3.3 70B** (Geraército: Subject + Body HTML + Follow-up 1/2/3) | Hoje: botão "Gerar Pitch" inerte. Com cadências, funil Stoppard. | M |
| A4 | **Endpoint `POST /api/leads/{id}/messages` + Estado de cadência (`lead_sequence_state`)** | Sustenta o follow-up automático (sequência dia 0/3/7/14). | M |
| A5 | **Job scheduler (cron) para disparar follow-ups** | Sem disto, o outreach não funciona. Implementar via APScheduler ou RQ + Redis. | M |
| A6 | **Envio via Resend** (kept para inual, use quem pode opt-out) | LGPD: dimea opt-outauto-apaga. | M |
| A7 | **Briefing de 5 minutos (1-pager IA) na aba Dossiê** | Mesmo sem-everything-no investment A2, POEMOS ser topoZ "Briefing". Influados no phaseA,B até to ant ideal stronger. | M |
| A8 | **`lead_events` table para timeline real** | "diasparado" hoje usa `created_at`. Sem isso, não há alerta de lead esquecido nem seguimento sequencial. | S |
| A9 | **Alerta de lead esquecido no kanban** (badge vermelho com dias desde `last_event_at`) | Visível para o vendedor — feedback instant "voce abandonarosta lead". | S |
| A10 | **Tabela `lead_dossiers` + aba "Dossiê Comercial"** (subset enrichment) | Substitui a página atual por briefing. Visual linear customer-reading. | L |

### Fase B — Melhorias importantes (consolidação do que existe)

| # | Item | Razão | Esforço |
|---|--|--|--|
| B1 | **Playbook evolution: adicionar `dimensions`, `expected_pains`, `objections_playbook`, `first_message_angle`, `providers` ao template** | Sem isto, a evolução 2D/3D do scoring não roda. | M |
| B2 | **Registry de providers de enriquecimento + refator do orchestrator para providers[]** | Remove `requires_technical_report` booleans ad hoc. Adiciona CNPJ/Hunter/Socials sem if. | M |
| B3 | **Iluminação das colunas `responsive_design`, `lighthouse_score`, `seo_errors`** (ou marshaller Playwright para preencher, ou deprecar marker deprecated) | Hoje colunas existentes não usadas — confuso no schema. | S |
| B4 | **Plugin de coleta multi-source (CNPJ + Google Dorks + IG)** | Hoje places é único. Para "Engenharia Mecânica" e segmentos não-varejo, Google Places é inútil. | L |
| B5 | **Audience builder**: listas inteligentes ("HOT + score>80 em SP", "sem contato há 10d") | Permite campaigns para sequências sem precisar de novos campaign_id rows. | M |
| B6 | **Dashboard "O que fazer agora" por action** (em vez de 3 contadores) | "Lead AX está atuamente req uma ação — startA aqui". Boost conversão. | S |
| B7 | **Página de configurações funcional** (trocar senha, editar perfil real, notificações) | Atualmente placeholder. A termo TB de LGPD opt-out-sale. | S |

### Fase C — Diferenciais competitivos

| # | Item | Razão | Esforço |
|---|--|--|--|
| C1 | **Aprendizado por conversões (Fase 5)** — endpoint `POST /api/leads/{id}/convert`; job recalibra pesos do template a cada 10 conversões | Difícil de copiar: exige base instalada. | L |
| C2 | **Heatmap de oportunidade por CNAE × região** com base em receptive_Receita + Google Places | Diferencial PMEs brasileiras, ninguém faz. | L |
| C3 | **Integração WhatsApp Business para envio de prospecção** (LGPD opt-in manual primeiro) | Brazilian moat; Apollo EUA não tem WhatsApp. | L |
| C4 | **Notas manuais no brief → loop de aprendizado por usuário** | "Eu notei este cliente disse X. IA usa no próximo scoring next". | M |
| C5 | **Aplicativo de WhatsApp + botão de notas rápidas para o comercial** | "todos os roteadores de followup -> no celular. Acesso sóhore para a dia." | L (?) |
| C6 | **Tailored follow-up por resposta** (IA gera nova mensagem baseada no que o lead respondeu) | Apollo.c -- cadência estática; para nós decisiva o que respondido. | M |
| C7 | **Cal.com via self-hosted integration** | Facilita "Reunião-alvo" do funil sem trocar plataforma. | M |
| C8 | **Briefing de 5 minutos também como PDF exportável** | PMEs brasileiras agora yields para compartilhar com sócio proprietario. | S |

### Fase D — Funcionalidades futuras

| # | Item | Razão | Esforço |
|---|--|--|--|
| D1 | **Multi-tenant completo** (Alphamec exposta das fases) | Roadmap já. | L |
| D2 | **Marketplace de templates de playbooks** (especialistas vendem playbooks) | Monetiza curadoria. | L |
| D3 | **Templates auto-gerados por categorias do negócio input ("vendo app para o varejo de moveis")** — LLM sugere todos os campos do template + o usuário aprova | Tempo to-market para novo tipo de serviço → ~zero. | M |
| D4 | **Voice briefing** (TTS) — vendedor ouve briefing no trajeto à reunião | Diferencial dramatico mas caro. | M |
| D5 | **Bench marking anonimizado entre segmentos** sem expor dados | "Sua campanha de petshops em Araraquara está abaixo da média para  seus similares." | L |
| D6 | **Auto-loop de scorings quando novos facts chegam (e.g., CNPJ re-analisado)** | Hoje a reanálise é manual; aqui trigger automatico. | M |

---

## Visão PM Apollo.io-adaptada → Lacunas vs projeto atual

Se, como Product Manager, eu recebesse a missão de criar "Apollo.io para
PMEs brasileiras e prestação de serviços", desenharia estas **7
funcionalidades indispensáveis**:

1. **Criação de campanha por "intenção"**, não por query Google Places.
   "Quero prospectar PMEs em SP que precisam de site, em segmento varejo." O
   sistema propõe 3 segmentos, 5 geografias, 3 ângulos de pitch.

2. **Dossiê de 1 página por lead** — briefing de 5 minutos — já
   descrito.

3. **Decisor listado + email sugerido** (com confidence) — não só
   "contato@empresa.com.br".

4. **Cadência inteligente** (não fixa dia 3/7/14) — reage à resposta.
   Se lead respondeu "Quer mais infos" → próxima mensagem é case study,
   não reabertura.

5. **Briefing de pós-reunião** — vendedor marca "Demo sobre proposta
   5 mil" a platform recomenda tomar nota de objeções, post scorer.

6. **Library de playbooks por categoria** — não preciso saber nada de
   petshops. Plataforma já tem playbook "Marketing digital para
   petshops".

7. **Aprendizado por empresa** — depois de 20 contatos, plataforma
   recomenda "os petshops em Ribeirão respondem menos que as academias em
   Matão. Market A direcione 30% mais mensagens para academias."

### Lacunas contra o projeto atual

| Apoloio.io-PM-pensado | Estado atual |
|---|---|
| Criação por intenção | Wizard 4 etapas, com `target_service=NULL` no DB |
| Dossiê 1-pager | Card "Aptidão" + Card "Evidências" — textos curtos, não narrativos |
| Decisor listado + email sugerido | Tabela contacts não existe |
| Cadência inteligente | Não existe sequência dia 3/7/14 |
| Briefing pós-reunião | Não há trackable conversação |
| Library de playbooks | Templates em DB ✅ mas só 9; não há gestão-enabled |
| Aprendizado por empresa | Conversion tabelano usada |

**Conclusão**:
Hoje, ~17% da visão PM-Apollo.io-PMEs-BR existe, e foram felizes conquistas
acabadas recentemente (scoring contextual + explicabilidade + reanálise
e2e validada). Prioridade clara: destravar o **funil comercial** (contatos +
cadência + briefing narrativo) em Fase A. O resto do produto se desdobra após
o comercial começar a responder.
