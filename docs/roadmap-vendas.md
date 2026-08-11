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
  copywriter anti-IA, CTA concreto, rodapé LGPD; geração de WhatsApp.
- **Cadência + envio** (`cadence_service.py`/`email_service.py`): humano no
  loop (default) ou `auto_send_email` (opt-in), bounce handling, supressão,
  threading, inbound de resposta/STOP.
- **Multi-tenant completo** (§3): orgs, papéis, convites, isolamento, BYOK.
- **BI + PDF** (`analytics_service.py`, `pdf_report_service.py`): 6 endpoints,
  relatórios `/relatorios`, export PDF, mapa Leaflet, kanban, trilha de
  atividades, conversão por faixa de score.
- **Frontend** Next.js 16: dashboard, campanhas, oportunidades, vendas,
  relatórios, configurações — com temas, roles e CSP.

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

#### 3.3.3 Remoção de membro / saída da org / transferência de ownership ⬜ (P1)

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

#### 3.3.4 Auditoria de membros e acessos ⬜ (P2)

**Proposta:** registrar em `lead_activities` (ou tabela `org_audit_log`) eventos
administrativos: convite criado/aceito/revogado, papel alterado, membro removido,
chave BYOK alterada. Dá rastreabilidade para a diretoria e conformidade.

#### 3.3.5 Papel de venda para "gestor da equipe" ✅/🟡 (parcial)

`MANAGER` já vê todos os leads e o BI de consultores. Falta apenas (a) permitir
que MANAGER gerencie `sales_role` dos membros (hoje só owner/admin) — decisão de
produto, e (b) metas (§4.6). Manter como está até decidir.

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

#### 4.2 Rastreamento de abertura e clique ⬜ (M, gratuito)

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

#### 4.4 Correção do threading de follow-ups ⬜ (S, gratuito)

- **Hoje:** `_thread_headers` em `cadence_service` referencia só o último
  `Message-ID`; Gmail conversa perfeitamente exige a **cadeia** de References.
- **Proposta:** acumular todos os Message-IDs anteriores em `References`
  (`refs + [novo]`), `In-Reply-To` do último.

---

### P1 — Entrega 2 · WhatsApp (canal que fecha venda no Brasil)

#### 4.5 Número validado + fluxo de 1 clique ⬜ (M, custo baixo)

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

---

### P1 — Entrega 3 · Dados de coleta = sinal de venda

#### 4.6 Rating, reviews e dados do Google Maps no scoring ⬜ (S, gratuito)

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

#### 4.7 Mais fontes de contato além da Receita ⬜ (M, gratuito)

- **Hoje:** decisores vêm de Receita (nome dos sócios) + Hunter (opcional) +
  heurística. Hit-rate de e-mail limitado.
- **Proposta (tudo passivo/LGPD):**
  - **Página de contato do site** da empresa (scrape passivo): e-mails/telefones
    públicos → alta veracidade.
  - **Busca de "nome + empresa + email"** em buscadores (padrão já usado para
    LinkedIn) para achar e-mails públicos.
  - **CNPJ enriquecido** (sócios com CPF já mascarado) + `phone` da empresa.
  - Consolidar e marcar proveniência (`email_source`) — alimenta o 4.1.
- **Aceite:** proporção de leads com e-mail verificado sobe.

---

### P1 — Entrega 4 · Gestão comercial (o que a diretoria cobra)

#### 4.8 Valor por oportunidade + forecast ponderado ⬜ (M, gratuito)

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

#### 4.9 Metas de vendas por consultor ⬜ (M, gratuito)

- **Proposta:**
  - Tabela `sales_targets` (org, consultor, mês, meta_reuniões, meta_receita).
  - `/analytics/consultants` retorna **atingimento** (realizado/meta) e ranking.
  - UI: badge de atingimento na página de relatórios e na tela de membros.
- **Aceite:** gestor vê "cada consultor está indo bem/atrasado" com número.

#### 4.10 SLA e lembretes para leads parados ⬜ (M, gratuito)

- **Proposta:** regras configuráveis por org (ex.: QUALIFICADO sem contato há 5
  dias → alerta; RESPONDIDO sem próximo passo em 2 dias → lembrete; lead que
  **abriu** e não respondeu em 2 dias → nudge). Alimenta `today-actions` e
  notificação no kanban.
- **Aceite:** leads quentes nunca ficam esquecidos; painel "ações de hoje"
  reflete as regras.

---

### P2 — Entrega 5 · LGPD e conformidade (indispensável para empresa real)

#### 4.11 Supressão global por e-mail/telefone ⬜ (S, gratuito)

- **Hoje:** `opt_out` e `EmailSuppression` são **por lead**. A mesma pessoa em 2
  campanhas pode receber 2 fluxos (risco LGPD e imagem).
- **Proposta:** no momento do envio (`send_step`/`run_due`), consultar supressão
  **global** (e-mail/telefone cruzando orgs). Movimentar STOP/opt-out de qualquer
  lead para a lista global.
- **Aceite:** pessoa que deu STOP nunca mais recebe de nenhuma campanha.

#### 4.12 Base legal e proveniência explícitas ⬜ (M, gratuito)

- **Proposta:** coluna `legal_basis` por contato/lead (`interesse_legitimo`/
  `consentimento`), origem e timestamp do dado (`email_source`, canal, data),
  e expor num dossiê "origem dos dados" por lead. Protege a EJ juridicamente.
- **Aceite:** todo contato tem origem e base documentadas e auditáveis.

#### 4.13 Retenção e anonimização automática ⬜ (M, gratuito)

