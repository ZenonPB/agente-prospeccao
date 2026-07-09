# Visão do Produto — Plataforma de Inteligência Comercial

> Este documento descreve o produto completo que estamos construindo.
> É a referência de "o que" e "por quê" — não de "como" (isso está em architecture.md).
> Leitura obrigatória antes de qualquer tarefa que envolva novas funcionalidades.

---

## O Problema que Resolvemos

Dois desenvolvedores full stack que vendem serviços de software (sites, landing pages,
ERPs, apps) precisam prospectar clientes manualmente. Isso significa:

- Horas por dia pesquisando empresas no Google Maps
- Analisando site por site para ver se tem oportunidade
- Escrevendo mensagens na mão, uma por uma
- Sem rastreamento de quem respondeu, quem virou cliente, o que funcionou
- O processo não escala — é limitado pelo tempo disponível

O resultado: 30+ mensagens enviadas para pouquíssimas respostas, porque são
genéricas e sem contexto real sobre o cliente.

---

## O que Estamos Construindo

Uma plataforma que faz tudo isso automaticamente, deixando para o desenvolvedor
apenas a etapa de maior valor: **a reunião com o cliente**.

Não é um bot de spam. É um pipeline de inteligência que:
1. Encontra empresas com sinais reais de oportunidade
2. Analisa tecnicamente a presença digital de cada uma
3. Pontua e qualifica com IA
4. Gera mensagens personalizadas citando problemas reais encontrados
5. Aprende quais perfis convertem mais ao longo do tempo

---

## Para Quem é

### Usuários da plataforma
- **Desenvolvedor A** (usuário principal) — full stack, co-fundador, usa para prospecção própria
- **Desenvolvedor B** — co-fundador, usa a mesma ferramenta
- **Empresa Júnior** (fase futura) — expansão para outros nichos, possível investidor

### Cliente-alvo da prospecção (quem o sistema vai encontrar)
- Pequenas e médias empresas brasileiras, qualquer segmento
- Prioritários: clínicas, salões, academias, restaurantes, lojas, escritórios,
  pequenas indústrias, transportadoras, imobiliárias
- Sinal de oportunidade: sem site, site ruim/inseguro, dependência de WhatsApp/Excel,
  sem sistema de gestão
- Abrangência: nacional, começando pela cidade dos usuários

---

## As 5 Etapas do Pipeline

### Etapa 1 — Coleta (automático)
Busca empresas em fontes de dados abertas.

**Hoje:** Google Places API (New)
- Nome, endereço, telefone, site, categoria

**Futuro:**
- CNPJ / Receita Federal — dados cadastrais, CNAE, porte, situação da empresa
- WHOIS / DNS — idade do domínio, provedor, dados técnicos
- Google Search — menções, notícias, perfis sociais
- Instagram / Facebook — presença e atividade nas redes (parcial)

**Nunca automatizar:** LinkedIn para envio de mensagens — risco de ban inaceitável.
A IA qualifica e gera a mensagem, mas o envio no LinkedIn é sempre manual.

---

### Etapa 2 — Enriquecimento Técnico (automático)
Analisa a presença digital de cada lead de forma **totalmente passiva**.
Nenhuma exploração ativa. Apenas o que qualquer pessoa veria abrindo o site.

**Sinais que coletamos e o argumento comercial de cada um:**

| Sinal | Como detectar | O que dizemos ao cliente |
|---|---|---|
| SSL ausente ou expirado | Requisição HTTPS + certificado | "Seu site não tem cadeado — visitantes recebem alerta de risco" |
| Sem redirecionamento HTTPS | Verificar resposta HTTP 301/302 | "Dados dos seus clientes podem ser interceptados" |
| CMS desatualizado (ex: WP 4.x) | Headers HTTP + meta tags | "Versões antigas têm falhas conhecidas publicamente" |
| Site não responsivo | Playwright em viewport mobile | "60%+ dos acessos são mobile — seu site afasta clientes" |
| Site lento (LCP > 4s) | Lighthouse via Playwright | "Site lento perde posição no Google" |
| Erros de SEO graves | Meta tags, sitemap, robots.txt | "Sua empresa não aparece nas buscas" |
| Sem política de privacidade | Varredura de links e rodapé | "Pode estar em desacordo com a LGPD — multas de até R$50mi" |
| Formulários quebrados | Playwright preenchendo e verificando submit | "Clientes tentam entrar em contato e o formulário não funciona" |
| Arquivos sensíveis expostos | HEAD em /.env, /.git/config, /wp-config.php | "Informações internas estão publicamente acessíveis" |
| Headers de segurança ausentes | Análise dos headers HTTP | Argumento técnico de vulnerabilidade |

