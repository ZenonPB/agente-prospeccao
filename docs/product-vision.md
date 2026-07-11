# Visão do Produto — Assistente de Inteligência Comercial para PMEs Brasileiras

> Este documento descreve o produto de forma **estável e viva**: o que ele é hoje,
> o que almeja ser e por quê. É a referência de **"o que"** e **"por quê"** — o
> **"como"** está em `architecture.md` e o **"como evoluir"** em
> `evolution-analysis.md` + `roadmap.md`.
>
> Leitura obrigatória antes de qualquer tarefa que envolva novas funcionalidades.
>
> Atualizado em 2026-07-09 — reposicionalização de "ferramenta de prospecção
> para dev houses" para "assistente de inteligência comercial para PMEs
> brasileiras que prestam serviços".

---

## 1. Reposicionamento

A plataforma deixou de ser "coletor de empresas com score". É um
**assistente de inteligência comercial** para pequenas e médias empresas
brasileiras que vendem **serviços** — tecnologia, engenharia, marketing,
consultoria, automação.

O foco deixa de ser "como um desenvolvedor prospecta clientes de software"
e passa a ser **como qualquer prestador de serviço PME brasileiro prospecta,
qualifica e conduz vendas B2B**, sem precisar montar um time comercial.

### Por que reposicionar

- O produto já suporta múltiplas categorias de serviço via
  `campaign_scoring_templates` (web, marketing, engenharia, automação,
  consultoria, genérico). A descrição "dev houses" ficou menor que o código.
- O mercado de "ferramenta de prospecção para dev houses" é minúsculo. O
  mercado de "ferramenta de inteligência comercial para PMEs de serviço" é
  grande, fragmentado e mal servido por ferramentas americanas (Apollo.io,
  Outreach, Lemlist) que não entendem realidade brasileira (WhatsApp,
  Receita/CNPJ, LGPD, sem stack de CRM).
- A IA contextual + explicável já implementada permite o salto: o sistema
  não precisa apenas pontuar, precisa **aconselhar** o comercial.

### Não é

- Não é um clone de Apollo.io. Conceitualmente inspirado, funcionalmente
  brasileiro e voltado a serviço (não a SaaS de ticket médio alto para
  enterprise).
- Não é ferramenta de spam. Outreach é sempre B2B, dados públicos, opt-out
  obrigatório, respeito à LGPD.
- Não é substituto do vendedor. Automatiza pesquisa e qualificação; a reunião
  permanece humana.

---

## 2. O Problema que Resolvemos

PMEs brasileiras que prestam serviços (agências de marketing, engenharias,
consultorias, desenvolvedores, integradores de automação) prospectam
manualmente:

- Horas/dia pesquisando empresas no Google, no Google Meu Negócio, no Maps,
  no Instagram.
- Análise ad-hoc, gonzo-a-gonzo: "este site é ruim? este petshop cresceu?
  esta metalúrgica tem expansão?" — sem critérios consistentes entre vendedores.
- Mensagens genéricas, baixíssima resposta (~2%).
- Sem rastreamento de quem respondeu, qual sequência funcionou, qual perfil
  converte.
- Sem saber **quem é o decisor** — "Olá, contato@" não responde.

Ferramentas americanas ignoram a realidade brasileira: não falam com Receita,
não mandam WhatsApp, não entendem CNAE, não respeitam LGPD de forma nativa.

---

## 3. O que Estamos Construindo

Uma plataforma que age como um **consultor comercial júnior aspiracional**:
encontra oportunidades, monta tese comercial por lead, sugere argumentário,
prevê objeções, sustenta cadência, e prepara o vendedor para a reunião.

O vendedor fica responsável apenas pela etapa de maior valor — **a conversa
humana**. Tudo o que é pesquisa, leitura, raciocínio e escrita comercial
repetitiva é automatizado.

### Princípios de produto