- **Hoje:** `DELETE /leads/{id}` existe; sem política automática.
- **Proposta:** job que **anonimiza** PII (nome, e-mail, telefone, CPF) de leads
  sem conversão após X meses (configurável) mantendo metadados agregados para BI;
  log de auditoria de acesso a campos sensíveis.
- **Aceite:** PII não fica retida para sempre; BI continua válido.

---

### P2 — Entrega 6 · Confiabilidade para produção real

#### 4.14 Medidor de cotas por org + alertas ⬜ (M, gratuito)

- **Hoje:** BYOK existe, mas **sem contador de uso** (Places ~100/mês, Groq).
- **Proposta:** contador diário por org/key em `provider_client`; alerta no
  dashboard ao passar 80%; travar chamadas excedentes (fallback/aviso).
- **Aceite:** custo nunca estoura sem aviso; org vê consumo na UI.

#### 4.15 Observabilidade e restauração ⬜ (M, gratuito)

- **Proposta:** logs estruturados dos eventos de cadência/abertura; **teste real
  de restore** do `pg_dump` quinzenal; `pytest` com 1 E2E do ciclo completo de
  outreach (agendar→verificar→enviar→abrir→responder/STOP); Sentry se aplicável.
- **Aceite:** backup é comprovadamente restaurável; ciclo completo tem teste.

#### 4.16 Paginação e performance das listas ⬜ (M, gratuito)

- **Proposta:** paginação server-side nas listas de leads/kanban (hoje em
  memória), índice composto `(organization_id, status, qualification_score)`,
  debounce já feito na busca.
- **Aceite:** listas de milhares de leads sem travar a UI.

#### 4.17 Frontend mobile-first ⬜ (M, gratuito)

- **Proposta:** revisar kanban/tabelas/mapas para o celular (consultor trabalha
  no WhatsApp no celular; EJ tem rotatividade e quem trabalha em campo).
- **Aceite:** principais fluxos (ver leads, abrir WhatsApp, mudar status)
  utilizáveis no celular.

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
| 4.1 | Verificação de e-mail (MX/blocklist) + badge | Entregabilidade | P0 | M | gratuito | — | ✅ Entregue 2026-08-04 |
| 4.2 | Rastreamento de abertura/clique (pixel + redirect) | Entregabilidade | P0 | M | gratuito | — | ✅ Entregue 2026-08-05 |
| 4.3 | Warmup, throttling e remetente dedicado | Entregabilidade | P0 | M | gratuito | 4.1 | ✅ Entregue 2026-08-06 |
| 4.4 | Threading completo dos follow-ups | Entregabilidade | P0 | S | gratuito | — | ✅ Entregue 2026-08-05 |
| 3.3.1 | Criar/renomear organização | Multi-org | P0 | S | gratuito | — | ✅ Entregue 2026-08-06 |
| 3.3.2 | Onboarding por convite (cadastro no aceite) | Multi-org | P0 | M | gratuito | 3.3.1 | ✅ Entregue 2026-08-06 |
| 4.5 | WhatsApp: validação + 1 clique + trilha | WhatsApp | P1 | M | baixo | 4.7 | ✅ Entregue 2026-08-10 |
| 4.6 | Rating/reviews do Google no scoring | Dados | P1 | S | gratuito | — | ✅ Entregue 2026-08-05 |
| 4.7 | Mais fontes de contato (site, busca) | Dados | P1 | M | gratuito | 4.1 | ⬜ |
| 4.8 | Valor por oportunidade + forecast ponderado | Gestão | P1 | M | gratuito | — | ⬜ |
| 4.9 | Metas de vendas por consultor | Gestão | P1 | M | gratuito | 4.8 | ⬜ |
| 4.10 | SLA/lembretes p/ leads parados | Gestão | P1 | M | gratuito | 4.2 | ⬜ |
| 3.3.3 | Remover/sair/transferir org | Multi-org | P1 | M | gratuito | 3.3.1 | ⬜ |
| 4.11 | Supressão global por e-mail/telefone | LGPD | P2 | S | gratuito | 4.1 | ⬜ |
| 4.12 | Base legal e proveniência explícitas | LGPD | P2 | M | gratuito | — | ⬜ |
| 4.13 | Retenção/anonimização automática | LGPD | P2 | M | gratuito | — | ⬜ |
| 4.14 | Medidor de cotas por org | Confiabilidade | P2 | M | gratuito | — | ⬜ |
| 4.15 | Observabilidade + teste de restore | Confiabilidade | P2 | M | gratuito | — | ⬜ |
| 4.16 | Paginação/performance das listas | Confiabilidade | P2 | M | gratuito | — | ⬜ |
| 4.17 | Frontend mobile-first | Confiabilidade | P2 | M | gratuito | — | ⬜ |
| 3.3.4 | Auditoria de membros/acessos | Multi-org | P2 | M | gratuito | 3.3.1 | ⬜ |
| 4.18 | Threshold automático por org | Avançado | P3 | M | gratuito | 4.8/4.9 | ⬜ |
| 4.19 | A/B de mensagens | Avançado | P3 | M | gratuito | 4.2 | ⬜ |
| 4.20 | Integrações (Agenda, n8n, Drive) | Avançado | P3 | L | — | — | ⬜ |
| 4.21 | Playbooks por consultor | Avançado | P3 | S | gratuito | — | ⬜ |

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
- **Fase 2 — Conformidade e escala (semanas 6-9):** 4.11-4.13 (LGPD),
  4.14-4.17 (confiabilidade), 3.3.3-3.3.4 (gestão de membros).
  *Critério de saída:* sem risco LGPD pendente, backup restaurável, UI em
  produção sem travar.
- **Fase 3 — Diferenciação (semanas 10+):** 4.18-4.21 (calibração, A/B,
  integrações, playbooks).

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
