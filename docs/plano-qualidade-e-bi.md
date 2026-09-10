# Plano de Qualidade, Refino Visual e BI Interativo

> **Propósito deste documento:** registrar o diagnóstico e o plano acordado para
> levar o Prospect.ai a um estado "100%" de qualidade — release-ready, otimizado,
> com boa UI/UX, bom desempenho e segurança. É um plano de **correção e
> aprimoramento do que já existe**, não de construção de novas capacidades do
> roadmap (workflows, CRM sync, API pública, saved searches — esses continuam em
> `docs/roadmap.md`).
>
> **Data do planejamento:** 2026-09-10 · branch `main` · commit `c3e47d2`
> (merge do PR #154) · Alembic head `3d8e0f2a3b4c`.

---

## Decisões tomadas nesta sessão

| Tema | Decisão |
|---|---|
| Horizonte / critério de 100% | **Duas fases:** Fase 1 release-ready; Fase 2 excelência sustentável. |
| Profundidade de segurança | Hardening **pragmático na Fase 1**; RLS/isolamento reforçado e auditoria formal na **Fase 2** (recomendação do agente). |
| UI/UX | Primeiro **corrigir pendências expostas ao usuário**; depois **refino visual**. |
| Paleta de cores | **Não alterar.** Manter os temas atuais (light / dark / AlphaMec). O refino é de layout, tipografia, espaçamento, hierarquia e interação. |
| Dashboards de BI | Deixar **mais bonitos, mais rápidos e com filtro cruzado ao clicar (estilo Power BI)**. |

---

## Estado verificado (evidências da auditoria)

- **Backend / performance:** as rotas principais (`leads`, `campaigns`,
  `notifications`, `pipeline`) já paginam (`offset`/`limit`) e usam
  `joinedload`; commits de performance anteriores já atacaram N+1. Situação
  razoável, mas **não medida sob carga**.
- **Segurança (já presente):** lockout de login, rate limit (`slowapi`),
  headers de segurança, Fernet nos secrets por organização, WebSocket com auth
  na primeira mensagem.
- **Segurança (frágil / faltando):** lockout de login é **em memória**
  (`_login_attempts` em `services/api/src/routes/auth.py`) — quebra em
  multi-processo; JWT **não valida `iss`/`aud`**; HSTS só em produção; RLS do
  Postgres desligado por decisão documentada; validação de webhook inbound a
  revisar.
- **UI/UX (bom):** uso amplo de `aria-label`, skeletons e estados de erro.
- **UI/UX (pendências expostas ao usuário):** `/ajuda`
  (`apps/web/src/app/(protected)/ajuda/page.tsx`) está cheia de `TODO`; botões
  "Em breve" (alterar foto, alterar e-mail) em `configuracoes/page.tsx`;
  política de privacidade é placeholder.
- **BI:** `docs/roadmap.md` e o código confirmam que o período (`period`) já
  propaga e a API aceita `campaign_id`/`consultant_id` em alguns endpoints;
  porém **cada card busca sua própria query** (8 hooks independentes em
  `relatorios/page.tsx`) e **não há filtro cruzado global** — só o dashboard
  tem um `activeFilter` local isolado. Os gráficos principais em
  `components/relatorios/chart-cards.tsx` são **barras CSS manuais**, sem
  clique/drill. **Recharts já está instalado** (`recharts ^3.9.2`), mas
  subutilizado nos cards-chave.
- **Reprodutibilidade:** o ambiente de trabalho atual **não** reproduz a suíte
  nem o lint/build (falta `apps/web/node_modules`, falta `starlette`,
  `python` não está no PATH). `compileall` passou. Reproduzir os gates é um
  item do plano.

---

## FASE 1 — Release-ready

Foco em bloqueadores de lançamento: reprodutibilidade, documentação fiel,
pendências visíveis ao usuário e segurança claramente frágil.

### Task 1 — Restaurar reprodutibilidade de build, testes e lint
- **Objetivo:** garantir que os gates do CI rodam localmente e batem com a
  documentação.
- **Implementação:** instalar deps (`requirements-dev.txt`; `apps/web` via
  `npm ci`); rodar `pytest -q -W error`, `compileall`, `npm run lint`,
  `npx tsc --noEmit`, `npm run build`, `scripts/verify_migrations.py` contra
  Postgres.
- **Teste/Demo:** os cinco gates verdes registrados + head Alembic confirmado.

### Task 2 — Sincronizar documentação com o estado real
- **Objetivo:** eliminar divergências (branch `main` vs `feat/...`; head
  `3d8e0f2a3b4c` vs referências antigas em `architecture.md` e no mapa de
  pendências).
- **Implementação:** atualizar `docs/context.md`, `docs/architecture.md`,
  `docs/00-status-mapa.md`, `docs/pendencias-pos-consolidacao.md`.
- **Demo:** um agente novo responde às perguntas de manutenção sem contradição.

### Task 3 — Remover pendências expostas ao usuário
- **Objetivo:** nenhum placeholder visível em produção.
- **Implementação:** reescrever `/ajuda` com FAQ real (remover `TODO`);
  resolver ou ocultar "Em breve" (foto de perfil, alteração de e-mail);
  substituir/ocultar política de privacidade placeholder até haver texto real;
  revisar botões `disabled`.
- **Teste:** varredura de `TODO`/"Em breve"/placeholder em páginas protegidas =
  0 exposto.
- **Demo:** navegação limpa de `/ajuda`, `/configuracoes` e telas de conta.

### Task 4 — Hardening de segurança pragmático
- **Objetivo:** corrigir o claramente frágil sem reescrever arquitetura.
- **Implementação:**
  - lockout de login **persistente** (hoje em memória — quebra em
    multi-processo);
  - JWT com `iss`/`aud`;
  - HSTS e revisão de headers;
  - revisão de exposição de **secrets/PII em logs**;
  - **validação/assinatura de webhooks inbound**;
  - confirmar dependências pinadas.
- **Teste:** testes de auth (lockout, claims); rejeição de webhook não assinado.
- **Demo:** lockout sobrevive a restart; token inválido por `aud` é rejeitado.

### Task 5 — Baseline de estados de erro/vazio e regressões visíveis
- **Objetivo:** toda tela crítica tem loading, erro e vazio coerentes.
- **Implementação:** auditar telas de lead, campanha, kanban e relatórios;
  padronizar `EmptyState`/erro.
- **Demo:** simular falha de API e ver mensagem tratada, não "NetworkError".

---

## FASE 2 — Excelência, refino visual e BI interativo

Foco em dívida técnica, refino estético (mantendo a paleta), performance e o
BI interativo estilo Power BI.

### Task 6 — Sistema visual consistente (mantendo a paleta)
- **Objetivo:** deixar tudo mais bonito **sem mudar cores**.
- **Implementação:** com as skills de frontend, padronizar espaçamento,
  tipografia, hierarquia, sombras, bordas e estados de hover/focus nos
  componentes `ui/` e nos cards; manter os tokens de cor atuais
  (light/dark/alpha).
- **Demo:** antes/depois de dashboard, relatórios e detalhe do lead.

### Task 7 — Contexto de filtro global de BI (fundação do cross-filter)
- **Objetivo:** um estado de filtro compartilhado por toda a página de
  relatórios/dashboard.
- **Implementação:** criar um provider de filtro (período + campanha +
  consultor + dimensão selecionada); substituir o `activeFilter` isolado; todos
  os hooks passam a ler esse contexto.
- **Teste/Demo:** alterar filtro atualiza todos os cards.

### Task 8 — Endpoints de BI aceitando filtros combinados
- **Objetivo:** o backend suportar drill/cross-filter.
- **Implementação:** estender os endpoints de analytics para aceitar o conjunto
  de filtros (campaign, consultant, stage, band, vertical) de forma consistente
  e org-scoped; garantir índices adequados.
- **Teste:** filtros combinados retornam recortes corretos, sem N+1.
- **Demo:** mesma dimensão filtrada via API retorna o subconjunto esperado.

### Task 9 — Gráficos interativos com clique-para-filtrar (estilo Power BI)
- **Objetivo:** clicar num segmento (etapa do funil, faixa de score, consultor,
  estado no mapa) filtra o painel inteiro.
- **Implementação:** migrar cards-chave para **Recharts** (já instalado) com
  handlers de clique que atualizam o contexto de filtro; realce do item ativo;
  breadcrumb de filtros ativos com botão "limpar".
- **Teste:** clicar num estágio filtra os demais cards; limpar restaura.
- **Demo:** clique no funil → todos os cards refletem aquele recorte.

### Task 10 — Performance do BI
- **Objetivo:** dashboards mais rápidos.
- **Implementação:** consolidar buscas (reduzir os 8 requests independentes
  onde possível); `staleTime`/cache no React Query; memoização de séries;
  lazy-load de mapa/timeline pesados; medir com web vitals.
- **Teste/Demo:** medição de tempo de render antes/depois.

### Task 11 — Refino final e verificação integral
- **Objetivo:** fechar o ciclo.
- **Implementação:** rodar todos os gates; revisar acessibilidade dos gráficos
  interativos (teclado, aria); validar responsividade mobile.
- **Demo:** gates verdes + walkthrough do BI interativo em desktop e mobile.

---

## Notas e ressalvas

- **Cross-filter estilo Power BI** é a maior parte do esforço da Fase 2:
  envolve frontend (contexto de filtro + Recharts) e backend (filtros
  combinados). Alto valor, mas não trivial.
- **Paleta intocada:** todo o refino é de layout, tipografia, espaçamento e
  interação — nenhuma mudança nos tokens de cor.
- **Fora de escopo deste plano:** novas capacidades de produto (workflows,
  CRM sync bidirecional, API pública/API keys, saved searches, Data Health,
  intent real). Essas permanecem rastreadas em `docs/roadmap.md`.

---

## Ordem de execução recomendada

1. Fase 1 completa (Tasks 1 → 5), pois destrava lançamento e dá base confiável.
2. Fase 2 na ordem: Task 6 (visual) → Tasks 7–9 (BI interativo) →
   Task 10 (performance) → Task 11 (verificação final).
3. Alternativa possível: se o BI interativo for prioridade máxima, adiantar
   Tasks 7–9 logo após a Fase 1, antes do refino visual amplo (Task 6).
