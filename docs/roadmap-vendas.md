# Roadmap de Evolução — Agente Prospecção (uso comercial da EJ)

> **Documento-norte** do sistema de prospecção B2B da EJ, construído para
> substituir ferramentas pagas (ex.: Apollo) que são inviáveis financeiramente.
>
> Ele descreve o **estado atual**, o **modelo de organização/papéis** (diretores,
> analistas e consultores) e o **mapa completo de melhorias** priorizadas para
> transformar o software numa máquina de vendas real e profissional.
>
> Criado em 2026-08-04. Atualizar este arquivo conforme cada item for entregue.

---

## 0. Como usar este documento

- **Leia antes de qualquer tarefa de evolução.** É a fonte única do *o quê* e
  do *por quê*. O *como* continua nas docs técnicas (`architecture.md`,
  `business-rules.md`, `decisions.md`) e no `context.md` (estado vivo).
- **Convenção de status** por item: `⬜` não iniciado · `🟡` em andamento ·
  `✅` entregue · `⛔` descartado (com motivo).
- Ao fechar um item: atualize a tabela de status (§8) e registre a entrega no
  `docs/context.md` (Estado atual + Próximo passo imediato).
- Regras de trabalho: branch nova por unidade de trabalho, commits convencionais,
  PR aberto manualmente pelo dono, docs vivas (ver §9).

---

## 1. Visão e objetivo

A EJ precisa **prospectar melhor e vender mais** com custo controlado. Apollo e
similares cobram mensalidade por assento/crédito — inviável. Este sistema é o
"Apollo próprio": coleta multi-fonte, qualificação contextual com IA explicável,
outreach personalizado com cadência, WhatsApp, e BI para a diretoria.

### Públicos do sistema (modelo da EJ)

| Quem | Papel no app | O que faz |
|---|---|---|
| **Diretores** (owner/admin) | Gestão total + BI | Gerenciam org, membros, convites, chaves e configurações; veem tudo e analisam resultados |
| **Analistas** (ANALYST) | Prospecção + análise | Prospectam/analisam dados, veem BI completo, exportam PDF; não administram a org |
| **Consultores** (CONSULTOR) | Vendas (funil) | Prospectam **de forma independente**: criam/gerenciam campanhas próprias, trabalham o próprio funil no kanban, atribuem-se leads |
| **Supervisor/Gestor** (MANAGER) | Supervisão | Tudo do analista + visão da equipe (desempenho por consultor, metas, reatribuição) |

### Norte do produto

```
Membro da EJ descreve a oferta/ICP → campanha (Places/CSV/CNAE)
        ↓
Coleta → enriquecimento adaptativo (site? CNPJ? contatos?)
        ↓
Score contextual explicável → prioridade HOT/WARM/COLD
        ↓
Consultor trabalha o funil (kanban) → mensagens IA → cadência 0/3/7/14
        ↓
WhatsApp + e-mail (humano no loop) → resposta/reunião/proposta
        ↓
Resultado real (ganhou/perdeu) → BI por analista/gestor → PDF p/ diretoria
        ↓
Feedback converte-se em calibração do próximo ciclo
```

---

## 2. Estado atual — o que já está pronto (base sólida)

Síntese do que já funciona e deve ser **preservado**:

- **Coleta multi-fonte**: Google Places (`places_service.py`), CSV
  (`csv_import_service.py`) e CNAE/Receita (`cnae_discovery_service.py`), com
  dedupe por org (`place_id`/CNPJ/`normalized_domain`).
- **Enriquecimento adaptativo** (`enrichment_orchestrator.py`): escolhe steps
  conforme flags do template; análise técnica **passiva** (Lei 12.737/2012).
- **Scoring contextual** (`scoring_service.py`): templates + router
  (exact→fuzzy→LLM→geração), score 0-100, `priority` HOT/WARM/COLD,
  `evidence[]`, `pitch_angle`, `executive_summary`.
- **Outreach personalizado** (`outreach_service.py`): sequência 0/3/7/14,
  copywriter anti-IA, CTA concreto, rodapé com opt-out (STOP); geração de WhatsApp.
- **Cadência + envio** (`cadence_service.py`/`email_service.py`): humano no
  loop (default) ou `auto_send_email` (opt-in), bounce handling, supressão,
  threading, inbound de resposta/STOP.
- **Multi-tenant completo** (§3): orgs, papéis, convites, isolamento, BYOK.
- **BI + PDF** (`analytics_service.py`, `pdf_report_service.py`): 6 endpoints,
  relatórios `/relatorios`, export PDF, mapa Leaflet, kanban, trilha de
  atividades, conversão por faixa de score.
- **Frontend** Next.js 16: dashboard, campanhas, oportunidades, vendas,
  relatórios, configurações — com temas, roles e CSP.
- **LinkedIn passivo** (`contact_enrichment_service.py`): busca "nome+empresa
  linkedin" (DuckDuckGo→Bing), heurística validada por índice, `linkedin_confidence`;
  sem API oficial (SNAP fechada para novos parceiros) — o resto da evolução
  LinkedIn está no backlog (itens 4.26–4.27).

> **Não mexer (regra preservada):** o **CONSULTOR cria e gerencia campanhas
> próprias** — é autônomo para prospectar o que e onde decidir. Qualquer
> melhoria de papel **não** pode restringir isso.

---

## 3. Modelo multi-org, papéis e convites — diagnóstico

### 3.1 O que JÁ está contemplado e funciona ✅

Validado no código:

| Capacidade | Onde | Status |
|---|---|---|
| Org pessoal criada automaticamente no registro | `org_service.create_personal_organization` | ✅ |
| Org switcher (lista todas as orgs do usuário) | `GET /orgs/my-organizations` + componente `OrgSwitcher` | ✅ |
| Convites por e-mail com token + expiração + revogação | `routes/invites.py` + `invite_service.py` + `/aceitar-convite` | ✅ |
| Convite já define papel administrativo E papel de venda | `CreateInviteRequest` (role + sales_role) | ✅ |
| Papéis administrativos owner/admin/member | `OrganizationRole` | ✅ |
| Papéis de venda CONSULTOR/ANALYST/MANAGER **por org** | `SalesRole` em `organization_members` | ✅ |
| Isolamento cross-tenant (lendo/mutando só dados da org, 404 para outra org) | `get_user_organization` nas rotas | ✅ |
| CONSULTOR vê só leads próprios + não atribuídos (auto-atribuição) | `consultant_lead_scope` em `leads.py` | ✅ |
| ANALYST/MANAGER/owner veem todos os leads | `is_full_access` | ✅ |
| BI e export PDF ANALYST/MANAGER/owner only (CONSULTOR → 403) | `require_analyst()` em `routes/analytics.py` | ✅ |
| Listar membros (MANAGER+) e definir papel de venda (owner/admin) | `routes/orgs.py` | ✅ |
| Chaves BYOK por org (criptografadas, sem expor valor) | `routes/orgs.py` + `secret_service.py` | ✅ |
| `auto_send_email` e `email_from` por org | `PATCH /orgs/{id}` | ✅ |
| Menu e rotas do frontend por papel (sidebar esconde Relatórios p/ CONSULTOR) | `sidebar.tsx` + middleware | ✅ |

### 3.2 A matriz de acesso desejada (modelo alvo da EJ)

| Capacidade | CONSULTOR | ANALYST | MANAGER | owner/admin |
|---|---|---|---|---|
| Criar/gerenciar campanhas próprias | ✅ **mantido** | ✅ | ✅ | ✅ |
| Trabalhar o funil (kanban, contato, reunião, proposta, conversão) | ✅ (próprios + não atribuídos) | ✅ (todos) | ✅ (todos) | ✅ (todos) |
| Ver leads de outros consultores | ❌ | ✅ | ✅ | ✅ |
| Atribuir leads a outros consultores | ❌ (só auto-atribuir) | ❌ | ✅ | ✅ |
| BI / relatórios / export PDF | ❌ | ✅ | ✅ | ✅ |
| Ver desempenho por consultor | ❌ | ✅ | ✅ | ✅ |
| Gerir membros / definir papel de venda | ❌ | ❌ | ver §3.3.5 | ✅ |
| Criar convites / revogar | ❌ | ❌ | ❌ | ✅ |
| Chaves BYOK / configurações da org | ❌ | ❌ | ❌ | ✅ |
| Metas de venda por consultor (a criar, §4.6) | — (vê a própria) | ✅ | ✅ | ✅ |

