##### Erro ao tentar inicializar a coleta com mercados em Araraquara, após ter feito uma coleta de uma campanha já:

(psycopg2.errors.UniqueViolation) duplicate key value violates unique constraint "uq_leads_org_normalized_domain" DETAIL: Key (organization_id, normalized_domain)=(f14e67ca-093a-4160-891a-361666f5af29, site.supermercado14.com.br) already exists. [SQL: INSERT INTO leads (id, organization_id, place_id, name, company_name, cnpj, address, website, normalized_domain, phone, whatsapp, email, category, city, state, country, google_rating, google_rating_count, google_maps_uri, company_linkedin_url, instag ... 10378 characters truncated ... s::UUID, %(assigned_at__9)s, %(opt_out__9)s, %(updated_at__9)s) RETURNING leads.created_at, leads.id] [parameters: {'email__0': None, 'phone__0': '(16) 3336-7430', 'opt_out__0': False, 'priority_reasoning__0': None, 'updated_at__0': None, 'qualification_score__0': 0, 'assigned_to_id__0': None, 'city__0': 'Araraquara', 'cnpj__0': None, 'place_id__0': 'ChIJcVaQOdjzuJQRAy5gezLafTU', 'google_rating_count__0': 2571, 'notes__0': None, 'organization_id__0': UUID('f14e67ca-093a-4160-891a-361666f5af29'), 'status__0': 'NOVO', 'post_sale_channel__0': None, 'value__0': None, 'priority__0': None, 'post_sale_contacted_at__0': None, 'assigned_at__0': None, 'primary_need__0': None, 'id__0': UUID('cceef7e2-23e5-4df8-b8ca-bbb49a1a0eef'), 'qualification_reason__0': None, 'address__0': None, 'country__0': 'Brasil', 'instagram_url__0': None, 'suggested_subject__0': None, 'google_maps_uri__0': 'https://maps.google.com/?cid=3854476766452133379&g_mp=Cidnb29nbGUubWFwcy5wbGFjZXMudjEuUGxhY2VzLlNlYXJjaFRleHQQAhgEIAA', 'normalized_domain__0': 'site.supermercado14.com.br', 'lost_reason__0': None, 'company_linkedin_url__0': None, 'segment_opportunity__0': None, 'expected_close_date__0': None, 'outcome_date__0': None, 'campaign_id__0': UUID('254bf683-26c3-4097-b795-37d4e4b099d0'), 'state__0': 'SP', 'contract_outcome__0': None, 'google_rating__0': 4.3, 'company_name__0': 'Supermercados 14 - Loja 02', 'executive_summary__0': None, 'category__0': 'Supermercado', 'whatsapp__0': None, 'pitch_angle__0': None, 'negotiation_stage__0': None, 'next_action_at__0': None, 'last_contacted_at__0': None, 'website__0': 'http://site.supermercado14.com.br/nossaslojas', 'name__0': 'Supermercados 14 - Loja 02', 'email__1': None, 'phone__1': '(16) 3336-9298', 'opt_out__1': False ... 370 parameters truncated ... 'last_contacted_at__8': None, 'website__8': None, 'name__8': 'Supermercado São Luiz', 'email__9': None, 'phone__9': '(16) 3461-1920', 'opt_out__9': False, 'priority_reasoning__9': None, 'updated_at__9': None, 'qualification_score__9': 0, 'assigned_to_id__9': None, 'city__9': 'Araraquara', 'cnpj__9': None, 'place_id__9': 'ChIJhxAgp6z2uJQRJV9swt4DtRQ', 'google_rating_count__9': 2572, 'notes__9': None, 'organization_id__9': UUID('f14e67ca-093a-4160-891a-361666f5af29'), 'status__9': 'NOVO', 'post_sale_channel__9': None, 'value__9': None, 'priority__9': None, 'post_sale_contacted_at__9': None, 'assigned_at__9': None, 'primary_need__9': None, 'id__9': UUID('44483df3-399e-4d5e-b102-c0adb0d3880f'), 'qualification_reason__9': None, 'address__9': None, 'country__9': 'Brasil', 'instagram_url__9': None, 'suggested_subject__9': None, 'google_maps_uri__9': 'https://maps.google.com/?cid=1492103106822692645&g_mp=Cidnb29nbGUubWFwcy5wbGFjZXMudjEuUGxhY2VzLlNlYXJjaFRleHQQAhgEIAA', 'normalized_domain__9': 'paulistaoatacadista.com.br', 'lost_reason__9': None, 'company_linkedin_url__9': None, 'segment_opportunity__9': None, 'expected_close_date__9': None, 'outcome_date__9': None, 'campaign_id__9': UUID('254bf683-26c3-4097-b795-37d4e4b099d0'), 'state__9': 'SP', 'contract_outcome__9': None, 'google_rating__9': 4.2, 'company_name__9': 'Paulistão Atacadista', 'executive_summary__9': None, 'category__9': 'Supermercado', 'whatsapp__9': None, 'pitch_angle__9': None, 'negotiation_stage__9': None, 'next_action_at__9': None, 'last_contacted_at__9': None, 'website__9': 'http://www.paulistaoatacadista.com.br/', 'name__9': 'Paulistão Atacadista'}] (Background on this error at: https://sqlalche.me/e/20/gkpj)


#### ao tentar mexer o card do kanban para a próxima seção:

## Error Type
Runtime Error

## Error Message
Base UI: MenuGroupContext is missing. Menu group parts must be used within <Menu.Group> or <Menu.RadioGroup>.


    at DropdownMenuLabel (src/components/ui/dropdown-menu.tsx:64:5)
    at children (src/components/vendas/kanban-board.tsx:562:39)

## Code Frame
  62 | }) {
  63 |   return (
> 64 |     <MenuPrimitive.GroupLabel
     |     ^
  65 |       data-slot="dropdown-menu-label"
  66 |       data-inset={inset}
  67 |       className={cn(

Next.js version: 16.2.10 (Turbopack)
Base UI: MenuGroupContext is missing. Menu group parts must be used within <Menu.Group> or <Menu.RadioGroup>.

src/components/ui/dropdown-menu.tsx (64:5) @ DropdownMenuLabel

  62 | }) {
  63 |   return (
> 64 |     <MenuPrimitive.GroupLabel
     |     ^
  65 |       data-slot="dropdown-menu-label"
  66 |       data-inset={inset}
  67 |       className={cn(

Call Stack 18
Show 16 ignore-listed frame(s)
DropdownMenuLabel
src/components/ui/dropdown-menu.tsx (64:5)
children
src/components/vendas/kanban-board.tsx (562:39)


#### Também está dando erro ao tentar gerar mensagem com IA

Gerando sequência personalizada de outreach com IA -> Falha ao gerar mensagem

---

## Resolução (2026-08-17) — branch `fix/erros-coleta-kanban-outreach`

Os três erros acima foram corrigidos:

1. **UniqueViolation `uq_leads_org_normalized_domain` na coleta** — causa raiz:
   `services/api/src/db/session.py` usa `autoflush=False`, então a dedup dentro
   do loop do `pipeline_worker.py` não enxergava os leads recém-adicionados no
   MESMO lote. Quando o Google devolve duas lojas da mesma rede com o mesmo
   site (ex.: "Supermercados 14" e "Supermercados 14 - Loja 02" →
   `site.supermercado14.com.br`), a segunda passava pela dedup e violava a
   constraint no `commit` em lote — derrubando a transação inteira (0 leads
   salvos). Fix:
   - `filter_new_batch_items()` — filtra, em Python, a 2ª ocorrência do mesmo
     `normalized_domain` dentro do lote (e place_ids já conhecidos da org);
   - `db.flush()` por lead dentro de `with db.begin_nested():` (SAVEPOINT) —
     o flush expõe o lead às dedupes seguintes e um `IntegrityError` residual
     só descarta a linha do conflito, sem rollback do lote.

2. **`MenuGroupContext is missing` no kanban** — causa raiz: `DropdownMenuLabel`
   (Base UI `Menu.GroupLabel`) exige estar dentro de `Menu.Group`/`RadioGroup`.
   Os usos em `kanban-board.tsx` ("Atribuir para" e "Mover para") e em
   `lead-list.tsx` (bulk "Atribuir para") ficavam direto no
   `DropdownMenuContent`. Fix: envolver os labels em `<DropdownMenuGroup>`
   (mesmo padrão do `header.tsx`).

3. **"Falha ao gerar mensagem" (502)** — causa raiz: `OutreachService.
   generate_sequence` fazia chamada **crua** à Groq (sem pacing global, sem
   retry/backoff de 429/5xx), ao contrário do scoring que já usa
   `provider_client.groq_json_chat`. No tier free, um 429 qualquer retornava
   `None` → 502. Fix: `generate_sequence` migrado para `groq_json_chat`
   (herda pacing + retry com `Retry-After` + gate/consumo de cota quando
   `db`/`organization_id` informados) e `max_tokens` 3200→6000 (JSON não
   trunca mais). As rotas `generate-messages`/cadência passam `db`/org e o
   consumo de cota ficou centralizado no provider (removido o `consume_quota`
   manual duplicado).

**Verificado:** `python -m pytest tests -q` → **285 passed** (6 novos de dedup
de lote + 3 do outreach→provider); `compileall` OK; web `npm run lint` +
`npx tsc --noEmit` + `npm run build` limpos.

---

## Varredura geral (2026-08-17) — branch `fix/sweep-bugs`

Revisão completa do sistema + troca do modelo de LLM (o anterior deixou de ter
suporte). Itens corrigidos:

**Modelo de LLM centralizado:**
- Modelos agora são config em `.env`: `GROQ_MODEL_CLASSIFY` (scoring/router) e
  `GROQ_MODEL_GENERATION` (outreach/segmentos/brief/templates) — antes cada um
  dos 6 serviços tinha constante própria (trocar o modelo exigia editar 6
  arquivos, e docstrings ainda citavam modelos descontinuados).
- Segmento/brief/router/geração de template migrados para
  `provider_client.groq_json_chat` (pacing global + retry 429/5xx + cota).
- Cota de `suggest-segment`/`from-brief` corrigida (consumo único no provider).

**Bugs críticos de runtime:**
- Auto-envio de follow-ups quebrado por `NameError`: `cadence_service.run_due`
  chamava `org_sends_today` (não existia) — corrigido para `sends_today`.
- `change-password` validava a senha atual mas **nunca gravava a nova hash** —
  agora persiste e commita.
- Import CSV com coluna de contato quebrava a FK de `contacts.lead_id`:
  `bulk_save_objects` com lista mista ignorava a relationship. Agora salva na
  ordem Lead→Contact (`add_all`) e `imported_count` conta só leads (novo campo
  `contacts_count`).

**Altos:**
- Playbooks: owner/admin não conseguiam editar/remover (comparação de enum por
  string `"OWNER"` nunca casava com o valor `"owner"`). Comparação por enum.
- Templates globais (seeds) agora são read-only via PATCH (400) — edição de um
  usuário afetava o scoring de todas as orgs.
- **Org switcher real (multi-org)**: o frontend envia `X-Organization-Id` (HTTP
  e websocket do pipeline) e o backend resolve a org/membership por ele,
  validando que o usuário é membro da org pedida (403 se não). Sem header,
  comporta como antes (primeira membership).

**Housekeeping:** `datetime` no topo de `leads.py` (NameError latente),
`member`→`target_member` na atribuição, tipo `_user`→`Organization` em
`orgs.py`, `.is_(None)` no `pipeline_worker`, `and_()`→`&` no `cadence_service`.

**Verificado:** `pytest` → **307 passed** (+22); `compileall` OK; web lint/
tsc/build limpos.

---

## Resolução (2026-08-18) — branch `fix/outreach-tpm-413`

**"Falha ao gerar mensagem" (502) persistente** — mesmo após o fix anterior
(outreach via `groq_json_chat`), a geração continuava falhando **sempre**.
Causa raiz:

1. **HTTP 413 determinístico por TPM**: `generate_sequence` usava
   `max_tokens=6000` fixo. Com prompt real (playbook + scheduling_url +
   evidências) ~2150 tokens, o request ia a ~8150 tokens > limite de **8000
   TPM** do tier `on_demand` da org → `413 Request too large`, que **não
   estava na lista de retriable** do provider → `None` na 1ª tentativa → 502.
2. **HTTP 400 `json_validate_failed` intermitente**: o modelo de geração
   (`qwen/qwen3.6-27b`) tem modo `thinking` ativo por padrão; com
   `response_format: json_object`, o raciocínio contamina a saída e a Groq
   rejeita com 400 (não-retriable) → 502 intermitente.

Fix:

- `provider_client.groq_json_chat` ganhou `reasoning_effort` (opcional): com
  `"none"`, desliga o thinking do qwen* — JSON sai limpo e a saída cai de
  ~5000+ para ~800 tokens (medido: 788).
- `provider_client` agora trata **HTTP 413** reduzindo `max_tokens`
  progressivamente (1024 a 1024) e retentando, em vez de desistir na primeira
  chamada — robusto para qualquer prompt que cresça.
- `outreach_service.generate_sequence` usa `max_tokens=5000` (antes 6000) +
  `reasoning_effort="none"`: prompt 2150 + 5000 = 7150 < 8000 TPM, sem 413.
- O mesmo `reasoning_effort="none"` foi aplicado aos outros serviços de geração
  (segmentos, brief e templates) para eliminar o 400 intermitente em todos.

**Verificado:** 6 novos testes (2 de 413 no provider + ajustes de
outreach/segmentos/brief/templates) → `python -m pytest tests -q` → **312
passed**; chamada real à Groq com o mesmo payload que dava 413 → **200 OK** com
JSON completo.