1. **Cada lead chega "pronto para conversar"** — não apenas pontuado. Tese
   comercial, dores prováveis, argumentário, objeções esperadas, cadência
   sugerida.
2. **Contexto é por campanha, não global.** Vender SEO para academia é
   diferente de vender aquecimento industrial para metalúrgica. A奥林匹ada
   de critérios mora em `campaign_scoring_templates`, editável sem código.
3. **Tudo passivo.** A IA observa o que é publicamente acessível. Nada de
   probing, scanning de vulnerabilidades, testes de autenticação (Lei
   12.737/2012).
4. **Brasileiro nativo.** CNPJ/Receita, LGPD, WhatsApp, CNAE — não
   adaptações de ferramentas americanas.
5. **Aprende com o uso.** Conversões registradas voltam como
   ajustes de playbook. Sem installs-base não há moat; com installs-base o
   sistema fica mais esperto por cliente.

---

## 4. Para Quem é

### Usuário direto (operador da plataforma)

- Pequenas e médias empresas brasileiras **prestadoras de serviço**:
  - Agências de marketing digital.
  - Software houses / dev shops.
  - Engenharias (mecânica, civil, elétrica, automação).
  - Consultorias (gestão, financeira, RH, processos).
  - Integradores de automação industrial.
  - Estúdios de design/branding/content.
- Vendedor solitary, fundador-comercial, ou 1-2 vendedores.
- Não tem CRM sofisticado, não tem SDR dedicado, não tem stack de outreach
  como Lemlist/Apollo configurado.

### Cliente-alvo da prospecção (quem a plataforma encontra para o usuário)

- PMEs brasileiras, qualquer segmento.
- Sinais de oportunidade dependem da campanha:
  - Para "Marketing Digital para Academias": IG ativo mas site sem CTA;
    sem área de membros; vitrine de planos fraca.
  - Para "Engenharia Mecânica": porte/fábrica/CNAE industrial; expansão
    recente (filiais); site é secundário.
  - Para "Desenvolvimento de Sites": SSL/SEO/performance/CMS desatualizado.
- A definição de "sinais relevantes" é declarada no template da campanha,
  não hardcoded.

### Não é para

- Enterprise com ciclo de venda 6-12 meses e múltiplos decisores.
- E-commerce B2C high-volume.
- Prospecção internacional (sinão pode ser estendido, mas não é o foco).
- Substituir SDRs de um time comercial grande.

---

## 5. Arquitetura Conceitual do Produto (5 etapas)

### Etapa 1 — Coleta (automático)

Fonte atual: Google Places API (New) — nome, endereço, telefone, site,
categoria.

Futuro próximo:
- **CNPJ / Receita Federal** — razão social, CNAE principal/secundário,
  porte, situação cadastral, sócios, filiais, idade do negócio.
- **WHOIS / DNS** — idade do domínio, provedor.
- **Google Search dorks** — menções, notícias, "contratou", "expansão",
  "nova filial".
- **Instagram / Facebook** — presença, atividade, frequência de post.

Princípio: a coleta respeita o template da campanha. Se o template declara
que alvos são "indústria por CNAE", a coleta faz pós-filtro por CNAE — não
inventa a segmentação no `searchText`.

**Nunca automatizar:** envio de mensagens no LinkedIn (risco de ban) e
qualquer ação não-passiva.

---

### Etapa 2 — Enriquecimento (multi-provider)

Hoje: enriquecimento **técnico passivo de sites** — SSL, headers, CMS,
load time, SEO, LGPD, paths expostos. Tudo o que qualquer pessoa veria
abrindo o site.

Evolução para **sistema de providers**, registrado e declarado por template:

| Provider | Quando relevante | Origem |
|---|---|---|
| `technical` (sites) | Marketing digital, dev web | httpx passivo |
| `cnpj` (Receita) | Engenharia, consultoria, automação — tese baseada em porte/CNAE | API CNPJ |
| `hunter` (decisores) | Qualquer B2B | Hunter.io |
| `socials` (IG/FB) | Marketing, branding | Scrape público |
| `domain_age` | Expansão / antiguidade | WHOIS |