### 3.3 Gaps do modelo atual (o que falta para a EJ)

#### 3.3.1 Criar e renomear organização — não existe ✅ (P0)

**Problema:** só existe a org pessoal do registro (`create_personal_organization`);
o `PATCH /orgs/{id}` só altera `auto_send_email`. Não dá para criar um workspace
dedicado "AlphaMec" nem renomear o existente.

**Proposta:**
- `POST /api/orgs` — cria nova organização com o usuário logado como OWNER
  (nome, slug único, opcionalmente `email_from`). No frontend, botão
  "Criar organização" no org switcher/Configurações.
- `PATCH /api/orgs/{id}/name` (owner/admin) — renomear.
- Fluxo de onboarding EJ: diretor registra → **cria org "AlphaMek"** → convida
  analistas/consultores (§3.3.2).

**Aceite:** usuário consegue criar org "AlphaMek" via UI; diretor é OWNER;
org aparece no switcher; nome editável.

**Status — Entregue (2026-08-06, `feat/org-onboarding`):** `POST /orgs` (cria com
OWNER + sales_role MANAGER); `PATCH /orgs/{id}/name` (owner/admin); UI no
`OrgSwitcher` ("Criar organização") e card em `/configuracoes` (renomear).

#### 3.3.2 Onboarding por convite para quem ainda não tem conta ✅ (P0)

**Problema:** `accept_invite` exige **usuário autenticado** com o e-mail do
convite (`get_current_user`). Um membro novo da EJ precisa primeiro se registrar
e só depois aceitar o token — fricção real para embarcar a equipe inteira.

**Proposta:**
- Página pública de aceite `/aceitar-convite` que detecta se o e-mail do convite
  já tem conta: **se sim** → pede login → aceita; **se não** → formulário de
  cadastro pré-preenchido (nome, senha) que cria a conta e **aceita o convite no
  mesmo fluxo** (token no payload).
- Endpoint novo ou flag em `accept_invite` para permitir `user=None` quando vier
  token + dados de registro.

**Aceite:** convidado novo faz 1 cadastro e já cai dentro da org AlphaMec.

**Status — Entregue (2026-08-06, `feat/org-onboarding`):**
- `GET /invites/check?token=` (público) informa email, org, se há conta;
- `POST /invites/accept-register` cria a conta + aceita o convite em 1 passo e
  devolve um JWT para auto-login;
- página `/aceitar-convite` decide login (conta existe) vs cadastro (não existe).

#### 3.3.3 Remoção de membro / saída da org / transferência de ownership ✅ (P1)

**Problema:** não há como remover um membro, sair da org, transferir ownership
nem fazer offboarding. Para uma organização real isso é essencial (rotatividade
de EJ é alta).

**Proposta:**
- `DELETE /api/orgs/{org_id}/members/{user_id}` (owner/admin): desativa o membro
  e **reassign** os leads atribuídos a ele (para pool `assigned_to_id=NULL` ou
  para outro consultor escolhido).
- `POST /api/orgs/{org_id}/transfer-owner` (owner): passa o OWNER para outro
  membro admin.
- `POST /api/orgs/{org_id}/leave` (qualquer membro não-owner): sai da org.
- No frontend: opções na tela de membros / configurações da org.

**Aceite:** remover consultor desatribui leads automaticamente; sair da org
funciona; ownership transferível.

#### 3.3.4 Auditoria de membros e acessos ✅ (P2)

**Proposta:** registrar em `lead_activities` (ou tabela `org_audit_log`) eventos
administrativos: convite criado/aceito/revogado, papel alterado, membro removido,
chave BYOK alterada. Dá rastreabilidade para a diretoria e conformidade.

**Status — Entregue (2026-08-14):**
- **Backend (`feat/org-audit-backend`):** tabela nova `org_audit_log` + enum
  `OrgAuditEvent` (14 eventos: ORG_*, MEMBER_*, INVITE_*, SECRET_*,
  SALES_TARGET_*) — migration `bff05fb7eb01`; `org_audit_service.py`
  (`log_org_event` com actor denormalizado + `list_org_audit`, **nunca grava
  valor de secret** — só `key_name`); instrumentado em `orgs.py` e `invites.py`;
  `GET /orgs/{org_id}/audit-log?event=&limit=` (MANAGER/owner/admin). Testes:
  `tests/test_org_audit.py` (7).
- **Frontend (`feat/org-audit-ui`):** tabela "Auditoria de acessos" em
  `/configuracoes/membros` (filtro por evento, Quando/Evento/Quem/Detalhe,
  labels PT-BR, badge por categoria) + `orgsApi.listAuditLog`/`useOrgAuditLog`/
  tipos `OrgAuditEvent`/`OrgAuditEntry`.
- **Acesso (2026-08-14, `feat/linkedin-match-semantico`):** a página
  `/configuracoes/membros` passou a aceitar **MANAGER** — a tabela de auditoria
  fica visível para MANAGER/owner/admin (decisão fechada, ver §3.3.5).

#### 3.3.5 Papel de venda para "gestor da equipe" ✅ (decisão fechada 2026-08-14)

`MANAGER` já vê todos os leads e o BI de consultores. Decisão:
- **(a)** MANAGER agora pode **definir o `sales_role`** dos membros (`PATCH
  /members/{user_id}` aceita MANAGER+, além de owner/admin) — cabe ao gestor
  montar a equipe. Convites, remoção, transferência de ownership, chaves BYOK e
  metas de venda **continuam owner/admin-only**.
- **(b)** Metas de venda (§4.9): listagem MANAGER+/owner, gravação owner/admin
  — mantido o status atual.

**Regra preservada:** o CONSULTOR continua autônomo (cria/gerencia campanhas) —
nada desta decisão restringe isso.

---

## 4. Pilares de melhoria

Priorizados por impacto no objetivo de **vender mais** e custo para a EJ.

### P0 — Entrega 1 · Entregabilidade de e-mail (o coração do cold outreach)

O maior fator entre "campanha que responde" e "campanha que vai pro spam".

#### 4.1 Verificação de e-mail antes do envio ✅ (M, gratuito)

- **Hoje:** `contact_enrichment_service.is_valid_email_syntax` valida só a forma.
  E-mails heurísticos (`nome.sobrenome@dominio`) são palpites; bounce queima a
  reputação do domínio e derruba os próximos envios.
- **Proposta:** validação passiva e gratuita via DNS (ex.: `dnspython`, async):
  1. **MX** do domínio existe (endereço entregável).
  2. Domínio **catch-all** (aceita tudo — não dá para confiar no padrão).
  3. Blocklist de domínios descartáveis (mailinator etc.).
  4. Gravar `Contact.email_verified` (bool) + motivo; UI com badge "verificado".
- **Gate:** envio automático só de e-mail verificado; humano pode enviar
  não-verificado com aviso.
- **Aceite:** taxa de bounce cai; badge de verificado aparece na aba Contatos;
  cadência bloqueia não-verificado no automático.
- **Status — Entregue (2026-08-04, `feat/email-verification`):**
  - Novo `EmailVerificationService` (`email_verification_service.py`) — MX via
    **Cloudflare DoH** (sem dependência nova), blocklist de domínios
    descartáveis e sintaxe; **fail-closed** (incerteza = não verificado).
  - Migration `c7d8e9f0a1b2`: `contacts.email_verified` + `email_verified_at`.
  - Enriquecimento roda a verificação; e-mail **heurístico nunca é marcado
    verificado** (padrão não comprovado). Badge "E-mail verificado" na aba
    Contatos; `email_mx`/`email_verify_reason` em `raw_data` (auditoria).
  - Cadência: envio **automático** só de `email_verified=True`.
  - ⚠️ **Catch-all não implementado (decisão de produto):** detectar catch-all
    exige probe SMTP (`RCPT TO`), ação não-passiva proibida pela política
    (Lei 12.737). Fica como item futuro caso a EJ decida explicitamente.

