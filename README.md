<div align="center">

# 🎯 Agente Prospecção

**Plataforma de prospecção B2B com IA para PMEs brasileiras que vendem serviços**

Coleta multi-fonte · Enriquecimento automático · Qualificação com IA explicável · Outreach com cadência · BI comercial

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?style=flat&logo=next.js&logoColor=white)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat)](LICENSE)

</div>

---

## 📌 Sobre o projeto

O **Agente Prospecção** é uma plataforma de **prospecção B2B** pensada para pequenas e médias empresas brasileiras que vendem serviços. Ele automatiza o funil comercial de ponta a ponta:

- 🔎 **Coleta de leads multi-fonte** (Google Places, CSV, CNAE)
- 🧩 **Enriquecimento passivo e adaptativo** (site, CNPJ, contatos)
- 🤖 **Qualificação com IA explicável** — score de 0 a 100, com prioridade HOT / WARM / COLD
- ✉️ **Outreach com cadência automatizada** (dia 0 / 3 / 7 / 14), com **humano no loop por padrão**
- 📊 **Relatórios de inteligência comercial** e BI por analista, com exportação em PDF para a diretoria
- 🔁 **Loop de feedback** — os resultados reais (ganhou/perdeu) calibram o próximo ciclo de scoring

### Como funciona, em uma imagem

```
Usuário/Org descreve a oferta → campanha (Places / CSV / CNAE)
        ↓
Coleta → enriquecimento adaptativo (site? CNPJ? contatos?)
        ↓
Score contextual explicável (templates + LLM) → prioridade HOT / WARM / COLD
        ↓
Atribuição ao consultor → mensagens geradas por IA → cadência dia 0/3/7/14 (com opt-out)
        ↓
Resultado real (ganhou/perdeu) → BI por analista → PDF para a diretoria
        ↓
Feedback converte-se em calibração do próximo ciclo
```

---

## ✨ Principais funcionalidades

| Módulo | Descrição |
|---|---|
| **Campanhas** | Criação de campanhas de prospecção a partir de Google Places, upload de CSV ou filtro por CNAE |
| **Enriquecimento** | Descoberta automática de site, CNPJ e contatos das empresas coletadas |
| **Scoring com IA** | Pontuação explicável (0–100) combinando templates de regras + LLM (Groq), com justificativa legível |
| **Cadência de outreach** | Sequência de mensagens em dias 0, 3, 7 e 14, com opt-out e respeito a limites de envio |
| **Entregabilidade de e-mail** | Teto diário por organização, janela de envio configurável e verificação de contatos, para preservar a reputação do domínio |
| **BI e relatórios** | Painéis por analista/consultor e exportação de relatórios em PDF para a diretoria |
| **Multi-organização** | Suporte a múltiplos consultores por organização, com remetente de e-mail dedicado por pessoa |

---

## 🏗️ Stack tecnológica

| Camada | Tecnologias |
|---|---|
| **Backend** | Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic |
| **Workers / Integrações** | httpx (async) · Google Places API · Groq (LLM) · Receita Federal / CNPJ |
| **Banco de dados** | PostgreSQL |
| **Frontend** | Next.js 16 · React 19 · TypeScript · shadcn/ui (@base-ui/react) |
| **BI / Relatórios** | Analytics *org-scoped* · WeasyPrint (geração de PDF) |
| **Infra / DevOps** | Docker · Docker Compose · GitHub Actions |
| **Testes** | Pytest |

---

## 📂 Estrutura do repositório

```
agente-prospeccao/
├── .github/workflows/     # Pipelines de CI/CD (GitHub Actions)
├── apps/
│   └── web/                # Frontend — dashboard, campanhas, oportunidades, vendas, relatórios
├── docs/                   # Documentação completa em português
├── scripts/                # Scripts utilitários
│   ├── setup.ps1 / setup.cmd   # Setup Windows sem Docker (PostgreSQL embarcado, venvs, .env, migrations, seed)
│   └── dev.ps1 / dev.cmd        # Sobe/derruba API + Web (Windows)
├── services/
│   ├── api/                 # API REST + WebSocket, scheduler de cadência, BI, geração de PDF
│   └── workers/             # Modelos (fonte única), migrations, coleta/enriquecimento/scoring
├── static/imgs/alphamec/   # Assets estáticos
├── tests/                   # Suíte de testes automatizados
├── .env.example             # Modelo de variáveis de ambiente
├── docker-compose.yml        # Orquestração dos serviços (API, Web, Postgres)
├── pytest.ini
├── requirements-dev.txt
├── AGENTS.md                 # Convenções para agentes/automação de código
└── QUICKSTART.md              # Guia rápido de inicialização (Windows)
```