O template da campanha declara `providers: ["cnpj", "hunter", "technical"]`
e o orquestrador chama exatamente esses — sem `if/else` no código. Adicionar
categoria de serviço = novo row de template. Adicionar provider = registro
no registry. **Zero alteração de código.**

**Limite legal absoluto:** análise 100% passiva. Lei 12.737/2012.

---

### Etapa 3 — Inteligência Comercial (IA, multi-dimensional)

Cada lead recebe não apenas um score, mas um **raciocínio comercial
multi-dimensional**:

| Dimensão | O que avalia |
|---|---|
| Fito comercial | Este lead precisa do serviço que vendemos? |
| Maturidade digital | Está pronto para aceitar a proposta? |
| Potencial de compra | Ticket médio provável |
| Urgência | Há sinais de momento (expansão, regulatório)? |
| Acessibilidade | Quão fácil contatar um decisor? |

Cada dimensão tem nota + evidências. O score global é **média ponderada**
dos pesos definidos no template.

Além das dimensões, a IA produz:

- **Hipóteses de dores prováveis** — nunca "confirmadas" (ético), sempre
  `pain_hypothesis` + `confidence` + `evidence`.
- **Argumentário priorizado** — 3-5 argumentos de venda, cada um com
  `angle`, `evidence_ref`, `objection_risk`.
- **Objeções prováveis** — top-3 + respostas sugeridas.
- **Previsão de interesse** — chance de marcar reunião na 1ª mensagem
  (inicialmente heurística, depois baseada em conversões reais do usuário).
- **Briefing de 5 minutos** — 1-pager narrativo no estilo McKinsey:
  Resumo do Negócio, Tese Comercial, Decisor, Pontos de Entrada, Cadência
  Já Feita, Roteiro de Perguntas, Objeções, Próxima Ação.

**Modelo de IA:** scoring na Geração Atual usa Groq Llama 3.1 8B (rápido,
preso a schema JSON, free tier). Geração de mensagens e briefings narrativos
usará Llama 3.3 70B (qualidade superior de texto).

**Aprendizado contínuo:** a cada conversão registrada, o sistema ajusta
pesos das dimensões do template. Após 10+ conversões por categoria, a IA
inclui no prompt um resumo de "perfis que convertem mais para este usuário".

---

### Etapa 4 — Outreach e Cadência (semi-automático)

Gera **sequência completa** de mensagens personalizadas — não apenas "1ª
mensagem". Cada referência a dados reais do lead (CMS detectado, CNAE, porte,
dores prováveis).

**Cadência de follow-up** (já definida em `business-rules.md`):

| Mensagem | Quando | Objetivo |
|---|---|---|
| 1ª | Dia 0 | Apresentação + problema + CTA reunião |
| Follow-up 1 | Dia 3 sem resposta | Reforço leve, novo ângulo |
| Follow-up 2 | Dia 7 sem resposta | Caso similar + valor direto |
| Encerramento | Dia 14 sem resposta | Ciclo encerrado, lead volta em 90 dias |

Evolução futura: **cadência adaptativa** — se lead respondeu "quer mais
informações", próxima mensagem é case study, não reabertura.

**Canais:**
- **E-mail** via Resend (com LGPD opt-out, throttle, warm-up).
- **WhatsApp Business** via API oficial Meta (futuro, moat brasileiro).
- **LinkedIn** — envio sempre manual (risco de ban).

**Agendamento de reuniões:** Cal.com self-hosted, link na mensagem.

---

### Etapa 5 — Reunião e Pós-reunião (humana, sempre)

O vendedor conduz. Antes da reunião, lê o **Briefing de 5 Minutos** da
plateforma — tudo o que precisa para entrar confiante.

