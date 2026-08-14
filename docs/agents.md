# Regras para Agentes de IA

> Este arquivo é lido pelo agente no início de cada sessão e vale para todas as
> tarefas neste repositório. Ele funciona como o "contrato" do que consultar,
> que skills carregar, como escrever e como entregar código. Sempre em PT-BR.
>
> **Fonte primeira do estado vivo:** `docs/context.md` (ler primeiro, ele aponta
> o que ler em seguida) e `docs/roadmap-vendas.md` (mapa-norte: o que falta).

---

## 1. Fluxo de trabalho — antes de qualquer tarefa (não pule etapas)

1. **Graphify-first.** Para qualquer pergunta sobre o código, rode
   `graphify query "<pergunta>"` (subgrafo escopado) antes de grep/leitura
   ampla; use `graphify path "A" "B"` (relações) e `graphify explain "conceito"`
   (foco). Se `graphify-out/wiki/index.md` existir, use-o para navegação ampla.
   - CLI: Windows `C:\Python314\Scripts\graphify.exe`; Linux
     `/tmp/opencode/graphify-venv/bin/graphify`. Se `graphify-out/graph.json`
     não existir, gere: `graphify extract . --code-only && graphify cluster-only . --no-label`.
   - Pode pular o graphify **só** se a tarefa for sobre saída errada do grafo ou
     se o usuário mandar não usar.
2. **Leia `docs/context.md`** — estado atual + seção "Próximo passo imediato".
   No fim da sessão, atualize-o.
3. **Carregue a skill certa para o momento** (matriz na §2) *antes* de escrever
   código — especialmente frontend: `frontend-design` e
   `vercel-react-best-practices` são obrigatórias para qualquer edição em
   `apps/web`.
4. Leia `docs/architecture.md` e `docs/business-rules.md`; para o *porquê*,
   `docs/decisions.md` antes de propor mudança; padrões em
   `docs/coding-standards.md`. Em `apps/web`, leia também `apps/web/AGENTS.md`
   (Next.js 16 tem breaking changes — docs em `node_modules/next/dist/docs/`).
5. Confirme o entendimento da tarefa antes de escrever código.

---

## 2. Matriz de skills — qual usar em cada momento

| Momento | Skills (carregar nesta ordem) |
|---|---|
| **UI nova / redesign visual** (`apps/web`) | `frontend-design` (direção estética) → `vercel-react-best-practices` (performance/data fetching) |
| **Código React/Next existente** (refatorar, corrigir, revisar) | `vercel-react-best-practices` (+ `frontend-design` se envolver visual) |
| **Auditar UI existente / acessibilidade / UX** ("review my UI") | `web-design-guidelines` |
| **Estilos Tailwind** (classes/tokens) | `tailwind` (projeto usa **v4** — verificar v3 × v4 antes de mexer) |
| **Feature/bug test-first ou pedir testes** | `tdd` (red-green-refactor; teste antes do código) |
| **Auditar/evoluir a arquitetura** | `improve-codebase-architecture` (gera relatório visual de aprofundamento) |
| **Automatizar navegador / QA / testar a app web / Electron** | `agent-browser` |
| **Pergunta sobre o código em geral** | `/graphify` (skill) — sempre antes de grep quando o grafo existir |
| **Procurar/instalar skill nova** | `find-skills` (`npx skills add <repo>@skill -g -y`) |
| **Configurar o próprio opencode** | `customize-opencode` (nunca usar para código do app) |
| **Firebase** | não se aplica (este repo usa Postgres) — ignorar `firebase-security-rules-auditor` |
| **Issue tracker / vocabulário** | `setup-matt-pocock-skills` — só configuração inicial |

Regra: a skill certa **define o approach**; carregar depois de escrever código
não conta.

---

## 3. Convenções de código (cheat-sheet obrigatória)

Backend/workers/API:
- **Tudo `async`**: `httpx.AsyncClient` (nunca `requests`), nunca função
  síncrona em serviço. SMTP síncrono fica fora do event loop (threadpool).