**Limite legal absoluto:** A plataforma jamais tenta explorar vulnerabilidades,
executar injeções, testar autenticação ou qualquer ação não-passiva.
Isso configuraria crime pela Lei 12.737/2012 (Lei Carolina Dieckmann).

**Futuro do enriquecimento:**
- Enriquecimento de contatos: Hunter.io + CNPJ para encontrar o decisor (CEO, sócio)
- `contact_confidence` para saber o quão confiável é aquele contato (0-100)
- Tabela `contacts` separada de `leads` — um lead pode ter múltiplos decisores

---

### Etapa 3 — Scoring com IA (automático)
Cada lead recebe uma pontuação de 0 a 100 com justificativa e sugestão de serviço.

**Score e significado:**
- 80-100 → Crítico: .env exposto, sem HTTPS, .git acessível
- 60-79 → Grave: múltiplos problemas de segurança ou performance
- 40-59 → Moderado: headers ausentes, WordPress detectado
- 20-39 → Leve: site funcional mas com melhorias
- 0-19 → Bem configurado, baixa oportunidade

**Score >= 60 → QUALIFICADO → entra na fila de outreach**
**Score < 60 → ANALISADO → não entra no outreach automático**

**Campos gerados pelo scoring:**
- `qualification_score` — número de 0 a 100
- `qualification_reason` — texto em português para o dono da empresa, sem jargão técnico
- `primary_need` — SECURITY_FIX | PERFORMANCE | MODERN_WEBSITE | SEO | NONE
- `issues_found` — lista de problemas com severidade, descrição e recomendação

**Modelo:** Llama 3.1 8B via Groq (tarefa simples de classificação, free tier)

**Configuração por campanha:**
O usuário define no dashboard qual serviço quer prospectar naquela campanha
(ex: "landing pages para restaurantes", "ERP para clínicas", "app para academias").
O prompt enviado à IA é gerado dinamicamente com base nisso — tornando o scoring
específico para o objetivo de cada campanha, sem precisar de código novo.

**Futuro — Aprendizado Contínuo:**
Após 10+ conversões registradas, o sistema inclui no prompt de scoring um resumo
dos perfis históricos de sucesso:
> "Clínicas odontológicas com site desatualizado em cidades do interior de SP
> converteram 3.8x mais. Vestuário tem respondido pouco nos últimos 90 dias."

---

### Etapa 4 — Outreach (automático)
Gera e envia mensagens personalizadas. Nunca genéricas — sempre referenciam
dados reais encontrados na análise.

**Exemplo de mensagem gerada:**
> "Olá! Encontrei a [Empresa] no Google e fiquei curioso — vocês têm um público
> bem ativo (mais de 80 avaliações!), mas percebi que o site está sem certificado
> de segurança e não abre bem no celular. Sabendo que 60%+ das buscas são feitas
> no celular, isso pode estar afastando clientes sem que vocês percebam. Somos
> especialistas em sites rápidos e seguros para [segmento] e gostaríamos de mostrar
> o que conseguimos fazer em uma conversa de 20 minutos. Topam?"

**Sequência de follow-up automática (e-mail):**

| Mensagem | Quando | Objetivo |
|---|---|---|
| 1ª mensagem | Dia 0 | Apresentação + problema identificado + CTA reunião |
| Follow-up 1 | Dia 3 sem resposta | Reforço leve + nova perspectiva |
| Follow-up 2 | Dia 7 sem resposta | Última tentativa + proposta de valor direto |
| Encerramento | Dia 14 sem resposta | Ciclo encerrado — lead volta à fila em 90 dias |

**Modelo:** Llama 3.3 70B via Groq (geração de texto de qualidade)
**Envio:** Resend (API de e-mail com bom deliverability, plano gratuito)
**Agendamento:** Cal.com self-hosted (link enviado no e-mail de outreach)

**Riscos do outreach:**
- E-mails caindo em spam → throttle de envio, domínio dedicado, warm-up gradual, opt-out obrigatório
- Violação da LGPD → apenas dados públicos B2B, opt-out em toda comunicação

---

### Etapa 5 — Reunião (manual, sempre)
O desenvolvedor conduz a reunião. Todo o pipeline anterior existe para garantir
que quando ele sentar com o cliente, a reunião já tenha alta probabilidade de conversão.