#### 4.2 Rastreamento de abertura e clique ✅ (M, gratuito)

- **Hoje:** só existe inbound de resposta/STOP. Não se sabe quem leu — o sinal
  mais quente de vendas.
- **Proposta:**
  - Pixel 1×1 por e-mail/etapa: `GET /t/{msg_id}/{step}` → grava `opened_at` em
    `Message` (e serve um GIF 1px).
  - Links rastreados: envolver URLs com `GET /c/{msg_id}/{idx}?url=` → redireciona
    e grava `clicked_at`.
  - `send_email` injeta pixel + reescreve links no HTML e no texto.
  - UI: ícone "abriu/leu" no lead/kanban + filtro `opened=true`; alimenta o
    "quem está quente" do `today-actions`.
- **Aceite:** após uma rodada de envio, o consultor vê quais leads abriram e em
  quais links clicaram; pode priorizar follow-up por isso.
- **Status — Entregue (2026-08-05, `feat/email-tracking`):** pixel 1×1 em
  `GET /t/{token}` (grava `opened_at`) + redirect `GET /c/{token}?url=`
  (grava `clicked_at`); `email_service` injeta pixel/links quando
  `TRACKING_BASE_URL` configurada; `FollowUp`/`Message` carregam
  `tracking_token`; badges "abriu"/"clicou" no `CadencePanel`.

#### 4.3 Warmup, throttling e remetente dedicado ✅ (M, gratuito)

- **Hoje:** `run_due` envia todos os vencidos de uma vez por poll de 60s; SMTP
  usa `from_email` da org (`organizations.email_from`).
- **Proposta:**
  - **Limite diário por remetente** (org): configurável (default p.ex. 40/dia),
    respeitado no `run_due` — espalha os envios no dia, não todos de uma vez.
  - **Espalhamento horário** aleatório dentro de janelas (ex.: 9h-17h).
  - **Checklist de aquecimento** documentado + painel: domínio dedicado
    (`@alpha...com.br`), SPF/DKIM/DMARC, aquecimento progressivo nas 2 semanas
    iniciais (p.ex. 5→10→20→40), alternativa a provedores (Brevo/Resend/Zoho têm
    tier gratuito ou custo irrisório e já cuidam de DKIM).
  - **Personalização de remetente por consultor** (cada consultor envia do
    próprio e-mail da org) para preservar reputação individual.
- **Status — Entregue (2026-08-06, `feat/cadence-warmup-throttle`):**
  - `organizations.daily_email_limit` (default 40) + `send_window_start/end`
    (default 09:00–17:00) e `organization_members.email_from` (remetente por
    consultor) — migration `f4a5b6c7d8e9`.
  - `cadence_service.run_due` respeita teto diário, janela (fuso do servidor) e
    teto por hora; etapas excedentes ficam `PENDING` (postergadas, nunca falham).
  - Remetente em ordem: consultor → org → global.
  - Painel em `/configuracoes` (owner/admin): badge "Envios hoje X/limite Y",
    limite diário, janela e remetente da org.
  - Guia de aquecimento no `README.md`.

#### 4.4 Correção do threading de follow-ups ✅ (S, gratuito)

- **Hoje:** `_thread_headers` em `cadence_service` referencia só o último
  `Message-ID`; Gmail conversa perfeitamente exige a **cadeia** de References.
- **Proposta:** acumular todos os Message-IDs anteriores em `References`
  (`refs + [novo]`), `In-Reply-To` do último.
- **Status — Entregue (2026-08-05, `fix/threading-chain`):**
  `_thread_headers` em `cadence_service.py` acumula a cadeia completa em
  `References` e usa o Message-ID mais recente em `In-Reply-To` (exigência do
  Gmail/Exchange para agrupar a conversa). Teste `tests/test_cadence_threading.py`.

---

### P1 — Entrega 2 · WhatsApp (canal que fecha venda no Brasil)

#### 4.5 Número validado + fluxo de 1 clique ✅ (M, custo baixo)

- **Hoje:** só `wa.me` manual com `whatsapp_short` preenchido.
- **Proposta:**
  - **Validação se o número é WhatsApp** via gateway barato (WhatsApp Business
    Cloud API oficial — tem faixa gratuita — ou utalk/GETI) → grava
    `Contact.phone_verified` + badge no lead.
  - **Card "Próxima ação"** no kanban/lead: botão abre `wa.me` com a mensagem da
    campanha já preenchida (nome do decisor + 1 fato + 1 CTA) — literalmente 1
    clique para o consultor.
  - **Registrar envio** de WhatsApp na trilha (`MessageChannel.WHATSAPP`) para
    contabilizar no funil e nos relatórios.
- **Nota:** manter **humano no loop** (disparo automático em massa = risco de ban
  e péssimo para a imagem). Se a EJ decidir automatizar volume, avaliar gateway
  com envio de baixo volume e follow-up de decisores que já abriram e-mail.
- **Aceite:** consultor vê "número verificado", abre WhatsApp preenchido em 1
  clique e o envio fica na trilha/BI.
- **Status — Entregue (2026-08-10, `feat/whatsapp-one-click`):**
  `POST /leads/{id}/whatsapp-click` valida número móvel BR, formata `wa.me`,
  atualiza `last_contacted_at` e grava a action `WHATSAPP_SENT` na trilha
  (migration `02a4353c47a7`); botões de 1 clique no kanban e no detalhe do lead
  abrem o WhatsApp com a mensagem pré-preenchida.

---

### P1 — Entrega 3 · Dados de coleta = sinal de venda

#### 4.6 Rating, reviews e dados do Google Maps no scoring ✅ (S, gratuito)

- **Hoje:** `FIELD_MASK` de `places_service` não pede `rating`,
  `userRatingCount`, `openingHours`. Perde-se a **dor mais óbvia** de um lead
  (negócio avaliado mal/isolado).
- **Proposta:**
  - Adicionar ao `FIELD_MASK`: `rating`, `userRatingCount`, `openingHours`,
    `googleMapsUri`.
  - Persistir em `leads` (ou `enrichments`) e expor como **evidência no scoring**
    ("Reputação online negativa — 3.2★ com 11 avaliações") e no pitch one-pager.
  - **Diferencial vs Apollo:** Apollo não lê o Google brasileiro; para EJ de
    serviços (lanchonetes, academias, lojas) avaliação ruim = oportunidade.
- **Aceite:** leads com nota baixa aparecem como oportunidade; evidência no
  detalhe/pitch/PDF.
- **Status — Entregue (2026-08-05, `feat/places-rating-scoring`):**
  `places_service` coleta `rating`/`userRatingCount`/`googleMapsUri`; campos em
  `leads` (migration `d8e9f0a2b3c4`); vira evidência "Reputação Google:
  X.Y★ com N avaliações" no scoring e exposto no pitch/summary do lead. Teste
  `tests/test_places_rating.py`.

#### 4.7 Mais fontes de contato além da Receita ✅ (M, gratuito)

- **Hoje:** decisores vêm de Receita (nome dos sócios) + Hunter (opcional) +
  heurística. Hit-rate de e-mail limitado.
- **Proposta (tudo passivo):**
  - **Página de contato do site** da empresa (scrape passivo): e-mails/telefones
    públicos → alta veracidade.
  - **Busca de "nome + empresa + email"** em buscadores (padrão já usado para
    LinkedIn) para achar e-mails públicos.
  - **CNPJ enriquecido** (sócios com CPF já mascarado) + `phone` da empresa.
  - Consolidar e marcar proveniência (`email_source`) — alimenta o 4.1.