- **Filtros SQLAlchemy com `&`/`|`**, nunca `and`/`or` do Python.
- **`logging`, nunca `print`** em serviços.
- **Config só via `src/config/settings.py`** (pydantic-settings). Nunca ler
  `os.environ` direto nas rotas/services.
- **Models definidos uma única vez** em
  `services/workers/src/database/models.py`; API re-exporta via
  `services/api/src/db/models.py` — nunca duplicar.
- **Migrations**: criar nova (`alembic revision --autogenerate` em
  `services/workers`), **nunca editar existentes**, nunca dropar coluna em prod
  (marcar deprecated).
- Um `XService` por arquivo em `src/services/`. Orquestração nova vai em
  `enrichment_orchestrator.py` ou `main.py`, não em serviço irmão.
- Nomes PT-BR nos textos de UI/prompts/docs; identificadores em inglês.

Frontend (`apps/web`):
- shadcn/ui sobre `@base-ui/react`: usar a prop **`render`**, nunca `asChild`.
- **Todo `SelectValue` exige rótulo explícito** (`children={(value) => label}`)
  — sem ele o Base UI mostra o valor cru (enum/UUID). Bug recorrente (C1).
- Datas via `toLocaleString/toLocaleDateString("pt-BR")`; dinheiro
  `toLocaleString("pt-BR", { style: "currency", currency: "BRL" })`.
- Ícones: `lucide-react` (1.x removeu ícones de marca — usar SVG próprio).
- Respeitar C1/C17: targets de toque ≥ 44px no mobile, `SelectValue` com label.

Regras transversais:
- **Análise de site/prospecto é SEMPRE passiva** (Lei 12.737/2012): nada de
  probe, injeção, autenticação forçada, varredura de paths sensíveis.
- Nunca inventar API/endpoints/schemas — consultar os routes reais.
- Nem pensar em commitar `.env` ou chaves; referenciar por nome de env var.

---

## 4. Regras de negócio que orientam mudanças

- **Score 0–100**: `>= 60` → `QUALIFICADO` (entra no outreach), `< 60` →
  `DESQUALIFICADO`.
- Funil: `NOVO → ANALISADO → QUALIFICADO/DESQUALIFICADO → CONTATADO →
  RESPONDIDO → REUNIAO_MARCADA → REUNIAO_FEITA → PROPOSTA_ENVIADA` (ou `PERDIDO`).
- **Lead sem site** não é desqualificado: em campanha de presença web é
  público-alvo (ponta pelo caminho business). **Falha do Groq mantém `NOVO`**
  (reprocessável), jamais forjar `score 0 ANALISADO`.
- **Gate de envio automático**: e-mail `email_verified=True`; cadência no
  `auto_send_email` respeita teto diário/janela/teto por hora; heurístico nunca
  é enviado automaticamente.
- **`PERDIDO` por ausência de resposta** re-entra na fila após
  `LOST_REQUEUE_DAYS` (90; `0` desativa). Perdas deliberadas
  (`PRECO/CONCORRENTE/PRAZO/OUTRO`) e `opt_out` **não** voltam. Cadência fechada
  sem resposta → `PERDIDO`/`NAO_RESPONDEU` após `CADENCE_CLOSE_GRACE_DAYS` (7).
- **CONSULTOR é autônomo** (cria/gerencia campanhas próprias) — nenhuma
  melhoria restringe isso. ANALYST/MANAGER/owner veem BI e todos os leads.
- Ações administrativas gravam `org_audit_log` (nunca valor de secret).

---

## 5. Como entregar uma tarefa

1. Escrever o código (após §1 + skill da §2).
2. Executar a verificação da camada (comandos da §6) e mostrar o output.
3. Se houver erro, corrigir antes de entregar.
4. Listar os arquivos modificados.
5. Atualizar as docs (§7) e sugerir o commit.

---

## 6. Verificação por camada (rodar SEMPRE ao tocar na camada)

Backend (`tests/` na raiz):
- Unit: `python -m pytest tests -q` (da raiz; deps:
  `pip install -r requirements-dev.txt`).