Esta etapa é **deliberadamente humana** e nunca será automatizada.

---

## Funil de Status dos Leads
NOVO
→ ANALISADO        após enriquecimento técnico
→ QUALIFICADO      score >= 60
→ DESQUALIFICADO   score < 60 ou sem oportunidade
→ CONTATADO        1ª mensagem enviada
→ RESPONDIDO       lead respondeu (positivo ou negativo)
→ REUNIAO_MARCADA  reunião agendada no Cal.com
→ PERDIDO          desistiu ou não é fit → volta à fila em 90 dias

---

## MVP — Coleta e Scoring (Fase 1)

O que está sendo implementado agora:
- Coleta via Google Places API (New) — nome, telefone, site, categoria, endereço
- Enriquecimento técnico passivo via httpx — SSL, headers, CMS, arquivos expostos
- Scoring com IA via Groq (Llama 3.1 8B) — score 0-100, justificativa, primary_need
- Persistência no PostgreSQL via SQLAlchemy
- Pipeline executado via terminal (main.py)
- Mensagem de outreach gerada manualmente com base no qualification_reason

O MVP está pronto quando o desenvolvedor consegue rodar o pipeline completo
pelo terminal e ter leads qualificados com score e justificativa no banco.

---

## Interface Web (Fase 2)

O que o usuário verá no dashboard:

- **Funil visual** — quantos leads em cada status
- **Lista de leads** com score, necessidade primária, site, telefone
- **Detalhe do lead** — relatório técnico completo, mensagem gerada, histórico
- **Campanhas** — criar/pausar/arquivar campanhas por nicho e cidade
- **Métricas** — taxa de resposta, conversão, custo por lead, tempo economizado
- **Configuração de campanha** — definir serviço-alvo, segmento, região

**Stack:** Next.js + NextAuth.js (Google OAuth + GitHub)
**Autenticação:** multi-usuário desde o início — preparado para empresa júnior

---

## Outreach Automatizado (Fase 3)

O que será implementado:
- Envio de e-mail via Resend
- Sequência de follow-up automática (dia 0, 3, 7, 14)
- Link de agendamento do Cal.com self-hosted no e-mail
- Throttle de envio para evitar blacklist
- Opt-out obrigatório em toda comunicação

---

## Enriquecimento Avançado (Fase 4)

O que será implementado:
- Responsividade mobile via Playwright em viewport mobile
- Lighthouse score via Playwright
- Análise de SEO: meta tags, sitemap, robots.txt
- Verificação de formulários: Playwright preenchendo e verificando submit
- Enriquecimento de contatos via Hunter.io + CNPJ
- Tabela `contacts` com decisores (CEO, sócio) e `contact_confidence`

---

## Aprendizado Contínuo (Fase 5)

Cada contrato fechado registra na tabela `conversions`:
- Segmento da empresa
- Cidade e região
- Porte estimado
- Tecnologias e sinais identificados
- Canal do primeiro contato
- Mensagem que gerou resposta
- Serviço vendido e valor
- Tempo entre primeiro contato e fechamento

Com 10+ conversões, o sistema recalibra o scoring automaticamente com dados reais.

---

## Metas de Sucesso

| Métrica | Meta |
|---|---|
| Leads processados por dia | >= 30 |
| Taxa de resposta | > 5% (vs ~2% manual hoje) |
| Conversão para reunião | > 15% das respostas |
| Custo por lead qualificado | < R$ 1,00 |
| Tempo economizado por semana | > 5h por usuário |

---

## Roadmap

| Fase | Status | O que entrega |
|---|---|---|---|
| 1 — MVP coleta + scoring | ✅ Concluído | Places API, enriquecimento, scoring, mensagem manual |
| 2 — Interface web | 🟡 Em andamento | Next.js, login (email/senha), dashboard, campanhas, pipeline |
| 3 — Outreach automatizado | 🔲 | E-mail via Resend, follow-up, Cal.com |
| 4 — Enriquecimento avançado | 🔲 | Mobile, Lighthouse, SEO, formulários, Hunter.io |
| 5 — Aprendizado contínuo | 🔲 | Conversions, recalibração do scoring |
| 6 — Expansão | 🔲 | Multi-tenant, empresa júnior, outros nichos |

---

## O que Nunca Fazer

- Automatizar envio de mensagens no LinkedIn
- Tentar explorar vulnerabilidades de qualquer tipo
- Coletar dados pessoais sensíveis
- Enviar e-mails sem opt-out
- Commitar chaves de API ou o arquivo .env