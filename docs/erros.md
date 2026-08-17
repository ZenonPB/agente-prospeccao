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