- **Aceite:** proporção de leads com e-mail verificado sobe.
- **Entregue (2026-08-10, branch `feat/contact-more-sources`):**
  - `ContactEnrichmentService` ganha `_emails_from_site` (home + `/contato`,
    `/fale-conosco`, `/contact` — extração passiva de e-mail/telefone com
    de-ofuscação anti-bot) e `_mail_to_company` (busca passiva
    `"<nome>" "<empresa>" email` via DuckDuckGo/Bing).
  - Precedência de e-mail: Hunter → **site** → **busca** → **CNPJ** → heurística;
    proveniência em `email_source`/`phone_source` no `raw_data` do contato.
  - `_contacts_from_receita` passa a usar o e-mail/telefone cadastral da empresa
    (`company_email`/`company_phone` da Receita) como fonte extra.
  - Frontend: badge "Fonte: ..." na aba Contatos do lead.
  - Testes: `tests/test_contact_site_sources.py` (15).

---

### P1 — Entrega 4 · Gestão comercial (o que a diretoria cobra)

#### 4.8 Valor por oportunidade + forecast ponderado ✅ (M, gratuito)

- **Hoje:** conversão tem `contract_value`, mas não há valor por estágio nem
  previsão de receita.
- **Proposta:**
  - `Lead.value` (estimativa de ticket) + `Lead.expected_close_date` +
    `lost_reason` (motivo de perda: preço, prazo, não respondeu, outro).
  - **Forecast ponderado** no BI: soma de `value × win-rate do estágio`
    (estágio → probabilidade) por consultor/campanha; gráfico no `/relatorios` e
    no PDF executivo.
  - Filtro "receita projetada vs realizada" no período.
- **Aceite:** diretor abre o PDF e vê receita projetada por estágio/consultor.
- **Status — Entregue (2026-08-10, `feat/opportunity-forecast`):** migration
  `69f0f84a9739` (`lead.value`, `expected_close_date`, `lost_reason`);
  `AnalyticsService.forecast()` (pipeline_value, forecast ponderado 5%–90%,
  receita realizada, motivos de perda) + `GET /analytics/forecast`;
  `PATCH /leads/{id}` aceita os 3 campos; card de ticket/previsão/motivo no lead
  e `ForecastCard` em `/relatorios`.

#### 4.9 Metas de vendas por consultor ✅ (M, gratuito)

- **Proposta:**
  - Tabela `sales_targets` (org, consultor, mês, meta_reuniões, meta_receita).
  - `/analytics/consultants` retorna **atingimento** (realizado/meta) e ranking.
  - UI: badge de atingimento na página de relatórios e na tela de membros.
- **Aceite:** gestor vê "cada consultor está indo bem/atrasado" com número.
- **Status — Entregue (2026-08-10, `feat/sales-targets`):** migration
  `b613230fd8fd` cria `sales_targets`; `AnalyticsService.consultants()` devolve
  `revenue_realized`, `meetings_target/revenue_target` e atingimento (%); CRUD
  em `routes/orgs.py`; `SalesTargetsManager` em `/configuracoes/membros` e badges
  de atingimento no `ConsultantsCard` de `/relatorios`.

#### 4.10 SLA e lembretes para leads parados ✅ (M, gratuito)

- **Proposta:** regras configuráveis por org (ex.: QUALIFICADO sem contato há 5
  dias → alerta; RESPONDIDO sem próximo passo em 2 dias → lembrete; lead que
  **abriu** e não respondeu em 2 dias → nudge). Alimenta `today-actions` e
  notificação no kanban.
- **Aceite:** leads quentes nunca ficam esquecidos; painel "ações de hoje"
  reflete as regras.
