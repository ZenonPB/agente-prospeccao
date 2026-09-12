# Runbook de UAT — Golden Path AlphaMec

Checklist de validação com usuário real. Requisito: stack local de pé
(Postgres via `docker compose up -d`, API `uvicorn main:app --reload --port 8000`
a partir de `services/api`, web `npm run dev` em `apps/web` → :3001) e `.env`
com `JWT_SECRET`, `GROQ_API_KEY`, `GOOGLE_API_KEY` preenchidos.

## 0. Pré-flight e migrations

1. Em `services/workers`, rode `alembic heads` e confirme uma única cabeça.
2. Rode `alembic upgrade head` em banco de teste antes de produção.
3. Confirme que nenhum segredo/token aparece em logs.
4. Execute a suíte backend e os gates do frontend antes do UAT funcional.

## 1. Onboarding multi-tenant
1. Acesse `http://localhost:3001/register`, crie conta → cai no dashboard com
   workspace pessoal criado automaticamente.
2. `Configurações → Membros`: convide um segundo usuário com papel CONSULTOR;
   aceite o convite pelo link recebido.
3. Com o consultor logado, confirme que ele não vê leads/campanhas da org do
   dono (org switcher só mostra organizações das quais é membro).

## 2. Campanha + coleta
1. `Campanhas → Nova`: crie campanha com segmento sugerido pela IA
   (`/suggest-segment`, rate-limit 20/min — não martelar o botão).
2. Rode coleta (Google Places ou CNAE). Verifique leads aparecendo na lista com
   status `NOVO`.

## 3. Enriquecimento + scoring
1. Rode o worker (`python -m src.main` em `services/workers`, limit=5) ou o
   pipeline pela UI.
2. Leads com site ganham dados técnicos; **leads sem site continuam sendo
   pontuados pelo caminho business**.
3. Valide score, prioridade, evidências e justificativa com exemplos reais.

## 4. CRM verdadeiro
1. No kanban (`Vendas`), mova um lead QUALIFICADO para `CONTATADO` e depois
   `RESPONDIDO`.
2. Marque um lead como **PERDIDO**: o motivo deve ser obrigatório e vir do enum
   (`PRECO/PRAZO/NAO_RESPONDEU/CONCORRENTE/OUTRO`).
3. Marque outro como **DESQUALIFICADO** e confirme que ele não é contabilizado
   como perda comercial.
4. Confirme que PERDIDO/DESQUALIFICADO não recebem nenhuma etapa de cadência
   pendente ou automática.
5. Confira na página do lead que trilha, status e forecast refletem o outcome.

## 5. Inbound de e-mail por organização

O caminho preferencial é `POST /api/webhooks/email/inbound/{token}`. O token é
opaco e por organização; somente o SHA-256 é persistido. A rota antiga
`POST /api/webhooks/email/inbound` existe temporariamente e exige **os dois**
headers `X-Webhook-Secret` e `X-Organization-Id`.

Antes de produção:

1. Gere/configure um token distinto para cada organização que usa inbound.
2. Reaponte Postmark/SendGrid (ou equivalente) para a URL com token da org.
3. Não registre a URL completa do webhook em logs, tickets ou screenshots.
4. Teste duas organizações com o **mesmo endereço de remetente** e confirme que
   uma resposta da org A altera somente o lead da org A.
5. Token inválido, org ausente na rota legada e segredo inválido devem falhar
   sem criar Message, LeadActivity, Notification ou alterar FollowUp.
6. Só remova a configuração legada do provedor depois de validar a rota nova.

## 6. Export cross-tenant
1. Na campanha, exporte CSV como MANAGER: todas as linhas autorizadas.
2. Repita como CONSULTOR atribuído a apenas 1 lead: CSV contém **somente** os
   leads do próprio escopo.
3. Com segunda org de teste, tente abrir o export de campanha de outra org pelo
   ID → deve retornar 404/403 sem revelar conteúdo.

## 7. Relatórios
1. `Relatórios → Exportar PDF` (ANALYST/MANAGER apenas; CONSULTOR não vê o
   botão). PDF deve refletir só os dados da org ativa.

## 8. Segurança
- Login errado 5× no mesmo email → lockout conforme política configurada.
- Acesso a lead/job de outra org ou job órfão → recusa fechada.
- Inbound nunca resolve lead globalmente por e-mail.
- Rate limits de auth e webhooks ativos.
- Tokens, API keys e segredos não aparecem em respostas nem logs.

## Evidências
Para cada item, capture screenshot ou saída de teste e anexe ao registro de UAT.
Não marque `ALPHAMEC — PRODUCTION READY: YES` enquanto houver blocker aberto,
gate técnico vermelho ou etapa do Golden Path que exija intervenção de dev.