Após a reunião, registra:
- Objeções reais ouvidas (alimenta aprendizado).
- Status do lead (avança no funil ou PERDIDO com motivo).
- Próxima ação.

A plataforma usa isto para refinar scores seguintes.

---

## 6. Funil de Status dos Leads

```
NOVO
 → ANALISADO        após enriquecimento
 → QUALIFICADO      score >= 60
 → DESQUALIFICADO   score < 60 ou sem fito
 → CONTATADO        1ª mensagem enviada
 → RESPONDIDO       lead respondeu
 → REUNIAO_MARCADA
 → REUNIAO_FEITA
 → PROPOSTA_ENVIADA
 → (ganho/perdido)
 → PERDIDO          volta à fila em 90 dias
```

`PERDIDO` reentra na fila após 90 dias para nova análise — pode ter mudado
-contexto (novo sócio, expansão,	stack renovado).

---

## 7. Dossiê Comercial por Lead

Cada lead recebe um **dossiê** além do score. Estrutura:

1. **Identidade** — razão social, nome fantasia, CNAE, porte, idade,
   situação cadastral.
2. **Localização & operação** — endereço, filiais, pólos regionais.
3. **Decisor** — nome, cargo, email, confidence, perfil em redes.
4. **Maturidade digital** — site, stack, responsive, SEO, LGPD, redes
   sociais, atividade recente.
5. **Sinais de negócio** — categoria, tipo (indústria/varejo/serviço),
   porte, expansão recente.
6. **Hipóteses de dor** — baseadas no template + facts do lead.
7. **Oportunidade contextual** — fito, primary_need, argumentário
   priorizado para esta campanha.
8. **Riscos & objeções** — top-3 + respostas sugeridas.
9. **Histórico** — coleta, contatos, follow-ups, reuniões, conversões.

Apresentado na UI como **briefing narrativo** (estilo McKinsey 1-pager),
não ficha técnica. Substitui a atual tela detalhe do lead.

---

## 8. Diferenciais Defensáveis (moat)

O que torna a plataforma difícil de copiar:

1. **Dossiê comercial narrativo LLM-contextualizado** — não é "50 campos
   como Apollo", é 1-pager que depende de curadoria humana de playbooks por
   categoria.
2. **Playbooks editáveis por categoria de serviço** — quanto mais o
   usuário usa, mais calibrado o template fica. Difícil de copiar sem
   curadoria inicial.
3. **Aprendizado por conversões do próprio usuário** — insights não
   exportáveis: cada instalação fica esperta sozinha.
4. **Brasileiro nativo** — CNPJ, CNAE, LGPD, WhatsApp, Google Meu
   Negócio. Apollo.io não constrói isto.
5. **Heatmap de oportunidade CNAE × região** — combinando Receita + Places
   num BI embutido. Ninguém no Brasil faz.
6. **Fluxo do vendedor brasileiro** — WhatsApp + agenda + cadência. Apollo
   é americano, ；e-mail-centric.

---

## 9. Estado Atual

### ✅ Pronto

- Coleta via Google Places (async, httpx).
- Enriquecimento técnico passivo (SSL, CMS, SEO, LGPD, perf, paths).
- Scoring contextual via Groq Llama 3.1 8B — template editável, prompt
  dinâmico, fallback "Genérico".
- Explicabilidade: `score_factors[]`, `evidence[]`, `priority` (LLM-decidida),
  `priority_reasoning`, `executive_summary`.
- API REST + WebSocket com auth JWT (FastAPI).
- Frontend Next.js 16 + React 19 + shadcn/ui (base-nova): login, dashboard,
  campanhas com wizard + pipeline inline, oportunidades, vendas (kanban).
- Reanálise end-to-end com template contextual validada (academias, petshop,
  farmácias).