- **Entregue (2026-08-10, branch `feat/sla-lead-reminders`; kanban 2026-08-11):** colunas
  de SLA por org (`sla_qualified_no_contact_days`, `sla_responded_no_next_action_days`,
  `sla_opened_no_response_days`); serviço `sla_service` + `GET /api/leads/sla-alerts`;
  card de configuração em `/configuracoes` e seção no painel "Ações de hoje".
  **Notificação no kanban** (parte do "alimenta today-actions **e** notificação no
  kanban"): chip resumo "N leads parados (SLA)", contador vermelho por coluna e badge
  "SLA há Xd" nos cartões (tooltip com a regra). Testes: `tests/test_sla_service.py` (8).

#### 4.11 Gráfico de funil ponta-a-ponta (leads → fechamento) ✅ (P1, S, gratuito)

- **Pedido da diretoria:** ver visualmente de quantos **leads achados** partimos,
  quantos foram **prospectados** (1º contato), quantos **responderam**, quantos
  marcaram **reunião diagnóstica** e quantos, de fato, **fecharam negócio** — por
  campanha/período/consultor.
- **Fontes no sistema:** funil atual (`GET /analytics/overview`), cadência
  (`FollowUp.sent_at`), resposta (`Message.is_response`/`Lead.status=RESPONDIDO`),
  reunião (`Lead.status=REUNIAO_MARCADA`), fechamento (`Conversion`).
- **Aceite:** gráfico de funil (nº absoluto + % de conversão entre etapas) no
  `/relatorios` e no PDF executivo — a diretoria enxerga onde o funil afina/vaza.
- **Status — Entregue (2026-08-12, `feat/funnel-end-to-end`):** cada etapa é
  **cumulativa** ("pelo menos"): além do status atual, conta eventos reais
  (`FollowUp.sent_at`/`Message.sent_at` p/ prospectado, `Message.is_response` p/
  resposta, `LeadActivity` STATUS_CHANGED→REUNIAO_MARCADA/MEETING_SCHEDULED p/
  reunião e `Conversion` p/ fechado) — leads que já saíram do funil (ex.:
  `PERDIDO`) não somem das etapas por onde passaram. `AnalyticsService.funnel()`
  + `GET /api/analytics/funnel` (filtros `from/to/campaign_id/consultant_id`);
  card **"Funil ponta-a-ponta"** em `/relatorios` (barras que afunilam + %
  de conversão entre etapas e "vazou X%"); seção homônima no **PDF executivo**.
  Testes: `tests/test_analytics_funnel.py` (6) — suíte em **140 passed**.

---

---

### P2 — Entrega 6 · Confiabilidade para produção real

#### 4.14 Medidor de cotas por org + alertas ✅ (M, gratuito)

- **Hoje:** BYOK existe, mas **sem contador de uso** (Places ~100/mês, Groq).
- **Proposta:** contador diário por org/key em `provider_client`; alerta no
  dashboard ao passar 80%; travar chamadas excedentes (fallback/aviso).
- **Aceite:** custo nunca estoura sem aviso; org vê consumo na UI.
- **Status — Entregue (2026-08-11, `feat/p2-confiabilidade` — PR #68):**
  `QuotaService`/`provider_usage` no workers (medidor diário por org/provedor +
  guard em Groq/Places); API: endpoint de uso + `PATCH api_quota` +
  guard/consume nas rotas de IA; web: card de cotas da org em `/configuracoes`
  (consumo Google/Groq, badge "Configurada"/"Pool global").

#### 4.15 Observabilidade e restauração ✅ (M, gratuito)

- **Proposta:** logs estruturados dos eventos de cadência/abertura; **teste real
  de restore** do `pg_dump` quinzenal; `pytest` com 1 E2E do ciclo completo de
  outreach (agendar→verificar→enviar→abrir→responder/STOP); Sentry se aplicável.
- **Aceite:** backup é comprovadamente restaurável; ciclo completo tem teste.
- **Status — Entregue (2026-08-11, `feat/p2-confiabilidade` — PR #68):**
  logs estruturados dos eventos de cadência/abertura; teste real de restore do
  `pg_dump`; pytest E2E do ciclo completo de outreach
  (agendar→verificar→enviar→abrir→responder/STOP).

#### 4.16 Paginação e performance das listas ✅ (M, gratuito)

- **Proposta:** paginação server-side nas listas de leads/kanban (hoje em
  memória), índice composto `(organization_id, status, qualification_score)`,
  debounce já feito na busca.
- **Aceite:** listas de milhares de leads sem travar a UI.
- **Status — Entregue (2026-08-11, `feat/p2-confiabilidade` — PR #68):**
  paginação server-side no kanban e na lista de leads + índices compostos
  `(organization_id, status, qualification_score)` (migration `ca2c1a...`).

#### 4.17 Frontend mobile-first 🟡 entregue no branch (M, gratuito)

- **Proposta:** revisar kanban/tabelas/mapas para o celular (consultor trabalha
  no WhatsApp no celular; EJ tem rotatividade e quem trabalha em campo).
- **Aceite:** principais fluxos (ver leads, abrir WhatsApp, mudar status)
  utilizáveis no celular.
- **Status — portado p/ `main` (2026-08-14, `feat/mobile-first-4-17`):**
  - Sistema: `DialogContent` com `max-h-[calc(100dvh-2rem)]` + `overflow-y-auto`
    (conteúdo longo não estoura a tela); `TabsList` com `w-max`/`mx-auto`/
    `justify-start` (scroll lateral sem cortar o início).
  - Kanban `/vendas`: touch targets 44px (WhatsApp, atribuir, "Atribuir a mim")
    via `sm:`; rodapé do card com `flex-wrap`; dica mobile "toque no cartão
    para atualizar o status".
  - Lista de leads: presets/ações em massa com alvo de toque maior; badges do
    card quebram linha em 320px.
  - Detalhe do lead: análise do site em 1 coluna no mobile; ações do header com
    `flex-wrap`.
  - Campanhas: header e linhas de leads responsivos; lista com header wrap.
  - Mapa (`/relatorios`): altura responsiva (`h-[300px] sm:h-[440px]`).
  - Verificação: `npm run lint`, `npx tsc --noEmit` e `npm run build` limpos.
  - **Pendente (próximo ciclo):** bottom-nav opcional, refinamento de DnD em
    touchscreen e validação em device real.

---

### LinkedIn — descobrir, validar e enriquecer decisores e empresas (sem API oficial)

> Origem: antiga `docs/especificacao-integracao-prospeccao-linkedin.md` (arquivada
> no roadmap). A spec deixa explícito que **não há API pública de pesquisa** —
> Sales Navigator exige o programa SNAP e o LinkedIn não aceita novos parceiros
> hoje (§34). Portanto a arquitetura é toda **passiva + pesquisa assistida
> (humano no loop)**: nada de scraping nem automação de navegador (§20/§25/§35).
>
> O que **já está contemplado**: busca passiva "nome + empresa + linkedin"
> (DuckDuckGo → Bing), heurística de URL validada por índice de busca (candidato
> ≠ confirmado), `linkedin_confidence`, múltiplos decisores por lead com
> `is_primary` (prioridade CEO/Diretor/Sócio), score comercial configurável por
> campanha e explicabilidade (evidence/pitch one-pager).

#### 4.22 Pesquisa assistida + associação manual de perfil ✅ (P1, M, gratuito)

- **Hoje:** sem API oficial, quando a busca passiva não acha o decisor não há
  caminho — o consultor não consegue gerar a consulta certa nem colar a URL de
  um perfil que encontrou manualmente.
- **Proposta:**
  - `GET /leads/{id}/linkedin-query` — consultas sugeridas (`"<empresa>"`
    founder/sócio/diretor/head/psicólogo… lista default, sobrescrevível pelo
    template) + atalho de busca externa `site:linkedin.com/in`.
  - `PATCH /leads/{id}/contacts/{contact_id}/linkedin` — valida a URL colada
    (formato + existência passiva no índice de busca), grava
    `linkedin_source="manual:<user>"` e `linkedin_confidence` (validado/revisão)
    + atividade na trilha.
- **Aceite:** todo lead sem decisor tem um fluxo guiado "copiar consulta →
  abrir no LinkedIn → colar o perfil → salvar validado".
- **Entregue (2026-08-11, `feat/linkedin-assistido-lgpd-cleanup`):** backend
  (`linkedin-query` + `PATCH .../linkedin`, serviço `linkedin_assist_service`,
  action nova `LINKEDIN_ASSOCIATED` na trilha) + frontend (Dialog guiado na aba
  Contatos: consultas copiáveis, busca externa, colar URL e "Validar e salvar";
  badge "Associado manualmente"). Testes: `tests/test_linkedin_assist.py` (8).

#### 4.23 LinkedIn da empresa (company page) ✅ (P2, S, gratuito)

- **Hoje:** só o LinkedIn da pessoa; a **página da empresa** (`/company/<slug>`)
  não é descoberta nem exibida.
- **Proposta:** no enriquecimento, busca passiva `"<empresa>" linkedin` →
  `linkedin.com/company/<slug>` gravando `leads.company_linkedin_url`
  (migration) + proveniência; exibir "Empresa no LinkedIn" na página do lead e
  no pitch.
- **Aceite:** a empresa prospectada tem a página da empresa localizada e
  clicável (valida o alvo além do decisor).
- **Entregue (2026-08-14, `feat/linkedin-empresa`):**
  - Migration `d4e5f6a7b8c9` — `leads.company_linkedin_url` (String 255).
  - `ContactEnrichmentService`: busca passiva `"<empresa>" linkedin`
    (DuckDuckGo→Bing) + helpers puros `extract_linkedin_company_slug` e
    `pick_linkedin_company_url` (overlap do slug com o nome da empresa,
    mínimo 1 termo — nunca aceita company page sem relação). Roda uma vez por
    lead no enriquecimento.
  - API: exposto em `_lead_summary` e no `identity` do pitch one-pager.
  - UI: "Empresa no LinkedIn" (link clicável) em "Informações do Lead" e no
    card de Identidade do Pitch One-Pager.
  - Testes `tests/test_linkedin_company.py` (5) — suíte em **204 passed**.

#### 4.24 Match semântico do LinkedIn (status derivado) ✅ (P2, S, gratuito)

- **Hoje:** só `linkedin_confidence` numérico; não há o "encontramos a pessoa
  certa?" como estado separado do score comercial.
- **Proposta:** derivar `linkedin_match_status` = `NOT_FOUND / CANDIDATE /
  NEEDS_REVIEW / VERIFIED` (fonte + confiança + manual) no serializador do
  contato; badge de 4 estados na aba Contatos; nunca exibir como confirmado
  abaixo do limiar.
- **Aceite:** o consultor distingue em 1 clique "perfil certo" de "candidato a
  revisar", sem interpretar número.
- **Entregue (2026-08-14, `feat/linkedin-match-semantico`):**
  - `linkedin_match_status(url, source, confidence)` puro em
    `linkedin_assist_service` — `search:*` → VERIFIED; `manual` com conf ≥ 90 →
    VERIFIED / conf < 90 → NEEDS_REVIEW; `heuristic` → CANDIDATE; sem URL →
    NOT_FOUND; fonte desconhecida usa conf ≥ 90 como limiar.
  - exposto em `_contact_to_dict` (`GET /leads/{id}`); badge semântico na aba
    Contatos (Confirmado / Revisar / Candidato) no lugar do limiar de 50%.
  - Testes `tests/test_linkedin_match_status.py` (6) — suíte em **199 passed**.

#### 4.25 Estado do enriquecimento + TTL ✅ (P2, M, gratuito)

- **Hoje:** `last_contacted_at` existe, mas não há estado/TTL por lead para
  evitar re-pesquisar os mesmos padrões repetidamente.
- **Proposta:** `last_enriched_at`/estado por lead com TTL (candidato LinkedIn
  30d, site 7d, reviews 24h) e depreciação indicada na página do lead.
- **Aceite:** re-enriquecer não refaz busca dentro do TTL (idempotência + cache).
- **Entregue (2026-08-14, `feat/enrichment-ttl`):**
  - Migration `e6f7a8b9c0d1` — `leads.enrichment_timestamps` (JSONB por fonte).
  - `services/enrichment_ts.py` (workers, fonte única): `TTL_HOURS`
    (linkedin 30d · site 7d · reviews 24h), `read_stamps`/`get_stamp`/`stamp`,
    `is_fresh` e `freshness_snapshot`.
  - **Gate real (LinkedIn):** `ContactEnrichmentService` não re-busca
    LinkedIn (pessoa/empresa) dentro de 30d e carimba ao buscar.
  - **Carimbos:** `enrichment_orchestrator` marca `site` após análise técnica
    e `reviews` quando há rating do Google.
  - **API:** `enrichment_freshness` (fresh/stale/never por fonte) no detalhe
    do lead.
  - **UI:** aviso "Dados antigos" (LinkedIn/análise do site/avaliações) em
    "Informações do Lead" quando a fonte passou do TTL.
  - Testes `tests/test_enrichment_ttl.py` (5) — suíte em **209 passed**.

#### 4.26 Sinal de Instagram no ICP/scoring ⬜ (P3, M, gratuito)

- **Hoje:** "Instagram ativo" é um dos sinais mais fortes de dor/oportunidade na
  spec (§13/§27/§31), mas não é coletado.
- **Proposta:** detectar `instagram_url`/atividade (link social no site,
  followers visíveis) → evidência no scoring + fato no pitch.
- **Aceite:** leads com Instagram ativo e sem site sobem de score com
  justificativa.

#### 4.27 Separação Company/Person ⬜ (P3, L, gratuito — decisão de produto)

- **Hoje:** modelo lead-centrado com contatos embutidos; a mesma empresa entre
  leads não é normalizada.
- **Proposta (grande):** modelo de 3 entidades (Company, Person, Employment +
  Lead = oportunidade) com dedupe por LinkedIn-id/e-mail/nome+empresa e
  histórico de emprego.
- **Aceite:** mesma empresa/pessoa reaproveitada entre campanhas sem duplicata.

---

### P3 — Entrega 7 · Aprofundamento (quando a operação crescer)

- **4.18 Ajuste automático de threshold por org** — com volume de conversões,
  calibrar o limiar QUALIFICADO/DESQUALIFICADO por org com base na taxa de
  conversão por faixa (base já existe em `analytics`).
- **4.19 A/B e variação de mensagens** — variações de subject/CTA por rodada e
  medição de resposta por variante.
- **4.20 Integrações externas** — Google Agenda/Cal.com para marcar reunião;
  n8n/webhook genérico para exportar; importação de leads de planilhas
  compartilhadas do Drive.
- **4.21 Playbooks por consultor** — repositório de mensagens que funcionaram por
  vertical, anotado pelo próprio time.

---

## 5. Backlog mestre (tabela única de rastreio)

| # | Item | Pilar | Prio | Esforço | Custo | Depende de | Status |
|---|---|---|---|---|---|---|---|
| 4.1 | Verificação de e-mail (MX/blocklist) + badge | Entregabilidade | P0 | M | gratuito | — | ✅ Entregue 2026-08-04 |
| 4.2 | Rastreamento de abertura/clique (pixel + redirect) | Entregabilidade | P0 | M | gratuito | — | ✅ Entregue 2026-08-05 |
| 4.3 | Warmup, throttling e remetente dedicado | Entregabilidade | P0 | M | gratuito | 4.1 | ✅ Entregue 2026-08-06 |
| 4.4 | Threading completo dos follow-ups | Entregabilidade | P0 | S | gratuito | — | ✅ Entregue 2026-08-05 |
| 3.3.1 | Criar/renomear organização | Multi-org | P0 | S | gratuito | — | ✅ Entregue 2026-08-06 |
| 3.3.2 | Onboarding por convite (cadastro no aceite) | Multi-org | P0 | M | gratuito | 3.3.1 | ✅ Entregue 2026-08-06 |
| 4.5 | WhatsApp: validação + 1 clique + trilha | WhatsApp | P1 | M | baixo | 4.7 | ✅ Entregue 2026-08-10 |
| 4.6 | Rating/reviews do Google no scoring | Dados | P1 | S | gratuito | — | ✅ Entregue 2026-08-05 |
| 4.7 | Mais fontes de contato (site, busca) | Dados | P1 | M | gratuito | 4.1 | ✅ Entregue 2026-08-10 |
| 4.8 | Valor por oportunidade + forecast ponderado | Gestão | P1 | M | gratuito | — | ✅ Entregue 2026-08-10 |
| 4.9 | Metas de vendas por consultor | Gestão | P1 | M | gratuito | 4.8 | ✅ Entregue 2026-08-10 |
| 4.10 | SLA/lembretes p/ leads parados | Gestão | P1 | M | gratuito | 4.2 | ✅ Entregue 2026-08-11 |
| 4.11 | Gráfico de funil ponta-a-ponta (achados→prospectados→responderam→reunião→fecharam) | Gestão | P1 | S | gratuito | 4.8/4.16 | ✅ Entregue 2026-08-12 |
| 3.3.3 | Remover/sair/transferir org | Multi-org | P1 | M | gratuito | 3.3.1 | ✅ Entregue 2026-08-10 |
| 4.14 | Medidor de cotas por org | Confiabilidade | P2 | M | gratuito | — | ✅ Entregue 2026-08-11 |
| 4.15 | Observabilidade + teste de restore | Confiabilidade | P2 | M | gratuito | — | ✅ Entregue 2026-08-11 |
| 4.16 | Paginação/performance das listas | Confiabilidade | P2 | M | gratuito | — | ✅ Entregue 2026-08-11 |
| 4.17 | Frontend mobile-first | Confiabilidade | P2 | M | gratuito | — | 🟡 entregue no branch (2026-08-14) |
| 3.3.4 | Auditoria de membros/acessos | Multi-org | P2 | M | gratuito | 3.3.1 | ✅ Entregue 2026-08-14 |
| 4.18 | Threshold automático por org | Avançado | P3 | M | gratuito | 4.8/4.9 | ⬜ |
| 4.19 | A/B de mensagens | Avançado | P3 | M | gratuito | 4.2 | ⬜ |
| 4.20 | Integrações (Agenda, n8n, Drive) | Avançado | P3 | L | — | — | ⬜ |
| 4.21 | Playbooks por consultor | Avançado | P3 | S | gratuito | — | ⬜ |
| 4.22 | Pesquisa assistida + perfil manual (LinkedIn) | LinkedIn | P1 | M | gratuito | 4.7 | ✅ Entregue 2026-08-11 |
| C5 | Aplicações web/ERP (template seed de categoria) | Dados | P1 | S | gratuito | — | ✅ Entregue 2026-08-14 |
| 4.23 | LinkedIn da empresa (company page) | LinkedIn | P2 | S | gratuito | 4.7 | ✅ Entregue 2026-08-14 |
| 4.24 | Match semântico (linkedin_match_status + badges) | LinkedIn | P2 | S | gratuito | 4.22 | ✅ Entregue 2026-08-14 |
| 4.25 | Estado do enriquecimento + TTL | LinkedIn | P2 | M | gratuito | 4.24 | ✅ Entregue 2026-08-14 |
| 4.26 | Sinal de Instagram no ICP/scoring | LinkedIn | P3 | M | gratuito | 4.6 | ⬜ |
| 4.27 | Separação Company/Person (3 entidades) | LinkedIn | P3 | L | gratuito | — | ⬜ |

**Legenda de esforço:** S < 1 dia · M 1-3 dias · L > 1 semana.

---

## 6. Fases sugeridas (timeline)

> Regra de ouro: **nada de novo antes de fechar a entrega em curso**. Entregar
> em pequenas fatias, cada uma com PR próprio e validação real.

- **Fase 0 — Estabilizar (semanas 1-2):** itens P0 de entregabilidade (4.1, 4.2,
  4.4) + multi-org (3.3.1, 3.3.2). São a base para qualquer campanha real.
  *Critério de saída:* e-mail verificado, tracking funcionando, org AlphaMec
  criada com onboarding por convite.
- **Fase 1 — Vender melhor (semanas 3-5):** 4.5 (WhatsApp), 4.6 (reviews),
  4.7 (fontes), 4.8/4.9 (forecast + metas), 4.10 (SLA).
  *Critério de saída:* consultor fecha 1º ciclo completo com tracking e
  WhatsApp; gestor vê desempenho contra meta.
- **Fase 2 — Conformidade e escala (semanas 6-9):**
  4.14-4.16 (confiabilidade) ✅, 4.17 (mobile-first),
  3.3.4 (auditoria de acessos), 4.22-4.25 (LinkedIn assistido).
  *Critério de saída:* backup restaurável, UI em produção sem travar, decisores
  associados via pesquisa assistida.
- **Fase 3 — Diferenciação (semanas 10+):** 4.18-4.21 (calibração, A/B,
  integrações, playbooks), 4.26-4.27 (Instagram + modelo 3 entidades).

---

## 7. Métricas de sucesso

O software só vale se a EJ vender mais. Definir linha de base antes de cada
rodada e acompanhar por campanha:

| Métrica | Onde ver | Meta referência |
|---|---|---|
| Taxa de **entrega** (não-bounce) | `email_suppressions` / stats | ≥ 95% |
| Taxa de **abertura** | tracking 4.2 | ≥ 40% (cold) |
| Taxa de **resposta** | inbound (RESPONDIDO) | ≥ 8-15% |
| Taxa de **reunião marcada** | funil | ≥ 3-5% |
| Conversão por **faixa de score** | `/analytics/overview` | qualificados convertem > desqualificados |
| **Receita projetada vs realizada** | forecast 4.8 | planejamento confiável |
| **Atingimento de meta** por consultor | 4.9 | ranking semanal |

---

## 8. Definição de pronto (DoD) e rastreio

**Todo item entregue precisa:**
- [ ] Branch própria + commits convencionais + PR revisado
- [ ] Migração (se houver) aplicada de ponta a ponta em Postgres real
- [ ] Teste (pytest ou smoke manual) do caminho feliz + falha
- [ ] `npm run lint` + `npx tsc --noEmit` limpos (se frontend)
- [ ] Docs atualizadas: este arquivo (status), `context.md`, e `architecture.md`
      se mudou arquitetura
- [ ] Nenhuma coluna removida em prod; migrations novas (nunca editar antigas)

**Rastreio:** atualizar a tabela do §5 a cada merge.

---

## 9. Convenções de trabalho (resumo)

1. Branch nova a partir de `main` atualizado: `git checkout -b <tipo>/<slug>`.
2. Commits convencionais: `feat(escopo)`, `fix(escopo)`, `refactor`, `docs`,
   `chore`, `test`.
3. PR aberto manualmente pelo dono do repo (não pelo autor).
4. Docs vivas ao fechar fatia: este arquivo + `context.md` (+ `decisions.md` se
   ADR nova).
5. Nunca commitar `.env`/secrets; perguntar antes de instalar dependências.
6. Tudo async nos serviços (httpx), filtros SQLAlchemy com `&`/`|`, `logging`
   em vez de `print`, config via `settings.py`.
7. **Passivo sempre** (Lei 12.737/2012): nenhuma análise ativa/probe/injeção.

---

> **Preservar sempre:** o CONSULTOR cria e gerencia campanhas próprias e
> prospecta de forma independente — nenhuma evolução pode restringir isso.
> (Decisão explícita da diretoria, 2026-08-04.)

---

## 10. Correções operacionais (2026-08-11) — onde estamos

Sessão de levantamento (branch `feat/theme-alphamec`, pronta para PR + este doc).
Mapa de bugs encontrados e correções: o que já foi feito e o que falta rodar.

### C1 · Selects exibindo valor cru (ex.: `web_presence`, `CONSULTOR`, UUID) ✅
- **Sintoma:** o trigger do Select mostra o valor cru (`web_presence`) em vez do
  rótulo ("Serviços digitais"); as opções aparecem corretas ao abrir.
- **Causa:** o port de `@base-ui/react` do shadcn renderiza o **valor** no
  `Select.Value` (o Radix renderizava o texto do item). Qualquer `Select` com
  `<SelectValue />` sem resolver o rótulo mostrava o enum/UUID.
- **Fix aplicado:** todos os `SelectValue` ganharam `children={(value) => label}`
  (função suportada pelo base-ui). Arquivos: `campanhas/nova` (perfil da
  prospecção), `configuracoes/membros` (papel de venda), `invites-manager`
  (papel admin + venda + lista de convites), `template-selector` (template +
  peso do sinal), `lead-list` (campanha, ordenação, mover). Verificado com
  `npm run lint` + `npx tsc --noEmit` limpos.
- **Atenção futura:** qualquer `Select` novo precisa de rótulo explícito no
  `SelectValue` — não usar `<SelectValue />` solto.

### C2 · Leads presos em `ANALISADO`/score 0 por falha transitória do Groq 🟡
- **Sintoma:** 35 de 45 leads com score 0; todos em `ANALISADO`. Sensação de que
  "só quem tem site recebe score" (o público-alvo **sem** site ficou preso).
- **Causa:** quando a chamada ao Groq falhava (rate-limit/5xx/rede),
  `process_single_lead` marcava `ANALISADO`; os batches só reprocessam `NOVO` —
  os afetados ficavam presos para sempre.
- **Fix aplicado:** `enrichment_orchestrator.py` agora mantém `NOVO` na falha
  (será reprocessado no próximo batch). Verificado: re-run manual pontua 60+.
- **Script `src/scripts/reprocess_stuck_leads.py`** (idempotente, dry-run por
  padrão) **validado** em 2026-08-11 (removido o `def reprocess_one` duplicado).
  Levantamento atual: **53 presos** + **3 com evidência errada de "sem site"** =
  56 leads.
- **PENDENTE — rodar na base real** (base local de teste recém-criada tem 0 leads):
  ```bash
  cd services/workers
  source venv/bin/activate
  python -m src.scripts.reprocess_stuck_leads --apply --fix-site-evidence
  ```

### C3 · Alucinação "sem site próprio" quando o lead TEM site 🟡
- **Sintoma:** ex. **Psicóloga Pâmela Oliveira** (site `psipamelaoliveira.com`,
  WordPress/SSL ok) — a IA gravou evidência "Sem site próprio — dados cadastrais",
  contradizendo os facts `Tem website: sim`.
- **Causa:** o prompt (SYSTEM_PROMPT/instruções) super-enfatizava o caso "sem
  site" e a LLM repetia a alegação como fato.
- **Fix aplicado:** regra no prompt ("presença de site é fato determinístico;
  nunca afirme ausência") + **guard determinístico** `_contradicts_site_state`
  em `scoring_service._normalize_response(has_website=...)` que remove
  evidências contraditórias. Testes: `tests/test_scoring_site_claims.py` (5).
- **PENDENTE:** re-pontuar os afetados (mesmo comando do C2, que já inclui o
  `--fix-site-evidence`).

### C4 · Leads SEM site deveriam pontuar (público-alvo de sites) ✅ entendido
- **Sintoma/entendimento:** leads sem site (ex.: **Psicóloga Jaqueline Pradelli**)
  estavam com 0 — mas por preso no C2, não por decisão. Para quem vende sites, o
  lead **sem** site é o público-alvo (item 4.2: scoring business mesmo em campanha
  web_presence).
- **Ação:** a correção do C2 destrava os presos. Em 2026-08-11 a regra foi
  **reforçada no código** (ver C6): sinal positivo "Sem site próprio" no seed +
  instrução dinâmica no prompt quando a campanha vende presença digital +
  guard `has_website` no `score_business_lead` — lead sem site é pontuado como
  público-alvo (não fica à mercê de interpretação do LLM).

### C6 · Docs sincronizadas + pendências registradas (2026-08-11) ✅
- **PR #70 mergeado (2026-08-11):** setup/dev **Windows sem Docker**
  (`setup.ps1`/`dev.ps1` + launchers `.cmd`), scoring "sem site = público-alvo"
  (C4) e fixes de UI (selects PT-BR, validação de sinais no template).
- **Novo item 4.11 no backlog:** gráfico de funil ponta-a-ponta
  (achados → prospectados → responderam → reunião diagnóstica → fecharam).
- **Regra pendente:** `PERDIDO` volta à fila em 90 dias — **não implementada**
  no código (registrada em `business-rules.md`).

### C7 · Funil ponta-a-ponta 4.11 entregue (2026-08-12) ✅
- Branch `feat/funnel-end-to-end`: `AnalyticsService.funnel()` + endpoint
  `GET /api/analytics/funnel` (filtros `from/to/campaign_id/consultant_id`),
  card "Funil ponta-a-ponta" em `/relatorios` e seção no PDF executivo.
- **Abordagem direcional (cumulativa):** cada etapa conta leads que **chegaram
  até ela** — usa status atual **+ eventos** (`FollowUp.sent_at`,
  `Message.sent_at`/`is_response`, `LeadActivity` → REUNIAO_MARCADA, `Conversion`).
  Assim um lead `PERDIDO` que respondeu e marcou reunião continua contando nas
  etapas que atravessou (coisa que só status atual não mostraria).
- **Pendências que restaram:** C5 (ERP/web apps) aguardando diretoria.

### C8 · Regra `PERDIDO` volta à fila implementada (2026-08-12) ✅
- Branch `feat/perdido-requeue-90d`: job em background (`_lost_requeue_loop` no
  `main.py`, poll `LOST_REQUEUE_POLL_SECONDS` default 1h) re-enfileira
  `PERDIDO → NOVO` após a carência (`LOST_REQUEUE_DAYS`, default 90).
- **Decisão (escopo conservador):** só volta quem foi perdido por **ausência de
  resposta** (`lost_reason` nulo ou `NAO_RESPONDEU`) e **não** é `opt_out`.
  Perdas deliberadas (`PRECO`/`CONCORRENTE`/`PRAZO`/`OUTRO`) **não** reabrem
  automaticamente — re-enfileirar negócio perdido por decisão seria indesejado.
- **Data de perda exata:** última `LeadActivity` com `status_to=PERDIDO`;
  fallback `Lead.updated_at` (leads antigos sem trilha). Mantém o consultor
  atribuído e grava a transição na trilha. `services/requeue_service.py`
  (elegibilidade em Python, função `_is_time_based_loss` — determinística).
- **Verificação:** `tests/test_requeue_lost.py` (14).

### C9 · Auto-`PERDIDO` no encerramento da cadência (2026-08-12) ✅
- Branch `feat/cadence-auto-perdido`: fecha o ciclo do `PERDIDO` ponta-a-ponta —
  o C8 é a **saída** (requeue 90d); este job é a **entrada**: quando o
  **`CLOSING`** (dia 14) foi enviado e o lead não respondeu na carência
  (`CADENCE_CLOSE_GRACE_DAYS`, default 7), ele é marcado `PERDIDO`/`NAO_RESPONDEU`
  em vez de ficar `CONTATADO` para sempre.
- **Guardas:** só transiciona `CONTATADO` (nunca sobrescreve `RESPONDIDO+` /
  reunião / proposta) e **não** marca `opt_out`. Registra trilha
  (STATUS_CHANGED + action `LOST`), que alimenta a data de perda do requeue C8.
- **Implementação:** `_cadence_close_loop` no `main.py` (poll
  `CADENCE_CLOSE_POLL_SECONDS` default 1h) + `services/cadence_close_service.py`
  (`close_expired_cadences`, guardas em Python — determinístico).
- **Verificação:** `tests/test_cadence_close.py` (12). Regra documentada em
  `business-rules.md` (funil + cadência) já atualizada.

### C5 · Suporte a aplicações web completas / ERP ✅ (2026-08-14)

- **Pergunta do usuário:** o sistema "só suporta landing pages"? Para vender
  aplicações web completas ou sistemas ERP a análise precisa ser diferente.
- **Decisão (2026-08-14):** **criar template de categoria** ("Aplicações Web / ERP"),
  conforme recomendação — sem terceiro perfil. O motor já separa perfil (o *que*
  analisar) de template (os *critérios*); ERP/web apps usam o MESMO perfil
  `web_presence` (analisar o site do prospecto), mudando apenas os sinais.
- **Entregue:** seed novo em `scoring_templates.py` — `service_label="Aplicações
  Web / ERP"` (`requires_technical_report=True`): positivos = "Site institucional
  / landing sem função", "Sem área logada / portal do cliente", "Processo manual
  / planilha", "Crescimento sem sistema"; negativos = "Painel / área do cliente
  presente", "Menção a integrações/API", "Portal do aluno/cliente ativo";
  `extra_instructions` com regra anti-desqualificação (processo manual =
  público-alvo, nunca desqualificar por site desatualizado) + playbook de
  outreach. Seed reaplicado (7 templates ativos). Testes
  `tests/test_erp_template_seed.py` (5) — suíte em **181 passed**.
- Router resolve: `aplicações web` casa fuzzy; `ERP`/`sistemas` pela etapa LLM
  (com `GROQ_API_KEY`) ou exact/fuzzy em `target_segment`.

---

## 11. Próximos passos (roadmap)

- **Imediato (pós-merge):** rodar `reprocess_stuck_leads --apply --fix-site-evidence`
  (C2/C3) **na base real** (script validado; base local de teste recém-criada tem
  0 leads) e revalidar a distribuição de scores no `analytics/overview`.
- **Item 4.22 entregue (2026-08-11):** LinkedIn assistido (consultas sugeridas +
  associação manual de perfil com validação passiva) — branch
  `feat/linkedin-assistido-lgpd-cleanup`.
- **Itens 4.14–4.16 entregues (2026-08-11, PR #68):** cotas por org (4.14),
  observabilidade/restore (4.15) e paginação/índices (4.16) — P2 confiabilidade
  fechado.
- **PR #70 mergeado (2026-08-11):** setup/dev **Windows sem Docker** +
  scoring "sem site = público-alvo" (C4/C6) + fixes de UI.
- **Item 4.11 entregue (2026-08-12, `feat/funnel-end-to-end`):** funil
  ponta-a-ponta (achados → prospectados → responderam → reunião diagnóstica →
  fecharam) no `/relatorios` e no PDF executivo — pedido da diretoria.
- **Regra `PERDIDO`/90d implementada (2026-08-12, `feat/perdido-requeue-90d`):**
  job em background re-enfileira `PERDIDO → NOVO` após a carência (perda por
  ausência de resposta e não-`opt_out`; perdas deliberadas não voltam). Ver §10 C8.
- **Ciclo do `PERDIDO` completo (2026-08-12, `feat/cadence-auto-perdido`):**
  auto-`PERDIDO` no encerramento da cadência (dia 14 sem resposta →
  `PERDIDO`/`NAO_RESPONDEU` após `CADENCE_CLOSE_GRACE_DAYS`) — com o requeue C8,
  entrada + saída automáticas. Ver §10 C9.
- **Backlog pendente (⬜ do §5):** P3 (4.18–4.21, 4.26–4.27).
  Pendências abertas de itens concluídos: 4.17
  (bottom-nav opcional, DnD em touchscreen, validação em device real).
- **C5 entregue (2026-08-14, branch `feat/erp-webapps-template-seed`):** decisão
  fechada — template de categoria "Aplicações Web / ERP" no seed (sem terceiro
  perfil). Ver §10 C5.
- **Pendências operacionais (2026-08-14):** base local vazia (0 leads) e chaves
  `GROQ_API_KEY`/`GOOGLE_API_KEY` sem valor — o reprocessamento (C2/C3, 56 leads)
  e a reanálise dos 18 leads `NOVO` (rate-limit pré-PR #77) devem ser executados
  na **base real**:
  ```bash
  # 1. Reprocessar presos + evidência de site errada (C2/C3)
  cd services/workers && source venv/bin/activate
  python -m src.scripts.reprocess_stuck_leads --apply --fix-site-evidence

  # 2. Reanalisar os 18 leads NOVO por rate-limit (PR #77) — re-pontua com template
  python -m src.seeds.scoring_templates        # idempotente, garante seeds atuais
  # ... depois, na API/UI: "Reanalisar leads" na campanha (POST /campaigns/{id}/reanalyze)
  ```
