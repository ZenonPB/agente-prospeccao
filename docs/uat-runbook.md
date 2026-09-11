# Runbook de UAT — Golden Path (Fatias 1–6)

Checklist de validação com usuário real (AlphaMec). Requisito: stack local de pé
(Postgres via `docker compose up -d`, API `uvicorn main:app --reload --port 8000`
a partir de `services/api`, web `npm run dev` em `apps/web` → :3001) e `.env`
com `JWT_SECRET`, `GROQ_API_KEY`, `GOOGLE_API_KEY` preenchidos.

## 1. Onboarding multi-tenant
1. Acesse `http://localhost:3001/register`, crie conta → cai no dashboard com
   workspace pessoal criado automaticamente.
2. `Configurações → Membros`: convide um segundo usuário (email real ou
   dumpmail) com papel CONSULTOR; aceite o convite pelo link recebido.
3. Com o consultor logado, confirme que ele não vê leads/campanhas da org do
   dono (org switcher só mostra a própria org).

## 2. Campanha + coleta
1. `Campanhas → Nova`: crie campanha com segmento sugerido pela IA
   (`/suggest-segment`, rate-limit 20/min — não martelar o botão).
2. Rode coleta (Google Places ou CNAE). Verifique leads aparecendo na lista com
   status `NOVO`.

## 3. Enriquecimento + scoring
1. Rode o worker (`python -m src.main` em `services/workers`, limit=5) ou o
   pipeline pela UI.
2. Leads com site ganham dados técnicos; **leads sem site continuam sendo
   pontuados pelo caminho business** (nunca desqualificados por falta de site).
3. Score ≥ 60 → `QUALIFICADO`; < 60 → `DESQUALIFICADO` (com motivo opcional no
   diálogo — sem `window.prompt`).

## 4. CRM verdadeiro (Fatias 5–6)
1. No kanban (`Vendas`), arraste um lead QUALIFICADO para `CONTATADO` e depois
   `RESPONDIDO` (confirmação por diálogo acessível, não `window.confirm`).
2. Marque um lead como **PERDIDO**: diálogo exige motivo da lista
   (`PRECO/PRAZO/NAO_RESPONDEU/CONCORRENTE/OUTRO`) — nunca motivo digitado
   livre.
3. Marque outro como **DESQUALIFICADO**: diálogo com textarea opcional.
4. Confira na página do lead que o badge de status e o forecast refletem o
   outcome registrado (LOST ≠ DISQUALIFIED no BI).

## 5. Export cross-tenant
1. Na campanha, exporte para Google Sheets (CSV) como MANAGER: todas as linhas.
2. Repita como CONSULTOR atribuído a apenas 1 lead: CSV contém **somente** os
   leads do próprio escopo.
3. (Opcional, com segunda org de teste) tente abrir o export de campanha de
   outra org pelo ID → deve retornar 404.

## 6. Relatórios
1. `Relatórios → Exportar PDF` (ANALYST/MANAGER apenas; CONSULTOR não vê o
   botão). PDF deve refletir só os dados da org ativa.

## 7. Segurança (sanity rápido)
- Login errado 5× no mesmo email → lockout 15 min (429 com mensagem).
- `POST /api/leads/{id}/mark-lost` com `X-Organization-Id` de outra org → 403.
- Rate limits de auth ativos: register 5/min, login 10/min, forgot 3/min.

## Evidências
Para cada item, capture screenshot e anexe no relatório de UAT. Falhas
encontradas → abrir card em `docs/roadmap-*` com passos de reprodução.