---

## 🚀 Como usar

Existem duas formas principais de rodar o projeto: **ambiente de desenvolvimento** (Windows ou Linux/macOS) ou **produção via Docker**.

### ✅ Pré-requisitos

- [Python 3.12+](https://www.python.org/downloads/)
- [Node.js](https://nodejs.org/) (compatível com Next.js 16)
- [Docker](https://www.docker.com/) e Docker Compose
- Chaves de API: `GROQ_API_KEY`, `GOOGLE_API_KEY` (Places) e, opcionalmente, `HUNTER_API_KEY`

---

### 🪟 Opção A — Windows (sem Docker, recomendado)

A forma mais simples de rodar o projeto no Windows **não precisa de Docker**: um script de setup baixa um **PostgreSQL embarcado**, cria os ambientes virtuais Python, gera os arquivos `.env` com segredos automáticos, roda as migrations e o seed dos templates de scoring — tudo em um único comando idempotente (pode rodar quantas vezes quiser).

**🖱️ Sem terminal (duplo clique):**

1. Dê duplo clique em `scripts\setup.cmd` — setup completo, uma única vez
2. Dê duplo clique em `scripts\dev.cmd` — sobe API e Web

**⌨️ Via PowerShell:**

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
.\scripts\dev.ps1 start    # sobe PostgreSQL, API (:8000) e Web (:3001)
.\scripts\dev.ps1 status   # verifica o que está rodando
.\scripts\dev.ps1 stop     # para tudo
```

> ✅ Única pendência manual: preencher `GROQ_API_KEY` e `GOOGLE_API_KEY` no `.env` (raiz) para coletar e qualificar leads. `HUNTER_API_KEY` é opcional.

Para o passo a passo detalhado (incluindo a alternativa com Docker Desktop), veja o **[QUICKSTART.md](./QUICKSTART.md)**.

---

### 🐧 Opção B — Linux/macOS (manual)

**1. Configure o ambiente**

```bash
cp .env.example .env
# preencha DATABASE_URL, JWT_SECRET, GROQ_API_KEY, GOOGLE_API_KEY, ...
```

**2. Suba o banco de dados** (opcional, caso não tenha PostgreSQL local)

```bash
docker compose up -d db
```

**3. Rode as migrações**

```bash
cd services/workers
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

**4. Inicie a API**

```bash
cd services/api
source venv/bin/activate && pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# Documentação interativa em http://localhost:8000/docs
```

**5. Inicie o frontend**

```bash
cd apps/web
npm ci && npm run dev
# Acesse em http://localhost:3001
```

**6. Primeiro acesso**

1. Abra `http://localhost:3001`
2. Clique em **"Cadastre-se grátis"**
3. Crie sua conta (você será o *owner* da organização)
4. Comece a criar suas campanhas de prospecção 🎉

---

### 🐳 Rodando em produção com Docker

```bash
cp .env.example .env        # preencha TODAS as variáveis (JWT_SECRET é obrigatório)
docker compose up -d --build
# API disponível em :8000 · Web em :3000 (use WEB_PORT para alterar a porta)
```

> ⚠️ Em produção (`ENVIRONMENT=production`), o SMTP é **obrigatório** — o envio de e-mail falha explicitamente em vez de simular sucesso. Configure também `EMAIL_WEBHOOK_SECRET` (inbound de respostas/STOP) e `SECRETS_ENCRYPTION_KEY` (chaves BYOK por organização).

---

## 📧 Entregabilidade e aquecimento de e-mail

O envio automático da cadência **respeita um teto diário por organização** e **uma janela de espalhamento** (ajustáveis em `/configuracoes` → *"Envio de follow-ups"*), evitando rajadas que prejudicam a reputação do remetente.

| Configuração | Descrição |
|---|---|
| `daily_email_limit` | Teto diário de envios automáticos (padrão: **40**) |
| `send_window_start` / `send_window_end` | Janela horária de envio (fuso do servidor) |
| `email_from` (por membro) | Remetente dedicado por consultor |
| `email_from` (por organização) | Remetente padrão da organização (fallback: `SMTP_FROM_EMAIL`) |

### ✅ Checklist de aquecimento (antes de prospectar de verdade)

1. **Use um domínio de envio dedicado** (ex.: `@suaempresa.com.br`) — evite a caixa pessoal de um funcionário.
2. **Configure SPF, DKIM e DMARC** no domínio, alinhados ao `SMTP_FROM_EMAIL`.
3. **Aqueça progressivamente**: comece com `daily_email_limit` baixo (5–10 na 1ª semana) e suba gradualmente (10 → 20 → 40) conforme a taxa de abertura sobe e o *bounce* cai.
4. **Envie automaticamente apenas para contatos verificados** — contatos heurísticos não saem sozinhos (fique atento ao badge "verificado" na aba Contatos).
5. **Monitore bounce** (`email_suppressions`) **e tracking** (aberturas/cliques). Alternativas gerenciadas como Brevo, Resend ou Zoho já cuidam de DKIM e reputação, com planos gratuitos ou de baixo custo.

> O envio automático exige `auto_send_email=true` **e** `email_verified=true` no destinatário. O modo humano-no-loop continua sendo o padrão do sistema.

---

## 💾 Backup do banco de dados

O volume `db_backups` é montado em `/backups` dentro do container do PostgreSQL. Sugestão de cron no host:

```bash
docker compose exec db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -Fc -f /backups/$(date +%F).dump
```

---

## 🧪 Testes

O projeto usa **Pytest** para a suíte de testes automatizados (configuração em `pytest.ini`, dependências em `requirements-dev.txt`).

```bash
pip install -r requirements-dev.txt
pytest
```

---

## 📖 Documentação

Toda a documentação detalhada do projeto está em [`docs/`](./docs), escrita em português. Ordem de leitura recomendada:

1. **`context.md`** — estado atual do projeto
2. **`architecture.md`** — arquitetura do sistema
3. **`business-rules.md`** — regras de negócio

Antes de propor mudanças, consulte também:

- **`decisions.md`** — decisões de arquitetura já tomadas
- **`coding-standards.md`** / **`agents.md`** — convenções de código e de agentes automatizados

Outros arquivos úteis na raiz do repositório:

- **[`QUICKSTART.md`](./QUICKSTART.md)** — guia passo a passo de inicialização (Windows)
- **[`AGENTS.md`](./AGENTS.md)** — diretrizes para agentes de automação de código

---

## 🛠️ Solução de problemas comuns

<details>
<summary><strong>Erro: "não existe a coluna follow_ups.attempts"</strong></summary>

**Causa**: migração pendente do banco de dados.
**Solução**: execute `alembic upgrade head` dentro de `services/workers`.
</details>

<details>
<summary><strong>Erro: "failed to connect to docker API"</strong></summary>

**Causa**: Docker Desktop não está em execução (relevante apenas se você optou pelo fluxo com Docker — ver Opção B ou "Rodando em produção").
**Solução**: inicie o Docker Desktop e aguarde o status "running", ou use o fluxo **sem Docker** da Opção A (`setup.ps1`/`setup.cmd`).
</details>

<details>
<summary><strong>Setup do Windows (`setup.ps1`) falha ou trava</strong></summary>

**Causa**: `setup.ps1` é idempotente — pode ser reexecutado com segurança. Ele detecta um PostgreSQL já instalado ou baixa um binário embarcado (`embedded-postgres-binaries-windows-amd64`) via `curl.exe`.
**Solução**: rode novamente `powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1`. Se o download falhar por rede/proxy, verifique conectividade e tente de novo — o hash dos requirements evita reinstalação desnecessária.
</details>

<details>
<summary><strong>API não inicia ou apresenta erro de imports</strong></summary>

**Causa**: dependências não instaladas ou ambiente virtual não ativado.
**Solução**:

```bash
cd services/api
# ative o venv (source venv/bin/activate no Linux/macOS ou .\venv\Scripts\activate no Windows)
pip install -r requirements.txt
```
</details>

<details>
<summary><strong>Web não carrega ou retorna erro 500</strong></summary>

**Causa**: o frontend não consegue se conectar à API.
**Solução**: verifique se `apps/web/.env.local` contém `NEXT_PUBLIC_API_URL=http://localhost:8000`.
</details>

<details>
<summary><strong>Porta 8000 ou 3001 já está em uso</strong></summary>

```bash
# Windows — descobrir o processo usando a porta 8000
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/macOS
lsof -i :8000
kill -9 <PID>
```
</details>

---

## 🗺️ Roadmap

O projeto segue roadmaps documentados internamente (ex.: entregabilidade e aquecimento de e-mail, itens 4.1–4.3). Consulte `docs/` para o roadmap completo e o histórico de decisões técnicas.

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Antes de abrir um Pull Request:

1. Leia `docs/coding-standards.md` para as convenções de código do projeto.
2. Verifique `docs/decisions.md` para entender decisões arquiteturais já tomadas.
3. Garanta que a suíte de testes (`pytest`) está passando.
4. Descreva claramente o problema resolvido ou a funcionalidade adicionada no PR.

---

## 📄 Licença

Este projeto é distribuído sob a licença [MIT](LICENSE).

---

<div align="center">

Feito para acelerar a prospecção B2B de PMEs brasileiras.

</div>