- 9 templates seedados (web genérico, marketing para academias/petshop/
  farmácias, dev de sites, SEO, engenharia, automação, consultoria).

### 🟡 Em andamento

- Funcionalidades pendentes da Fase 2 (esqueci-minha-senha, configurações
  funcionais, CSP produção).
- Testar fluxo completo end-to-end.

### 🔲 Não existe ainda

- Tabela `contacts` com decisores ( maior gap isolado).
- `outreach_service.py` — geração de corpo de e-mail + follow-up.
- Scheduler de cadência (APScheduler/RQ+Redis).
- Envio via Resend.
- `lead_events` para timeline real (kanban hoje usa `created_at` — está errado).
- `lead_dossiers` — UI narrativa de briefing.
- Scoring multi-dimensional (fit/maturidade/potencial/urgência/acessibilidade).
- Registry de providers de enriquecimento (CNPJ, Hunter, socials).
- Aprendizado por conversões (`Conversion` model existe, endpoint não).
- Coleta multi-source (hoje só Places).
- WhatsApp Business.
- Heatmap CNAE × região.

---

## 10. Não-funcionais

- **Limites legais (Lei 12.737/2012):** nada de probing, scanning,
  injeção, teste de autenticação. Apenas passivo.
- **LGPD:** dados públicos B2B, opt-out em toda comunicação, retenção
  documentada.
- **Limites de API:** Google Search 100/dia, Hunter.io 1k/mês, WHOIS 50/mês,
  CNPJ 20/mês por chave. Fallback e cache quando estoura.
- **Custo por lead:** Groq free tier;elmanha de scoring ~ $0.0001/lead,
  mensagem Llama 3.3 70B ~ $0.001/lead.
- **Multi-tenant:** planejado para fase futura; hoje single-tenant.

---

## 11. Metas de Sucesso

| Métrica | Hoje / atual | Meta Fase A | Meta Fase C |
|---|---|---|---|
| Leads processados por campanha | 5-20 | 50+ | 200+ |
| Decisor identificado (% dos leads) | 0% | 60%+ | 85%+ |
| Taxa de resposta (e-mail) | ~2% (manual) | 8%+ | 15%+ |
| Conversão para reunião | n/a | 15% das respostas | 25%+ |
| Tempo economizado/semana | 0 | 5h | >10h |
| Briefing de 5 min disponível | não | sim | sim + PDF |

---

## 12. Roadmap resumido

Detalhes completos em `roadmap.md` + `evolution-analysis.md` (Fases A/B/C/D).

- **Fase A — Destravar o funil comercial** (essencial): contacts + CNPJ,
  outreach_service, scheduler, lead_events + alerta, dossiê comercial inicial.
- **Fase B — Consolidar inteligência** (importante): expandir template
  (dimensions, pains, objections), registry de providers, audience builder,
  dashboard "o que fazer agora" inteligente.
- **Fase C — Defensibilidade competitiva** (diferencial): aprendizado por
  conversões, heatmap CNAE × região, WhatsApp, notas manuais no loop,
  briefing PDF.
- **Fase D — Futuro** (expansão): multi-tenant, marketplace de playbooks,
  templates auto-gerados por LLM, voice briefing, benchmarking anônimo.

---

## 13. O que Nunca Fazer

- Automatizar envio de mensagens no LinkedIn.
- Tentar explorar vulnerabilidades de qualquer tipo (Lei 12.737/2012).
- Coletar dados pessoais sensíveis fora do escopo B2B público.
- Enviar mensagens sem opt-out e sem contexto real do lead (zero spam
  genérico).
- Commitar chaves de API, `.env`, ou qualquer segredo.
- Tratar `score` como a única saída da IA — score é subproduto do
  raciocínio; o dossiê é o produto.
- Escrever playbooks hard-coded — sempre em `campaign_scoring_templates`,
  editáveis.
- Adaptar ferramentas americanas sem perguntar "faz sentido no Brasil?".