- Compile: `python -m compileall -q services/api services/workers`.

API (CWD **`services/api`** obrigatório — resolve `../../.env`):
- `uvicorn main:app --reload --port 8000` → http://localhost:8000/docs.
- Health: `GET /health` → `{"status":"ok","database":"ok"}`.

Workers (CWD **`services/workers`**):
- `python -m src.main` (enriquecimento+scoring, limit=5);
  `python -m src.seeds.scoring_templates` (seed idempotente);
  `alembic upgrade head`.
- `run_lead_collection(...)` é `async` — não rodar via `python -m`.

Web (CWD `apps/web`):
- `npm run lint` → `npx tsc --noEmit` → `npm run build`.

CI executa: web (lint, tsc, build) + backend (compileall, pytest) +
migrations (upgrade head + seed smoke).

---

## 7. Definition of Done (fechamento de item/sessão)

- [ ] Branch própria + commits convencionais (`feat|fix|refactor|docs|chore|test`).
- [ ] Migração (se houver) aplicada em Postgres real; **nunca** editada depois.
- [ ] Teste do caminho feliz + falha (pytest ou smoke manual) criado/quando couber.
- [ ] Verificação da camada (§6) limpa e documentada na resposta.
- [ ] Docs vivas: `docs/context.md` (Estado atual + "Próximo passo imediato") e,
      se mudou arquitetura, `docs/architecture.md`; status do item em
      `docs/roadmap-vendas.md` (§5 tabela + seção do item); novas decisões em
      `docs/decisions.md`.
- [ ] `graphify update .` após mudanças de código (AST-only, sem custo).
- [ ] Nunca commitar `.env`/chaves; perguntar antes de instalar dependência.

---

## 8. Pitfalls operacionais conhecidos (consulte antes de tocar a área)

- **PDF no Windows**: WeasyPrint precisa de GTK/Pango — `pdf_report_service.
  _setup_windows_gtk()`; se quebrar, é precedência da Pango antiga
  (`Gtk-Runtime` vs `GTK3-Runtime Win64`).
- **`.env` compartilhado** na raiz via `env_file='../../.env'` — CWD dos
  serviços Python **não pode mudar**.
- **`JWT_SECRET` obrigatório** na API (não sobe sem ele); `NEXTAUTH_SECRET`
  **estável** em `apps/web/.env.local` (mudou → sessão/decrypt quebra).
- **`TRACKING_BASE_URL`** vazio desliga pixel/redirect (tracking off em dev).
- **Pipeline roda em job-consumer** (`jobs_consumer.py`, claim atômico) — não
  recriar `asyncio.create_task` no handler de request.
- **Rate-limit Groq**: pacing global `GROQ_MIN_INTERVAL_SECONDS` (default 20) e
  backoff `GROQ_MAX_RETRIES` (5) — não reduzir sem revalidar (18/20 leads já
  ficaram sem score por 429).
- **`SMTP_PORT=` vazio** quebra o pydantic no boot — setar `587`.
- **Windows**: `package-lock.json` órfão em `~/` corrompe o workspace root do
  Turbopack (limpar `apps/web/.next` antes de subir o dev).
- **`Select` novo** (Base UI): sempre com rótulo no `SelectValue` (ver §3).
- **Quota por org** conta uso; **cota do pool** ainda não é contabilizada
  (nota no roadmap 4.14) — não estimar Gate pela soma do pool.

---

## 9. Referências

- Fluxo _como rodar/verificar_ mais resumido: `AGENTS.md` (raiz).
- Estado vivo + histórico de sessões: `docs/context.md`.
- Mapa-norte com backlog e tabela de status: `docs/roadmap-vendas.md`.
- Regras do produto (funil, cadência, tracking): `docs/business-rules.md`.
- Stack/arquitetura/modelos/endpoints: `docs/architecture.md`.
- Decisões (ADRs): `docs/decisions.md`. Padrões de código: `docs/coding-standards.md`.