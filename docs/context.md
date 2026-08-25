# agente-prospeccao — Context

> Leia este arquivo primeiro. Ele indica o que ler em seguida.

## Leitura obrigatória antes de qualquer tarefa

1. `docs/architecture.md` — estrutura do sistema, stack, serviços, modelo de dados
2. `docs/business-rules.md` — regras de negócio, pipeline, status dos leads
3. `docs/roadmap-vendas.md` — **mapa e norte de evolução** para uso comercial da EJ
   (entregabilidade, WhatsApp, dados, gestão/BI, confiabilidade, multi-org)

## Consulte antes de modificar

- `docs/decisions.md` — decisões técnicas tomadas e motivos
- `docs/coding-standards.md` — padrões obrigatórios de código
- `docs/agents.md` — regras específicas para agentes de IA

## Estado atual (atualizar a cada sessão)

### Fase 1 — Workers (Backend) ✅ Pronta

- `places_service.py` — coleta via Google Places API (async)
- `technical_enrichment_service.py` — análise passiva de sites (async)
  - `_detect_cms` agora usa HTML já baixado (sem nova requisição) + detecção ampliada de stack
  - `_check_seo` verifica title/meta description/h1 + menção a privacidade
  - `performance` interpreta `load_time_ms` (rápido/aceitável/lento/muito lento)
- `scoring_service.py` — qualificação via Groq (openai/gpt-oss-20b)
  - Prompt conhece contexto da campanha (`target_service` + `target_segment`)
  - LLM gera `pitch_angle` (gancho de abordagem) e `suggested_subject` (assunto de e-mail)
  - `primary_need` inclui adequação de privacidade
  - `qualification_reason` vira argumento de venda
- `enrichment_orchestrator.py` — repassa contexto da campanha ao scoring e persiste `pitch_angle`/`suggested_subject`
- `models.py` — `Lead.pitch_angle` (Text) e `Lead.suggested_subject` (String 255) adicionados (migration `1fb286c0715b`)
- `main.py` — `run_enrichment_and_scoring` integrado com scoring
- AsyncClient refactorado para pattern per-use

### Fase 1.5 — API REST + WebSocket ✅ Pronta (2026-07-10)

- `services/api/` — FastAPI com endpoints REST + WebSocket
- `GET /api/leads` — lista com filtros (status, campaign, search, min_score)
- `GET /api/leads/stats` — estatísticas agregadas
- `GET /api/leads/{id}` — detalhe do lead (inclui `pitch_angle` e `suggested_subject`)
- `GET /api/campaigns` — lista com lead_count e avg_score
- `GET /api/campaigns/{id}` — detalhe da campanha
- `GET /api/metrics` — métricas do dashboard + funnel
- `POST /api/pipeline/start` — inicia pipeline em background, retorna job_id
- `POST /api/leads/{id}/generate-messages` — gera sequência de outreach via Groq Llama 3.3 70B
  - Busca lead + campanha (context_service/segment) + contatos
  - Retorna subject, body_opening, followup_1/2, closing, whatsapp_short, rationale
- `POST /api/auth/forgot-password` — gera token de reset e envia email (ou loga no console)
- `POST /api/auth/reset-password` — redefinie senha com token válido
- `POST /api/auth/change-password` — altera senha do usuário autenticado
- `PATCH /api/auth/profile` — atualiza nome do perfil
- `pipeline_worker.py` — repassa `campaign.target_service/segment` ao scoring ao chamar `process_single_lead`
- `WS /ws/pipeline/{job_id}` — streaming de eventos em tempo real
- Reutiliza models e session dos workers
- CORS configurado para frontend
- Email service (stdlib smtplib) com fallback para console em desenvolvimento
- Migration `d5e6f7a8b9c0` — `reset_token` + `reset_token_expires` em users

### Fase 2 — Frontend Web ✅ Concluído (2026-07-10)

**Unificação campanhas/pipeline:**
- `/campanhas/[id]` — detalhe da campanha com pipeline inline, botão "Iniciar Coleta", tabela de leads
- `CampaignList` — cards com link para detalhe + botão "Iniciar Coleta"
- Sidebar: "Buscas" → "Campanhas"; "Acompanhamento" removido
- Página `/pipeline` removida

**Auth completo:**
- Setup Next.js 16 + React 19 + TypeScript
- shadcn/ui configurado (21+ componentes)
- NextAuth.js com Credentials provider (email/senha + JWT)
- Login + Registro + Esqueci senha + Resetar senha
- Link "Esqueci minha senha?" na página de login
- Páginas: `/esqueci-senha` (form email → token enviado) e `/resetar-senha` (token URL → nova senha)
- Backend FastAPI com auth (registro + login + bcrypt + JWT, forgot/reset/change/profile)
- Todas as rotas da API protegidas por autenticação JWT

**Páginas do app:**
- `/dashboard` — métricas interativas + gráficos (Recharts + TanStack Query)
- `/campanhas` — lista + wizard 4 etapas (criação) + detalhe com pipeline inline
- `/oportunidades` — lista de leads + detalhe com abas (Dados gerais, Evidências, Análise do site, Contatos, Ações)
  - Botão "Gerar mensagem personalizada" com modal de Tabs e cópia integrada
- `/vendas` — kanban com drag-and-drop (6 colunas do funil)
- `/configuracoes` — perfil (editar nome), aparência (temas claro/escuro/alpha), segurança (trocar senha)

**Pipeline / Reanálise:**
- Pipeline monitor com WebSocket streaming
- `POST /api/campaigns/{id}/reanalyze` — reanalisa leads existentes sobrescrevendo scoring legado
- Botão "Reanalisar leads" no `CampaignPipeline`
- `load_scoring_template` com match por `target_service` e `target_segment`

**Kanban / PATCH status:**
- `POST /api/leads/{id}/status` — endpoint PATCH para atualizar status
- `LeadStatus` enum expandido: `REUNIAO_FEITA` e `PROPOSTA_ENVIADA`
- `GET /api/leads?status=` aceita múltiplos valores separados por vírgula
- KanbanBoard: drag-and-drop chama PATCH + toast de confirmação (sonner)
- Botão "Registrar contato realizado" no detalhe do lead

**Scoring explicabilidade (Fase 2):**
- `score_factors[]` (±), `evidence[]` (severidade), `priority` (HOT/WARM/COLD), `executive_summary`
- Frontend: EvidenceCard com fatores +/− coloridos, prioridade com badge
- Migration `c4a1f2e8b9d0` + tabela `campaign_scoring_templates`
- 7 templates seedados: Desenvolvimento de Sites, SEO/Marketing Digital, Aplicações Web/ERP, Eng. Mecânica, Automação Industrial, Consultoria Empresarial, Genérico

**Gerar mensagens de outreach:**
- `apps/web/src/types/index.ts` — `OutreachMessages` interface
- `apps/web/src/lib/api.ts` — `leadsApi.generateMessages` + `authApi` completo
- `apps/web/src/hooks/use-api.ts` — `useGenerateMessages` (useMutation sem invalidate)
- Modal Dialog com Tabs (E-mail, Follow-ups, WhatsApp) e botões de cópia

**Reformulação UI/UX (Branch `feat/ui-ux-revamp`):**
- **Sistemas de Design & Tipografia**: Fontes `Inter` (sans) + `Space Grotesk` (display) + `Geist Mono` (mono). Paleta de cores renovada em OKLCH com dark mode adaptativo.
- **Componentes Globais de Layout**:
  - `BrandMark`: Ícone de radar (sinal de oportunidade) customizado em SVG.
  - `AuthShell`: Layout dividido para páginas de autenticação com cartão explicativo do produto.
  - `PageHeader`: Cabeçalho padronizado com sobrancelha, título font-heading, descrição e slot de ações.
  - `EmptyState`: Componente para listas sem itens com ícones e chamadas para ação.
- **Páginas Refatoradas**: Dashboard, Campanhas, Oportunidades, Negociações (Kanban), Relatórios, Equipe, Configurações e Auth (Login, Register, Esqueci/Resetar Senha, Aceitar Convite).
- **Sidebar & Header**: Navegação em grupos ("Visão", "Operação", "Inteligência", "Gestão"), indicador ativo de barra lateral, e switcher de organizações aprimorado.
- **Suporte a Temas Multi-Modo (Claro / Escuro / Alpha)**:
  - `.alpha` variante adicionada em `globals.css` baseada no tema da empresa juníor AlphaMec (`#4c0000`, `#630201`, `#ffffff`, `#7c0000`, `#910001`).
  - Tema Alpha refinado para paleta harmônica (dark com vermelho profundo elegantente).
  - `ThemeProvider` estendido para aceitar `['light', 'dark', 'alpha']`.
  - Página `/configuracoes` permite alternância em tempo real entre os 3 temas com persistência em `localStorage` (`app-theme`).
  - **(2026-08-13)** `next-themes` removido: provider próprio em
    `components/theme-provider.tsx` (classe no `<html>`, `useSyncExternalStore`,
    sync cross-tab, anti-flash via script inline SSR no `layout.tsx`).

**Bloco 2 de melhorias (`docs/melhorias.md`) — vertentes flexíveis:**
- **Enriquecimento por perfil de vertente**: `CampaignScoringTemplate.enrichment_steps`
  declara as fontes de informação (`technical_site` | `cnpj_receita` |
  `business_social`); fallback pelos flags antigos quando ausente. O
  `enrichment_orchestrator` agora RODA o passo cadastral (`CnpjService.lookup`)
  para vertentes industriais — persiste em `Enrichment.raw_business_data` com
  TTL 30d (`enrichment_timestamps["cnpj"]`) e injeta `cnae_info` +
  `company_size_info` nos facts do scoring (os dois caminhos). Falha do
  provedor (Receita/BrasilAPI) loga warning e segue o batch — nunca derruba.
  Seeds: Eng. Mecânica usa `["cnpj_receita","business_social"]` (sem site).
- **Cadência longa por template**: `CampaignScoringTemplate.cadence_schedule`
  define os dias das 4 mensagens (padrão 0/3/7/14; Eng. Mecânica 0/7/30/60).
  `schedule_cadence` aceita `day_offsets` (invalido → fallback); `cadence/start`
  resolve o calendário pelo template da campanha e devolve em `schedule`.
  Rótulos das etapas deixaram de citar "dia N" (a UI mostra a data agendada).
- **UI (wizard campanha, passo 4)**: seções "O que analisar nesta empresa"
  (toggles de Site/Receita/Reputação Google) e "Acompanhamento da empresa"
  (4 dias configuráveis) no `template-selector`; `CadencePanel` sem textos
  fixos 0/3/7/14.
- Migration `c2d3e4f5a6b7` (colunas `enrichment_steps`, `cadence_schedule`,
  `raw_business_data`).

**Bloco 3 de melhorias (`docs/melhorias.md`) — gerenciador de vertentes na UI:**
- **Permissão MANAGER+**: criar/editar/gerar/apagar vertente exige
  MANAGER/owner/admin (`require_manager`); CONSULTOR/ANALYST usam as vertentes
  existentes (leitura no wizard e na tela). NO wizard, não-gestor vê aviso
  "edição exclusiva de gestores" em vez do editor.
- **Geração por IA como rascunho**: `POST /api/scoring-templates/generate`
  (manager+, rate-limit 15/min) recebe `service`/`segment`/`description` em
  linguagem natural, usa `TemplateGenerationService.build_draft` (novo — gera
  sem persistir, LLM + validação; quota 429, falha 502, label repetido 409) e
  **persiste já como rascunho** `is_generated=True`/`is_active=False` — sem
  persistência prévia, fechar a página sem querer perderia o trabalho.
- **Duplicar vertente** (`source_template_id` opcional no POST): copia critérios,
  fontes, cadência, instruções e playbook de uma global/da org como ponto de
  partida ("quero algo como Eng. Mecânica ajustado pro meu ICP"); body explícito
  tem precedência; globais continuam protegidas de PATCH/DELETE (400/404).
- **DELETE `/api/scoring-templates/{id}`** (manager+): remove vertentes da org;
  409 quando em uso por `N` campanha(s); globais invisíveis (404).
- **Frontend `/configuracoes/vertentes`** (sidebar Gestão, ícone Layers):
  lista (global/rascunho/gerada/inativa), busca, criação por IA em 1 campo,
  duplicar (dialog com nome default "(cópia)"), excluir (AlertDialog), ativar/
  inativar (switch), editor reutilizável. Editor extraído do wizard para
  `components/vertentes/template-editor.tsx` (DRY com `template-selector.tsx`).
- **Humanização da UI (editor inteiro, wizard + vertentes)**: "Sinais
  positivos/negativos" → "Características que indicam/reduzem oportunidade";
  "Playbook de outreach (item 3.8)" → "Como abordar esse tipo de empresa";
  "subject" → "Assuntos para o e-mail"; "Hooks" → "Frases de abertura";
  "Objeções do decisor" → "Dúvidas comuns do cliente"; "a IA roteia" → "a IA
  escolhe os melhores critérios"; placeholder "Sinal" → "nome da característica".
  Auditoria final: badge "Template de critérios" (wizard Agente) → "Critérios
  de avaliação"; card de mensagens salvas em /configuracoes perdeu "playbook"/
  "vertical" dos textos visíveis ("Salvar mensagem", "Segmento (opcional)");
  badge redundante "Uso autorizado" removido da lista de vertentes.
- **Testes**: `tests/test_vertentes_manager.py` (13) — permissão, duplicar,
  rascunho por IA (quota/LLM), delete. Suíte em **381 passed**; compileall,
  `tsc --noEmit`, `lint` e `npm run build` limpos.

**Bugfix (2026-08-19) — loop infinito no tour guiado:** `guided-tour-manager.tsx`
tinha deps instáveis no efeito de destaque (`visibleSteps` = array novo por
render; `updateStatusMutation` = objeto novo do `useMutation`) → cada
`setIsWaitingForElement` (aguardando elemento) reexecutava o efeito →
"Maximum update depth exceeded". Fix: `visibleSteps` memoizado (`useMemo`) e
uso do `mutate` estável no lugar do objeto da mutation.

**Bloco 1 de melhorias (`docs/melhorias.md`):**
- **Alerta de nota mínima baixa** (`OrgThresholdSettings` em `/configuracoes`, owner/admin): aviso visual quando o `qualification_threshold` fica abaixo de 50, sem jargão técnico.
- **Proteção de entregabilidade de e-mail**: `AnalyticsService.check_email_deliverability()` + endpoint `GET /api/analytics/deliverability` (ANALYST/MANAGER). Scheduler `_deliverability_check_loop` (poll `DELIVERABILITY_POLL_SECONDS`, default 1h) pausa `auto_send_email` quando bounce > 5%. `EmailSuppression` ganhou `organization_id` (migration `b2c3d4e5f6a9`) para os alertas serem por organização.
- **Webhook de importação `POST /api/webhooks/import`**: recebe `campaign_id` + array de até 500 empresas (n8n/Make/Zapier/Apps Script), protegido por `EMAIL_WEBHOOK_SECRET`; deduplica por `place_id`/site/CNPJ e cria contato opcional. Mensagens de erro em linguagem amigável.

**Tutorial & Onboarding Interativo Multi-Páginas:**
- Sistema completo de onboarding guiado em 7 etapas navegando pelas páginas da aplicação (`/dashboard` → `/campanhas` → `/oportunidades` → `/vendas` → `/relatorios` → `/configuracoes`).
- `driver.js` com estilização nos temas Claro, Escuro e Alpha (tokens OKLCH e tipografia Space Grotesk / Inter).
- Persistência híbrida no Postgres (`User.onboarding_status`) e `localStorage` com endpoints `GET /api/auth/me` e `PATCH /api/auth/onboarding`.
- Opção para refazer tutorial no Header (menu de perfil) e no card de tutorial em `/configuracoes`.
- **(2026-08-19) Tour profundo + botão Voltar**:
  - **Botão "Voltar" corrigido**: o driver.js desabilita o botão anterior sempre que a instância tem um único passo (nosso caso, um driver por etapa). Agora `onPopoverRender` re-habilita o botão (desabilitado só no 1º passo) e o driver é destruído antes de navegar de rota — o overlay antigo não bloqueia a página de destino.
  - **Tour aprofundado**: de 7 → 24 etapas cobrindo cada função por página (métricas clicáveis, funil, campanhas ativas, ações de hoje, linha do tempo; lista/cards/coleta de campanhas; filtros/busca/seleção em lote de oportunidades; kanban com WhatsApp/atribuição; período+PDF/visão executiva nos relatórios; criação/duplicação de vertentes; perfil/chaves/envio automático nas configurações). Novas âncoras `data-tour` adicionadas em dashboard, campanhas, oportunidades, vendas, relatórios, vertentes e configurações. `tsc`/`lint`/`build` limpos.

**Bugfixes de qualidade de dados e UI (2026-08-04):**
- **Limite de coleta**: `campaign-pipeline.tsx` agora busca até **50 leads** por coleta (era 10).
- **Mensagens de outreach**: botão "Gerar/Enviar mensagem" no detalhe do lead agora dispara a geração por IA ao abrir o modal (antes ficava vazio até clicar em gerar). Adicionado estado de loading.
- **Perfis falsos (Instagram/LinkedIn)**: `contact_enrichment_service.py` agora NUNCA salva URL de LinkedIn não confirmada passivamente (removido fallback de confiança 45); `places_service.py` trata website que aponte para rede social (`is_social_domain`) como "sem site próprio" — evita análise técnica errada / score 0 / falso "tem site".
- **Crash em Evidências**: `evidence-card.tsx` agora tolera `scoreFactors === null` (mostra estado vazio em vez de quebrar).
- **Pitch genérico**: instruções do `pitch_angle`/`suggested_subject` no prompt de scoring reforçadas para exigirem ganchos FACTUAIS e específicos (nunca genéricos).
- **Estimativa de leads**: texto hardcoded "45-60 leads" removido do wizard de campanha (substituído por orientação sobre o fluxo).

**Coleta incremental + PDF no Windows (2026-08-04):**
- **Coleta de leads NOVOS por rodada**:
  - `places_service.search_places(query, max_results, exclude_place_ids=None)` agora aceita um conjunto de `place_id`s já coletados e os filtra ANTES de paginar — cada rodada traz leads realmente inéditos, sem gastar páginas da API com já conhecidos.
  - `pipeline_worker.py` consulta os `place_id`s já salvos da organização e repassa ao `search_places`. Mantém a dedup por `place_id`/`company_name+website`/`normalized_domain` como rede de segurança.
  - Teto de 6 páginas (`max_pages`) por rodada para não estourar custo da API quando quase tudo já foi coletado.
  - Padrão do botão de coleta: **20 leads por rodada** (`campaign-pipeline.tsx`).
- **PDF funcionando no Windows**:
  - Causa do erro 500: dois runtimes GTK na máquina — `GTK3-Runtime Win64` (Pango 1.50, com `pango_context_set_round_glyph_positions`) e `Gtk-Runtime` (Pango 1.43, sem o símbolo exigido pelo WeasyPrint 61+). O Windows carregava a Pango antiga → `AttributeError` → 503/erro de fetch no export.
  - Fix: `pdf_report_service._setup_windows_gtk()` agora adiciona TODOS os diretórios GTK válidos via `os.add_dll_directory` e precede `GTK3-Runtime Win64\bin` no `PATH` do processo (precedência da versão nova).
  - Testado: `_setup_windows_gtk()` + WeasyPrint renderiza PDF (3736+ bytes).

**Segurança / CSP:**
- `middleware.ts` (renomeado de proxy.ts) — proteção de rotas + CSP por ambiente
  - Dev: `'unsafe-eval'` + `'unsafe-inline'` para HMR
  - Prod: `'strict-dynamic'` + nonces, mais restrito
  - Rotas públicas: /login, /register, /esqueci-senha, /resetar-senha, /api/auth

**Sugestão de segmentos por IA (wizard de campanha):**
- `services/workers/src/services/segment_suggestion_service.py` — Groq Llama 3.3 70B
  - `SegmentSuggestionService.suggest(profile, current_segment?, exclude?)` → dict
  - Prompt conhece o perfil (`web_presence` / `business_opportunity`) e variação por
    `temperature=0.9` + lista `exclude[]` para evitar repetição imediata
  - Fallback determinístico offline (`FALLBACKS` por perfil) quando Groq falha
  - Retorna: `segment`, `rationale`, `subniches[]`, `hook`, `cities_hint[]`
- `POST /api/campaigns/suggest-segment` — endpoint autenticado (JWT)
  - Body: `{ profile, current_segment?, exclude? }` — `profile` válido via Pydantic
  - Rota declarada antes de `/{campaign_id}` para evitar conflito de path matching
- `apps/web/src/lib/api.ts` — `campaignsApi.suggestSegment`
- `apps/web/src/hooks/use-api.ts` — `useSuggestSegment` + tipo `SegmentSuggestion`
- Wizard `/campanhas/nova` (step 2): botão "Me sugira segmentos" ativo
  - Card de resultado com segmento (preenche input), rationale, hook em itálico,
    subnichos clicáveis como Badges, cidades com densidade via `cities_hint`
  - Botão "Gerar outro" no canto do card — repete chamada com `exclude` atualizado

### Fase 3 — Services Avançados (Futura)

- `contact_enrichment_service.py` — Hunter.io + WHOIS + CNPJ
-        `outreach_service.py` — mensagens IA + envio via Resend ✅ (agora em uso pelo endpoint generate-messages)
   - **Quality overhaul das mensagens (2026-07-14)** — `outreach_service.py`:
     SYSTEM_PROMPT reescrito como copywriter sênior com regras anti-generic-AI
     (primeira frase factual direta, sem "notei que"/"ao analisar", sem jargão
     como "soluções"/"sinergia", sem frases-IA"diante disso"/"vale destacar"),
     CTA específico com horário proposto ("terça 10h ou quarta 14h"),
     contagens mínimas: body 200-280, followup_1 120-160, followup_2 140-180,
     closing 70-100 palavras. `max_tokens=3200` no payload Groq. Schema JSON
     atualizado. Bugfix do rodapé de opt-out ("B2P" → "B2B"). INSTRUÇÕES do
     `build_prompt` agora guiam saudação em linha separada + observação
     factual imediata.
- Integração Cal.com para agendamento

### Fase A — Multi-tenant e Isolamento (P0) ✅ Concluído (2026-08-01)

**Models (workers):**
- `Organization` (workspace com `slug` único) + `OrganizationMember` (owner/admin/member)
  + `Invite` (convite por e-mail com token)
- `Campaign.organization_id` (NOT NULL) e `Lead.organization_id` (NOT NULL)
- `Lead.place_id` unique global → composta `uq_leads_org_place_id (organization_id, place_id)`
- `Job.organization_id` (nullable, jobs legados sem campanha)

**Migration `9a7b6c5d4e3f2`:**
- Cria `organizations`, `organization_members`, `invites`
- Enum `organization_role` (owner/admin/member)
- Backfill: uma org pessoal por usuário existente + membership owner + propagação
  para campanhas/leads/jobs
- Índices em `organization_id` (campaigns/leads/members)

**API (isolamento cross-tenant):**
- `org_service.py`: `create_personal_organization` (registro), `unique_slug`, `user_organization`
- `auth/dependencies.py`: `get_user_organization` — dependency que resolve a org do usuário
- `leads.py`, `campaigns.py`, `metrics.py`: toda listagem/detalhe/mutate filtra por org
- `pipeline.py`: job cria com `organization_id`; campanha validada como da org;
  WebSocket valida que o job pertence à org do usuário (403)
- `auth.py` register: cria org pessoal no onboarding
- `pipeline_worker.py`: leads coletados herdam org da campanha; filtro de leads por org

**Testado E2E:** registro de 2 usuários → orgs separadas; mesmo `place_id` em orgs
diferentes persiste; duplicata na mesma org rejeitada; A não vê lead/campanha de B (404).

### Fase X1 — Atribuição de leads + trilha (item 1.1 do roadmap) ✅ (2026-08-01)

- `Lead.assigned_to_id` (FK users) + `Lead.assigned_at` — dono do lead (consultor)
- Tabela `lead_activities` + enum `lead_activity_action` (CREATED/ASSIGNED/UNASSIGNED/
  STATUS_CHANGED/MESSAGE_GENERATED/CONTACTED/RESPONDED/MEETING_SCHEDULED/CONVERTED)
- `Conversion.user_id` + `Conversion.assigned_to_id` (quem fechou / quem trabalhava)
- `lead_activity_service.py`: `log_activity()` / `log_status_change()` — gravação central
- `PATCH /api/leads/{id}/assign` — atribui/desatribui (valida membro da mesma org, 403
  se não pertencer); grava ASSIGNED/UNASSIGNED
- `PATCH /api/leads/{id}/status` agora grava STATUS_CHANGED com status anterior
- `POST /api/leads/{id}/generate-messages` grava MESSAGE_GENERATED
- Detalhe do lead (`_lead_detail`) expõe `assigned_to` + `activities[]` (trilha)
- Migration `6b3c2a1d9e8f4`

**Testado E2E:** atribuir consultor da mesma org OK; atribuir usuário de outra org → 403;
mudança de status grava trilha (from/to corretos); trilha aparece no detalhe.

### Fase 1.2/1.3 — Router + geração de template sob demanda ✅ (2026-08-01)

- `template_router.py`: `route_scoring_template()` — exact → fuzzy (token overlap) →
  LLM (Groq 8B) → `GENERATE_NEW`/Genérico; cache em memória (256, chave=texto+labels)
- `template_generation_service.py`: `TemplateGenerationService.generate()` — Groq 70B
  cria `positive/negative/context_signals` + flags + `extra_instructions` no schema do
  seed; persiste com `is_generated=True` + `organization_id`; reutiliza por label; fallback Genérico
- `campaign_scoring_templates.is_generated` + `organization_id` (migration `7d4e5f6a8b9c0`)
- `pipeline_worker.py`: consome `GENERATE_NEW` → gera e vincula o template à campanha

**Testado:** router classifica "engenharia mecânica" → Eng. Mecânica; "auditoria contábil"
→ Consultoria; geração cria 7 sinais positivos p/ "landing pages para clínicas de psicologia".

### Fase 1.4 — Campanha por linguagem natural ✅ (2026-08-01)

- `campaign_brief_service.py`: `CampaignBriefService.interpret()` — Groq 70B parseia
  brief PT-BR → `name`, `target_service`, `target_segment`, `target_city`,
  `target_state`, `analysis_profile`, `places_query`, `scoring_template_label`,
  `rationale`; validação Pydantic + erro 502 claro em falha (sem fallback inventado)
- `POST /api/campaigns/from-brief` — devolve a sugestão SEM criar; resolve o template
  mais próximo via router (exact/fuzzy/LLM) para o review card
- `campaigns.places_query` (migration `8a1b2c3d4e5f6`) — query otimizada p/ Places;
  pipeline a usa quando presente (senão monta de target_segment/city/state)
- Frontend `/campanhas/nova`: toggle **Wizard | Agente**; modo agente = textarea +
  "Gerar campanha" → review card editável → "Criar" ou "Criar e iniciar coleta"
- Corrigido erro TS pré-existente (interface `OutreachMessages` duplicada em api.ts)

**Testado E2E:** brief "landing pages p/ clínicas de psicologia em Araraquara" →
campos corretos + template "SEO / Marketing Digital" (MATCHED); campanha criada
com `places_query`; pipeline coletou 3 leads de psicologia em Araraquara e
qualificou 2 (score 62/64) usando a query do agente.

### Fase 1.5 — CRUD de templates + vínculo no wizard ✅ (2026-08-01)

- `GET/POST/PATCH /api/scoring-templates` (novo route): globais (org NULL) + da org;
  `scope=all|global|org`, `include_inactive`, `search`; POST cria com `is_generated=False`
  na org do usuário; PATCH edita sinais/flags/instruções/`is_active` (usado na
  revisão humana do item 1.5.4); isolamento por org validado (404 para outra org)
- `PATCH /api/campaigns/{id}` — vincula/desvincula `scoring_template_id` (valida
  org ou global); pipeline já consome via `explicit_template_id`
- Frontend: `template-selector.tsx` no passo 4 do wizard — escolhe template,
  edita sinais (positive/negative/context + weight), flags (técnica/cadastrais),
  instruções; badge "Gerado por IA — revisar" para `is_generated` (1.5.4);
  "Salvar alterações no template" (PATCH) e vínculo automático ao criar campanha

**Testado E2E:** lista globais (9 seeds); criar template local (org scoping);
PATCH sinais/flags; vincular template à campanha; outra org → 404 + scope=org vazio.

### Fase 2.1 — Papéis de venda 🟡 em andamento (2026-08-01)

- `OrganizationMember.sales_role` — enum `CONSULTOR`/`ANALYST`/`MANAGER`
  (default CONSULTOR), **por organização** (migration `b2c3d4e5f6a7b`, aplicada)
- `SalesRole` exportado no re-export da API; pesos: CONSULTOR=0, ANALYST=1, MANAGER=2
- Dependencies novas (`auth/dependencies.py`):
  - `get_user_membership()` — membership da org ativa (403 se não membro)
  - `require_sales_role(min)` (fábrica) + `require_analyst()` + `require_manager()`
  - `require_org_admin()` — owner/admin (gestão de membros)
  - owner/admin equivalem a MANAGER para leitura/BI independente do papel de venda
- `src/services/org_service.py`: `is_full_access(member)` (ANALYST/MANAGER/owner/admin)
  + `consultant_lead_scope(member, query)` — CONSULTOR vê só leads dele OU não atribuídos
- `routes/orgs.py` (novo): `GET /api/orgs/{id}/members` (MANAGER+)
  + `PATCH /api/orgs/{id}/members/{user_id}` (owner/admin) → define `sales_role`
- `routes/leads.py`: escopo por papel em `list`, `stats`, `get`, `status`, `assign`,
  `generate-messages` (CONSULTOR → 403 em lead de outro consultor; auto-atribuição de
  lead não atribuído permitida)
- Registrado em `main.py`

**Testado E2E:** CONSULTOR vê 3 (2 seus + 1 não atribuído) e é bloqueado (403)
em lead do ANALYST; ANALYST vê todos (4); owner promove/rebaixa membro
(CONSULTOR↔MANAGER); CONSULTOR não lista membros (403) nem muda papel (403).

**Pendente 2.1:** ~~frontend (badge de papel, gestão na tela de membros), testes
automáticos, revisão de `require_org_admin` para ADMIN (hoje ADMIN já passa).~~
**Frontend entregue (2026-08-02)** — badge de papel de venda, página `/configuracoes/membros`
(gestão de papéis por owner/admin), kanban com self-assign + badge de atribuição, badge no
perfil, sidebar "Equipe", `GET /api/orgs/me` e `assigned_to_name` no lead. PR #25 aberto.

### Fase 2.2 — APIs de BI ✅ (2026-08-02)

- `src/services/analytics_service.py` (novo) — `AnalyticsService` org-scoped (filtra
  por `organization_id` em todas as queries; nada vaza entre tenants)
- `routes/analytics.py` (novo) — 6 endpoints **ANALYST/MANAGER-only**
  (owner/admin passam); CONSULTOR → 403:
  - `GET /api/analytics/overview` — KPIs, funil, conversão/reunião/resposta, leads por faixa de score
  - `GET /api/analytics/consultants` — por consultor: atribuídos, contatados, reuniões, propostas, convertidos, conversão %
  - `GET /api/analytics/leads-ranking` — top leads (`sort_by=score|converted|created`, filtro campanha/período)
  - `GET /api/analytics/geo` — agregação por cidade e UF (count, avg_score, convertidos) p/ heatmap + mapa
  - `GET /api/analytics/campaigns` — leads, qualificados, contatados, reuniões, conversão, receita
  - `GET /api/analytics/timeline` — evolução temporal `group_by=day|week` (novos, reuniões, fechados)
- Filtro de período `from`/`to` (YYYY-MM-DD) em todos os endpoints
- Registrado em `main.py`

**Testado E2E** (banco temporário Postgres + TestClient): dados reais (funil, faixas,
consultor com 1 conversão, geo cidade/UF com convertidos, receita R$5.000, timeline e
filtro período) corretos; **ANALYST → 200 em todos; CONSULTOR → 403 em todos**.

### Fase 2.3 — Exportação PDF ✅ (2026-08-02)

- `src/services/pdf_report_service.py` (novo) — `build_report_pdf()`: agrega via
  `AnalyticsService` (org-scoped) e renderiza **WeasyPrint** (HTML→PDF) com branding:
  visão executiva (KPIs + taxas), funil, por campanha, por consultor, top leads, geo,
  evolução temporal (gráfico CSS)
- **Dependência nova aprovada**: `weasyprint` (requirements da API) + runtime
  GTK/Pango no Windows (`GTK3-Runtime Win64`) com `os.add_dll_directory()` automático;
  em Linux basta o pacote de sistema do Pango
- Cache em memória do HTML agregado (TTL 5min) — item 2.3.4
- `GET /api/analytics/export/pdf?from=&to=` — **ANALYST/MANAGER-only**; retorna
  `application/pdf` com `Content-Disposition: attachment`; 503 se WeasyPrint ausente
- Registrado em `routes/analytics.py` (path fixo, sem conflito)

**Testado E2E** (banco temporário): PDF gerado (`%PDF-1.7`, 29KB, seções presentes);
**ANALYST → 200 + application/pdf**; **CONSULTOR → 403**; PDF com período OK.

### Fase 2.4 — Frontend relatórios/kanban/mapa ✅ (2026-08-02)

- **Dependência nova aprovada**: `leaflet` + `react-leaflet@5` (React 19) + `@types/leaflet`
- **`/relatorios`** (nova rota, guard MANAGER/ANALYST/owner/admin — CONSULTOR vê acesso restrito):
  - KPIs executivos (leads, qualificados, contatados, reuniões, convertidos, receita)
  - Funil, taxas (conversão/resposta/reunião), faixas de score
  - **Mapa de oportunidades** (Leaflet): círculos por UF, cor = score médio, tamanho = nº leads,
    tooltip com convertidos — centroides estáticos (sem API de geocodificação; offline)
  - Desempenho por consultor + campanhas + melhores oportunidades
  - Evolução temporal (Recharts: barras novos/reuniões + linha de fechados)
  - Filtro de período (presets 30/90 dias/Tudo + datas) e botão **Exportar PDF** (download)
- **Kanban `/vendas`**: menu "Atribuir para" (owner/admin/MANAGER) com lista de membros +
  desatribuir; CONSULTOR mantém "Atribuir a mim" (item 2.1)
- **Detalhe do lead**: nova aba **Atividades** — trilha (quem fez o quê, quando, transições)
- Sidebar: item "Relatórios" (visível apenas para ANALYST/MANAGER/owner/admin)
- `analyticsApi` + hooks `useAnalytics*` no client

**Build**: `npm run build` OK (rota `/relatorios`); lint sem erros novos (4 erros são
pré-existentes em `campaign-pipeline.tsx`/`funnel-chart.tsx`); dev server responde.

### Fase 2.5 — Pitch one-pager + site audit ✅ (2026-08-02)

- `src/services/pitch_service.py` (novo) — `build_pitch_one_pager()` e `build_site_audit()`:
  consolida identidade (CNPJ/porte/CNAE), contexto da campanha, qualificação (score, dores,
  necessidade), pitch (gancho, assunto), fatores +/−, evidências, contato principal e auditoria do site
  (SSL, CMS, velocidade, segurança, SEO, privacidade, caminhos expostos)
- `GET /api/leads/{id}/pitch` (endpoint novo no `routes/leads.py`): retorna o pitch one-pager
  estruturado para o vendedor/consultor
- `pdf_report_service.py`: inclui dossiê das 3 melhores oportunidades no PDF do relatório executivo
- Frontend:
  - Rota `/oportunidades/[id]`: nova aba **Pitch One-Pager** (`LeadPitchTab`) com cards de pitch,
    identidade cadastral, contato principal, fatores de qualificação, evidências e auditoria do site
  - `leadsApi.getPitch` e hook `useLeadPitch`
  - Interfaces `PitchOnePager`, `SiteAudit`, `SiteAuditSection` em `types/index.ts`

### Fase A4/A5 — Org switcher + sistema de convites ✅ (2026-08-04)

**Backend:**
- `src/services/invite_service.py` (novo) — `create_invite`, `accept_invite`, `list_pending_invites`, `revoke_invite`
- `POST /api/orgs/{id}/invites` — cria convite (owner/admin only), gera token único com expiração 7 dias
- `GET /api/orgs/{id}/invites` — lista convites pendentes (owner/admin only)
- `POST /api/invites/accept` — aceita convite por token (valida e-mail do usuário autenticado)
- `DELETE /api/orgs/{id}/invites/{id}` — revoga convite pendente
- `GET /api/orgs/my-organizations` — lista todas as organizações do usuário (para org switcher)
- Migration `c3d4e5f6a7b8c` — adiciona `invited_by_id` (FK users) e `sales_role` (enum) à tabela `invites`
- Modelo `Invite` atualizado com relationship `invited_by`

**Frontend:**
- `OrgSwitcher` component — dropdown no sidebar para trocar entre organizações (localStorage com versão `org_storage_v1`)
- `InvitesManager` component — criar/listar/revogar convites (dialog + cards + confirmação AlertDialog + validação de e-mail)
- Rota `/aceitar-convite?token=...` — página pública para aceitar convites (com guard contra requisições duplicadas + acessibilidade aria-live)
- Integrado em `/configuracoes/membros` — seção de convites acima da lista de membros + feedback visual per-member no PATCH role
- API client: `orgsApi.listMyOrganizations`, `invitesApi.{create,list,accept,revoke}`
- Hooks: `useMyOrganizations`, `useInvites`, `useCreateInvite`, `useAcceptInvite`, `useRevokeInvite`
- Types: `OrganizationListItem`, `Invite`
- Middleware: `/aceitar-convite` adicionado como rota pública + CSP aprimorada com `frame-ancestors 'none'` e tile servers no `img-src`
- **Revisão com Skills (`frontend-design` & `vercel-react-best-practices`)**:
  - `OrgSwitcher`: memoização com `useMemo`/`useCallback`, versionamento de schema no localStorage, rótulos de papéis traduzidos (PT-BR), acessibilidade `aria-expanded` e `aria-label`.
  - `InvitesManager`: `AlertDialog` para confirmação de revogação, `render` prop do Base UI, validação de e-mail antes do envio, `aria-hidden` em ícones decorativos.
  - `MembrosPage`: feedback de alteração de papel (`isSuccess`) escopado por usuário individual.
  - `AcceptInvitePage`: ref para prevenir mutação duplicada no React 19 / StrictMode, `aria-live="polite"` no feedback de carregamento.
  - Instruções para agentes atualizadas em `AGENTS.md` e `docs/agents.md`.

**Testado:** migration aplicada, API roda sem erros, org switcher mostra orgs, página de convites renderiza.

### Fase 3.1 — Importação de Leads por CSV ✅ (2026-08-04)

**Backend:**
- `services/api/src/services/csv_import_service.py` (novo) — `CsvImportService.parse_and_import()`:
  - Suporte a delimitadores `,` e `;`
  - Mapeamento flexível de colunas (Nome/Empresa, Site/Website, Telefone, Cidade, Estado/UF, CNPJ, Endereço, Categoria)
  - Validação linha a linha + higienização de URLs e CNPJs
  - Deduplicação por `(organization_id, website/cnpj/place_id)`
  - Geração de `place_id` sintético determinístico (`csv_<hash>`)
  - Retorna relatório estruturado (`total_rows`, `imported_count`, `duplicate_count`, `error_count`, `errors[]`)
- `POST /api/campaigns/{id}/import` — endpoint multipart/form-data com suporte a codificações UTF-8 e Latin-1

**Frontend:**
- `CsvImportModal` component — modal interativo para seleção de arquivos .csv, exibição de regras de colunas, progresso e relatório detalhado pós-importação.
- Integrado na página de detalhe da campanha `/campanhas/[id]` com botão "Importar CSV" no topo.
- `campaignsApi.importCsv` + hook `useImportCsv` com invalidação do cache de campanhas e leads.

### Fase 3.2 — Descoberta de Empresas por CNAE / Receita ✅ (2026-08-04)

**Backend:**
- `services/workers/src/services/cnae_discovery_service.py` (novo) — `CnaeDiscoveryService`:
  - Integração resiliente multi-provedor (BrasilAPI + Minha Receita + CNPJá Open API com rate-limit automático de 5 req/min)
  - Normalização de CNAE e CNPJ
  - Busca de dados cadastrais detalhados
- `pipeline_worker.py`: suporte estendido a `source="cnae"`, permitindo coleta de leads diretamente da Receita Federal
- `POST /api/campaigns/{id}/collect-cnae` — endpoint autenticado para disparar o job de coleta CNAE/CNPJ em background

**Frontend:**
- `CnaeDiscoveryModal` component — modal para inserção de código de CNAE (ex: `2869100`), lista de CNPJs e limite de leads
- Integrado na página da campanha `/campanhas/[id]` com botão "Buscar por CNAE"
- `campaignsApi.collectCnae` + hook `useCollectCnae`

### Fase 3.3 — Enriquecimento Adaptativo ✅ (2026-08-04)

**Backend:**
- `enrichment_orchestrator.py`: seleciona steps condicionalmente (`requires_technical_report` e `requires_business_data` do template) — não faz scraping/requisições HTTP em sites se o template da campanha indicar que auditoria técnica é irrelevante.
- `pipeline_worker.py`: emissão de logs e eventos WebSocket em tempo real para cada step ("Pulpando auditoria técnica de site", "Consultando dados cadastrais/CNAE", "Score contextual").

### Fase 3.4 — Decisor Email + LinkedIn ✅ (2026-08-05)

**Backend:**
- `services/workers/src/services/contact_enrichment_service.py` (novo) — `ContactEnrichmentService`:
  - Multi-provider de e-mail (ordem): **Hunter.io** (opcional, se `HUNTER_API_KEY`) → **Receita Federal via CNPJ** → **heurística determinística** (`nome.sobrenome@dominio`, confidence baixa).
  - LinkedIn (busca passiva, 100% gratuito): DuckDuckGo HTML → fallback Bing → heurística de URL (`linkedin.com/in/primeiro-ultimo`) com validação por índice de busca (LinkedIn bloqueia bots diretos, status 999 — nunca GET direto no perfil).
  - Rate-limit + cache em memória; **passivo** (Lei 12.737/2012 respeitada — sem probe, sem injeção).
  - `_recalc_confidence`: base do contato + bônus por canal confirmado (email/linkedin).
- Migration `e1f2a3b4c5d6` — `contacts.linkedin_url` + `contacts.linkedin_confidence` + enum `lead_activity_action.CONTACT_ENRICHED`.
- `settings.py`: `HUNTER_API_KEY` opcional (default vazio = fallback gratuito).
- `POST /api/leads/{id}/enrich-contacts` — enriquece decisores (Receita → email/LinkedIn) e registra `CONTACT_ENRICHED` na trilha.
- `_lead_detail` agora expõe `contacts[]` (com `linkedin_url`/`linkedin_confidence`).
- `pipeline_worker.py`: **Fase 3 automática** — leads QUALIFICADOS têm decisores enriquecidos (email/LinkedIn) com eventos WS.
- `pitch_service.py`: `primary_contact` inclui `linkedin_url`.
- `outreach_service.py`: fatos do prompt incluem o LinkedIn do decisor (sugere canal ao consultor, sem gerar texto InMail).

**Frontend:**
- `types`: `ContactItem` (com `linkedin_url`/`linkedin_confidence`) + `Lead.contacts[]` + `primary_contact.linkedin_url`.
- Aba **Contatos** do detalhe do lead (antes placeholder): lista de decisores com e-mail (copiar), telefone, LinkedIn (abrir/copiar), badge de confiança e "Enriquecer decisores" (botão).
- `LinkedInIcon` custom (lucide-react 1.x removeu ícones de marca).
- `lead-pitch.tsx`: "Ver perfil no LinkedIn" no card de contato principal.
- `leadsApi.enrichContacts` + hook `useEnrichContacts` (invalida `["leads", id]`).
- Label `CONTACT_ENRICHED` na trilha de atividades.

**Testado:** migration aplicada; helpers (domínio/slug/URL) unit-testados; busca passiva retorna perfil real (Bill Gates → `bill-gates-...`); CNPJ Petrobras → 9 sócios; fluxo completo email+linkedin com lead fake; `npm run build` OK.

### Item 3.5 — BYOK e cotas por org ✅

Branch: `feat/org-byok`

**Workers:**
- `OrganizationSecret` (model) + migration `f2a3b4c5d6e7` — tabela `organization_secrets` (unique `organization_id + key_name`) com `encrypted_value`.
- `secret_service.py` — Fernet (`SECRETS_ENCRYPTION_KEY`) com fallback dev derivado do `DATABASE_URL`; `encrypt_value`/`decrypt_value`; `set_org_secret` (upsert), `delete_org_secret`, `resolve_key`/`resolve_all` (BYOK → pool global).
- Serviços passam a aceitar `api_key` injetável: `places_service`, `scoring_service`, `outreach_service`, `campaign_brief_service`, `segment_suggestion_service`, `template_router` (`route_scoring_template`/`_classify_llm`), `template_generation_service`.
- `settings.py`: `SECRETS_ENCRYPTION_KEY` (default vazio = dev). `.env.example` atualizado.

**API:**
- `pipeline_worker.py` — resolve chaves da org da campanha (`SecretService.resolve_all`) e injeta em Places/Scoring/Template (linhas ~157/223/229/245).
- Rotas que chamam LLM resolvem por org: `suggest-segment`, `from-brief`, `generate-messages`.
- Endpoints CRUD em `routes/orgs.py` (org admin only): `GET/PUT/DELETE /orgs/{org_id}/secrets/{key_name}` — valores nunca expostos (só `configured`).

**Frontend:**
- `orgsApi.listSecrets/putSecret/deleteSecret` + hooks `useOrgSecrets`/`usePutOrgSecret`/`useDeleteOrgSecret`.
- Card **"Chaves de API da organização"** em `/configuracoes` (admin): salvar/atualizar/remover `GOOGLE_API_KEY` e `GROQ_API_KEY`; badge "Configurada"/"Pool global"; não-admin vê aviso.

**Testado:** py_compile de todos os arquivos tocados; imports de rotas e serviços OK; roundtrip Fernet OK; `npm run build` OK; eslint limpo. Quota diária do pool não contabilizada (nota no roadmap 3.5.2).

### Item 3.6 — Feedback conversão → score ✅

Branch: `feat/conversion-feedback`

**Backend (3.6.1):**
- Novo enum actions na trilha: `PROPOSAL_SENT` e `LOST` (migration `f3a4b5c6d7e8`, aplicada).
- `lead_activity_service.semantic_action_for(status)` — mapeia status → action comercial (`CONTATADO`→`CONTACTED`, `RESPONDIDO`→`RESPONDED`, `REUNIAO_MARCADA`→`MEETING_SCHEDULED`, `PROPOSTA_ENVIADA`→`PROPOSAL_SENT`, `PERDIDO`→`LOST`).
- `PATCH /api/leads/{id}/status` agora grava, além da `STATUS_CHANGED`, a action semântica do destino.
- Novo endpoint `POST /api/leads/{id}/conversion` — cria registro em `conversions` (service_sold, contract_value, notes, time_to_close_days derivado do `created_at`) + grava `CONVERTED` na trilha.

**Backend (3.6.2):**
- `analytics_service.overview()` — `leads_by_score_band` agora cruza com `Conversion`: cada faixa traz `count`, `converted` e `conversion_rate` (taxa de acerto do score).

**Frontend:**
- `AnalyticsOverview.leads_by_score_band` type atualizado (converted + conversion_rate).
- `ScoreBandsCard` (relatórios) exibe taxa de conversão por faixa + barra verde proporcional.
- Aba "Próximas Ações" do lead: botão "Registrar conversão" (dialog com serviço, valor, observações) + hook `useRegisterConversion` (invalida leads/analytics/metrics).
- Labels `PROPOSAL_SENT`/`LOST` na trilha do lead.

**Testado:** migration aplicada; PATCH status → action `LOST` gravada (rollback); conversão E2E real → revenue + taxa por faixa refletem (dados limpos depois); `npm run build` OK; eslint limpo (só warnings pré-existentes); app importa OK.

### Item 3.7 — Cadência de follow-up + envio ✅

Branch: `feat/outreach-cadence-playbooks`

**Models (migration `72ce8b2f4cf3`):**
- `FollowUp` (tabela `follow_ups`) — etapas da cadência dia 0/3/7/14 por lead; enums `FollowUpStep` (OPENING/FOLLOWUP_1/FOLLOWUP_2/CLOSING, com `day_offset` 0/3/7/14) e `FollowUpStatus` (PENDING/SENT/SKIPPED/CANCELLED).
- `Organization.auto_send_email` (default false) — opt-in de envio automático.
- `Lead.opt_out` (default false) — opt-out do lead (cadências pendentes → SKIPPED).

**Backend:**
- `email_service.send_email(to, subject, body)` — SMTP ou fallback console (dev).
- `cadence_service.py` — `schedule_cadence` (gera etapas dia 0/3/7/14), `send_step` (envia, registra Message + `CONTACTED` na trilha, move para CONTATADO no 1º contato), `mark_opt_out` (do-not-contact), `run_due` (envio automático só de orgs com opt-in, respeitando opt-out).
- Scheduler asyncio no lifespan do `main.py` (poll `CADENCE_POLL_SECONDS`, default 60s) — sem dependência nova.
- Rotas: `GET /leads/{id}/cadence`, `POST /leads/{id}/cadence/start`, `POST /leads/{id}/cadence/send/{step}`, `POST /leads/{id}/opt-out`; `PATCH /orgs/{org_id}` (auto_send_email) + exposto no `/orgs/me`.

### Item 3.8 — Playbooks por vertical ✅

Branch: `feat/outreach-cadence-playbooks`

- `CampaignScoringTemplate.playbook` (JSONB) — hooks, subject_ideas, objections por vertical.
- Seeds atualizados com playbooks reais (Sites, Petshops, Academias, Farmácias).
- `outreach_service.build_prompt`/`generate_sequence` aceitam `playbook` e injetam no prompt.
- `template_router.get_playbook_for_campaign` resolve o template (exact→fuzzy→LLM→genérico) e devolve o playbook; usado em `generate-messages` e `cadence/start`.
- CRUD de templates expõe/aceita playbook; `template-selector.tsx` edita hooks/assuntos/objeções.

**Frontend:**
- Aba **Cadência** no detalhe do lead (`CadencePanel`): iniciar cadência, lista de etapas com status, enviar etapa manualmente (humano-no-loop), opt-out do lead.
- Configurações da org: toggle **Envio automático de follow-ups** (`OrgSendSettings`).
- Types/hooks: `LeadCadence`, `FollowUpItem`, `useLeadCadence`, `useStartCadence`, `useSendCadenceStep`, `useOptOutLead`, `usePatchOrgSettings`.

**Testado:** migration aplicada; E2E cadência (start → 4 etapas → send OPENING → SENT → opt-out cancela pendentes); scheduler `run_due` enviou follow-up vencido de org com opt-in e registrou Message; playbook resolvido (Petshops → hooks/objeções reais); `npm run build` OK; eslint limpo; app importa OK.

### Item 4.3 — Warmup/throttling + remetente dedicado ✅ (2026-08-06)

Branch `feat/cadence-warmup-throttle` (P0 do roadmap-vendas 4.3):

- **Modelos/migration `f4a5b6c7d8e9`** (aplicada): `organizations.daily_email_limit`
  (default 40) + `send_window_start/end` (default 09:00–17:00);
  `organization_members.email_from` (remetente dedicado por consultor).
- **`cadence_service`**: `run_due` agora respeita **teto diário por org**,
  **janela de espalhamento** (fuso do servidor) e **teto por hora**
  (`ceil(limite*60/janela)`); etapas excedentes ficam `PENDING` (postergadas,
  nunca falham). `sends_today()` conta `Message` de hoje por org. `_resolve_from_email`
  prioriza: consultor dedicado → org → global.
- **Rotas**: `GET /orgs/me` e `PATCH /orgs/{id}` expõem/aceitam os novos campos +
  `sends_today`.
- **settings.py**: `DAILY_EMAIL_LIMIT` (default 40).
- **Frontend**: `/configuracoes` (owner/admin) — badge "Envios hoje X/limite Y"
  com barra de progresso, campos de limite diário, janela e remetente da org.
  `tsc --noEmit` + `lint` + `build` limpos.
- **Testes**: `tests/test_cadence_throttle.py` (12 checagens: limite, janela,
  teto por hora, remetente dedicado).

**Pré-requisitos cumpridos nesta sessão:** `alembic upgrade head` aplicou
`d8e9f0a2b3c4` (rating) e `e2f3a4b5c6d7` (tracking); `TRACKING_BASE_URL`
definido no `.env` (ativa o pixel/redirect).

### Item C.3 — Funil de negociação + resultado de contrato ✅ (2026-08-06)

Branch `feat/negotiation-funnel` (roadmap-leads Parte C.3 — largar a planilha):

- **Modelos/migration `f5a6b7c8d9e0`** (aplicada): `Lead.negotiation_stage`
  (enum `RD/ORCAMENTO/RP`) + `Lead.contract_outcome`
  (`APROVADO/REPROVADO/EM_ANALISE`) + `Lead.outcome_date`. Re-exportados na API.
- **`PATCH /leads/{id}/negotiation`** — registra/limpa estágio e resultado,
  **somente** quando o lead está em `RESPONDIDO/REUNIAO_MARCADA/REUNIAO_FEITA/
  PROPOSTA_ENVIADA` (400 caso contrário); grava a action `NEGOTIATION_UPDATED`
  na trilha. Conversão (`POST /conversion`) marca `contract_outcome=APROVADO`.
- **Exposição**: campos novos no resumo/detalhe do lead (`_lead_summary`).
- **Analytics**: `overview` ganha `negotiation_distribution` e
  `contracts_by_outcome` (BI p/ diretoria).
- **Frontend**: controle **Negociação** na aba Próximas Ações do lead
  (`NegotiationControl` — selects de estágio/resultado + salvar); badge de
  estágio/resultado nos cards do kanban; card **Negociação** nos Relatórios
  (estágio RD/Orçamento/RP + resultado de contrato). `tsc`/lint/build limpos.
- **Testes**: `tests/test_negotiation_enums.py` (4) — suíte em **70 passed**.

### Item 3.3.1/3.3.2 — Criar/renomear org + onboarding por convite ✅ (2026-08-06)

Branch `feat/org-onboarding` (roadmap-vendas P0):

- **3.3.1 — criar/renomear org**: `org_service.create_organization` (dono OWNER
  + `sales_role` MANAGER); `POST /orgs`; `PATCH /orgs/{id}/name` (owner/admin);
  UI no `OrgSwitcher` ("Criar organização") e `OrgNameCard` em `/configuracoes`.
- **3.3.2 — aceite com cadastro**: `GET /invites/check?token=` (público, informa
  email/org/se tem conta) + `POST /invites/accept-register` (cria conta e aceita
  o convite no mesmo fluxo, sem workspace pessoal — cai direto na org do convite;
  devolve JWT p/ auto-login). Página `/aceitar-convite` vira o fluxo completo:
  o convidado decide login (conta existe) × cadastro (não existe).
- **Testes**: `tests/test_org_service.py` (slug + criação owner/MANAGER) — **74
  testes passando**.

### Item C.3 — Pós-venda ✅ (2026-08-06)

Branch `feat/post-sale` (roadmap-leads C.3 — largar a planilha):

- **Modelos/migration `f6b7c8d9e0f1`** (aplicada): `Lead.post_sale_contacted_at`
  (data do 1º contato pós-cliente) + `Lead.post_sale_channel`
  (`WHATSAPP`/`EMAIL`); `FollowUpStep.POST_SALE` (day_offset 14) para o lembrete
  rodar pelo mesmo motor da cadência.
- **`POST /leads/{id}/post-sale`** — registra data+canal, grava action `POST_SALE`
  na trilha e, se houver `content`, agenda um `FollowUp.POST_SALE` (enviável
  manualmente ou com `auto_send_email`). Só para leads convertidos (400 se não).
- **Exposição**: campos novos no `_lead_summary`.
- **Frontend**: `PostSaleControl` na aba Próximas Ações (exibido p/ leads
  convertidos) — canal + mensagem opcional + registrar. `tsc`/lint/build limpos.
- **CI/CD**: job de migrations do `ci.yml` ganhou seed smoke pós-`upgrade head`.
- **Testes**: `tests/test_post_sale.py` (5) — **79 testes passando**.

### Item 4.5 — WhatsApp: validação + 1 clique + registro na trilha ✅ (2026-08-10)

Branch `feat/whatsapp-one-click` (roadmap-vendas P1):

- **Modelos/migration `02a4353c47a7`** (aplicada): `LeadActivityAction.WHATSAPP_SENT`
  adicionado ao enum `lead_activity_action`.
- **`POST /api/leads/{id}/whatsapp-click`**: formata o número no padrão `wa.me`, valida se é móvel BR, atualiza `last_contacted_at` e grava a action `WHATSAPP_SENT` na trilha.
- **Frontend**:
  - `useRecordWhatsAppClick` hook + chamada no Kanban board (botão de WhatsApp no card) e no detalhe da oportunidade (header + modal de mensagens).
  - Toast de confirmação + abertura da janela do WhatsApp com texto pré-preenchido.
  - Tradução `WHATSAPP_SENT` ("WhatsApp acionado") na trilha de atividades.
- **Testes**: `tests/test_whatsapp_click.py` (4) — suíte em **83 passed**. `tsc --noEmit` e `eslint` limpos.

### Item 4.8 — Valor por oportunidade + forecast ponderado ✅ (2026-08-10)

Branch `feat/opportunity-forecast` (roadmap-vendas P1):

- **Modelos/migration `69f0f84a9739`** (aplicada):
  - `Lead.value` (Numeric 12,2) — estimativa de ticket / contrato.
  - `Lead.expected_close_date` (DateTime) — data prevista de fechamento.
  - `Lead.lost_reason` (enum `LostReason`: `PRECO`, `PRAZO`, `NAO_RESPONDEU`, `CONCORRENTE`, `OUTRO`).
- **Backend & BI**:
  - `AnalyticsService.forecast()`: calcula `pipeline_value` em aberto, `forecast_weighted` ponderado pela probabilidade do estágio (`NOVO` 5% → `PROPOSTA_ENVIADA` 90%), `realized_revenue` e distribuição por estágio/motivos de perda.
  - Endpoint `GET /api/analytics/forecast` (ANALYST/MANAGER) + `overview()` atualizado com `pipeline_value` e `forecast_weighted`.
  - `PATCH /api/leads/{id}` aceita `value`, `expected_close_date` e `lost_reason`.
- **Frontend**:
  - Card "Acompanhamento & Oportunidade" no detalhe do lead com edição de ticket (R$), previsão de fechamento e motivo de perda.
  - Badge de valor estimado no card do Kanban board.
  - `ForecastCard` em `/relatorios`: KPIs (Pipeline Total, Forecast Ponderado, Receita Realizada), tabela por estágio e detalhamento de motivos de perda.
- **Testes**: `tests/test_opportunity_forecast.py` (2) — suíte em **85 passed**. `tsc --noEmit` e `eslint` limpos. Corrigido import de `LostReason` no topo de `routes/leads.py` (build CI).

### Item 3.3.3 — Gestão de membros (remover / sair / transferir ownership) ✅ (2026-08-10)

Branch `feat/org-member-management` (roadmap-vendas P1):

- **Backend & Serviços**:
  - `unassign_user_leads_in_org()` em `org_service.py`: desatribui automaticamente todos os leads do usuário na organização e registra atividade `UNASSIGNED` na trilha.
  - `DELETE /api/orgs/{org_id}/members/{user_id}` (owner/admin): desvincula o membro e reatribui seus leads para a fila livre (impede remoção do OWNER e auto-remoção).
  - `POST /api/orgs/{org_id}/transfer-owner` (OWNER only): transfere o papel de OWNER para outro membro ativo da org.
  - `POST /api/orgs/{org_id}/leave`: permite que um membro saia da org e desatribua seus leads.
- **Frontend**:
  - Tabela em `/configuracoes/membros` atualizada com a coluna "Ações": botões com diálogos de confirmação (`AlertDialog`) para "Remover membro", "Transferir Dono" e "Sair da org".
  - Hooks `useRemoveMember`, `useTransferOwnership`, `useLeaveOrganization` em `use-api.ts`.
- **Testes**: `tests/test_org_member_management.py` — suíte em **86 passed**. `tsc --noEmit` e `eslint` limpos.

### Item 4.9 — Metas de vendas por consultor ✅ (2026-08-10)

Branch `feat/sales-targets` (roadmap-vendas P1):

- **Modelos/migration `b613230fd8fd`** (aplicada): tabela `sales_targets`
  (`organization_id`, `user_id`, `month` "YYYY-MM", `meetings_target`,
  `revenue_target`; unique `(org, user, month)`).
- **Backend & BI**:
  - `AnalyticsService.consultants()` agora calcula `revenue_realized` (soma dos
    `Conversion.contract_value` por consultor), resolve a meta do mês do período
    (`_target_month`) e devolve `meetings_target`, `revenue_target`,
    `meetings_attainment` e `revenue_attainment` (% realizado vs meta).
  - CRUD em `routes/orgs.py` (owner/admin p/ gravar, MANAGER+/owner p/ listar):
    `GET /orgs/{org_id}/sales-targets?month=`, `PUT /orgs/{org_id}/sales-targets`
    (upsert), `DELETE /orgs/{org_id}/sales-targets/{target_id}`.
- **Frontend**:
  - `SalesTargetsManager` em `/configuracoes/membros` (card "Metas de vendas" do
    mês atual): definir/editar/remover meta de reuniões e receita por consultor.
  - `ConsultantsCard` em `/relatorios` exibe receita realizada e badges coloridos
    de atingimento de meta (verde ≥100%, âmbar ≥60%, vermelho <60%).
  - Tipos `SalesTarget` + `AnalyticsConsultant` estendido; hooks
    `useSalesTargets`, `useUpsertSalesTarget`, `useDeleteSalesTarget`.
- **Testes**: `tests/test_sales_targets.py` — suíte em **90 passed**. `tsc --noEmit` e `eslint` limpos. Grafo atualizado (`graphify extract` + `cluster-only`: 2128 nós, 4509 arestas, 160 comunidades).

### Item 4.10 — SLA e lembretes para leads parados ✅ (2026-08-11)

Branch `feat/sla-lead-reminders` (roadmap-vendas P1) + `fix/reprocess-stuck-leads-4-9-4-10`:

- **Modelos/migration `c24a13047b0e`** (aplicada): `organizations` ganhou
  `sla_qualified_no_contact_days` (default 5), `sla_responded_no_next_action_days`
  (default 2) e `sla_opened_no_response_days` (default 2) — prazos por org.
- **Backend**:
  - `services/api/src/services/sla_service.py` (novo): `compute_sla_alerts(db, org_id, member, limit=50)` com regras
    `QUALIFICADO_NO_CONTACT` (QUALIFICADO sem nenhum contato há N dias),
    `RESPONDIDO_NO_NEXT_ACTION` (RESPONDIDO sem próxima ação agendada/vencida há N dias)
    e `OPENED_NO_RESPONSE` (abriu mensagem via tracking e não respondeu há N dias);
    respeita o escopo do consultor (`consultant_lead_scope`).
  - Endpoint `GET /api/leads/sla-alerts?limit=` em `routes/leads.py` listando os
    alertas ordenados por dias parados (regras configuráveis por org).
  - `PATCH /orgs/{org_id}` + `/orgs/me` expõem/aceitam os 3 campos SLA
    (validação 1-120 dias).
- **Frontend**:
  - Card **"SLA de leads parados"** em `/configuracoes` (owner/admin) para editar os
    prazos (`OrgSlaSettings`).
  - Seção **"Leads parados (SLA)"** no painel "Ações de hoje" do dashboard com link
    direto para a oportunidade.
  - **Notificação no kanban** (`/vendas`, kanban-board.tsx): chip vermelho "N leads
    parados (SLA)" no topo, contador vermelho por coluna e badge "SLA há Xd" nos
    cartões com alerta ativo (tooltip com o rótulo da regra).
- **Testes**: `tests/test_sla_service.py` (8: 3 helpers + 5 com `compute_sla_alerts`
  cobrindo as 3 regras e a ordenação por criticidade via db fake) — suíte em **118 passed**.

### Item 4.7 — Mais fontes de contato além da Receita ✅ (2026-08-10)

Branch `feat/contact-more-sources` (roadmap-vendas P1 — fechar a Entrega 3):

- **`ContactEnrichmentService`** (`services/workers/src/services/contact_enrichment_service.py`):
  - `_emails_from_site(client, lead)` — GET passivo da home + `/contato`,
    `/fale-conosco` e `/contact`; extrai e-mails/telefones públicos com
    de-ofuscação anti-bot (` [at] `/`(dot)`/entidades HTML); cache `_site_cache`
    por página; fonte `site` (alta veracidade, MX-verificável).
  - `_mail_to_company(client, contact, lead)` — busca passiva `"<nome>"
    "<empresa>" email` em DuckDuckGo/Bing (reusa a infra de LinkedIn); seleciona
    o e-mail cujo local part combina com o nome do decisor; fonte `search:*`.
  - **Precedência de e-mail**: Hunter → **site** → **busca** → **CNPJ** →
    heurística; proveniência sempre gravada em `email_source`/`phone_source` no
    `raw_data` do contato.
  - `_contacts_from_receita` usa o e-mail/telefone cadastral da empresa
    (`company_email`/`company_phone` do DTO da Receita) como fonte extra —
    sócios seguem com CPF mascarado (minimização de dados).
  - Pequeno ganho de qualidade: `_email_heuristic` agora normaliza acentos
    (`João` → `joao`).
- **Frontend**: badge "Fonte: ..." (Site/Busca/CNPJ/Hunter/heurística) ao lado
  do e-mail na aba Contatos do lead (`/oportunidades/[id]`).
- **Sem migration** (usa colunas existentes + `raw_data`).
- **Testes**: `tests/test_contact_site_sources.py` (15) — suíte em **108 passed**.

### Item 4.22 — LinkedIn assistido ✅ (2026-08-11)

Branch `feat/linkedin-assistido-lgpd-cleanup` (roadmap-vendas P1):

- **Backend**:
  - `services/api/src/services/linkedin_assist_service.py` (novo): `build_linkedin_queries`
    (consultas `"<empresa>" <papel> linkedin` — padrão ou `playbook.linkedin_queries` do
    template), `extract_linkedin_username` (formato validado) e `LinkedInAssistService`
    (validação passiva via DDG/Bing + `associate` que grava `linkedin_source="manual:<user>"`
    com confidence 90 validado / 60 revisão e registra `LINKEDIN_ASSOCIATED` na trilha).
  - Migration `c183a77bc662` — action nova `LINKEDIN_ASSOCIATED` no enum
    `lead_activity_action` (aplicada).
  - `GET /api/leads/{id}/linkedin-query` — consultas sugeridas + `search_url`
    (`site:linkedin.com/in`); `PATCH /api/leads/{id}/contacts/{contact_id}/linkedin` —
    valida URL e associa (org-scoped, `_can_access_lead`).
- **Frontend**:
  - `LinkedInAssociateDialog` na aba Contatos: fluxo guiado "copiar consulta → buscar
    no LinkedIn → colar perfil → validar e salvar"; badge "Associado manualmente".
  - Hooks `useLinkedinQueries`/`useAssociateLinkedIn`; label `LINKEDIN_ASSOCIATED`
    na trilha.
- **Testes**: `tests/test_linkedin_assist.py` (8) — suíte em **121 passed**.

### Itens 4.14–4.16 — Confiabilidade (P2) ✅ (2026-08-11)

Branch `feat/p2-confiabilidade` (roadmap-vendas P2 — PR #68):

- **4.14 Cotas por org + alertas** — `QuotaService`/`provider_usage` (workers):
  medidor de cotas diárias por org/provedor + guard em Groq/Places; API:
  endpoint de uso + `PATCH api_quota` + guard/consume nas rotas de IA; frontend:
  card de cotas (Google/Groq) na página `/configuracoes`.
- **4.15 Observabilidade + restauração** — logs estruturados dos eventos de
  cadência/abertura; **teste real de restore** do `pg_dump`; pytest E2E do ciclo
  completo de outreach (agendar→verificar→enviar→abrir→responder/STOP).
- **4.16 Paginação / performance** — paginação server-side no kanban e na lista
  de leads + índices compostos `(organization_id, status, qualification_score)`
  (migration `ca2c1a...`).

### Modelo de 3 Entidades, Google OAuth2, Monitoramento & Catch-All Opt-in ✅ (2026-08-18)

Branch `feat/3-entities-webhooks-integrations`:

- **Modelo de 3 Entidades (Company, Person, Lead — Item 4.27)**:
  - Migration `2b137f2dc6f5`: cria tabelas `companies`, `persons` e `webhook_logs`, e vincula `company_id` e `primary_person_id` ao `leads`.
  - `CompanyPersonService` (`services/workers/src/services/company_person_service.py`): sincronização automática e reutilização de histórico de empresas e decisores na mesma organização. Integrado em `pipeline_worker.py` e `csv_import_service.py`.
  - `duplicate_detection_service.py`: atualizado para considerar `company_id` e `person_id` na detecção de duplicatas.
- **Sincronização Nativa Google Sheets via OAuth2 (Item 4.20)**:
  - `GoogleSheetsService` (`services/api/src/services/google_sheets_service.py`): fluxo OAuth2 completo com autorização, troca/renovação de tokens e espelhamento direto via API REST Google Sheets (`sheets.googleapis.com/v4/spreadsheets`).
  - Endpoints: `GET /api/orgs/{org_id}/google/oauth-url`, `POST /api/orgs/{org_id}/google/oauth-callback` e `POST /api/campaigns/{id}/sync-google-sheets`.
- **Painel de Monitoramento de Webhooks & Jobs**:
  - Backend: endpoints `GET /api/orgs/{org_id}/webhook-logs` e `GET /api/orgs/{org_id}/job-logs`. `webhook_outbound_service.py` grava cada disparo em `webhook_logs`.
  - Frontend UI: `SystemMonitoringPanel` (`components/configuracoes/system-monitoring.tsx`) adicionado à página `/configuracoes`.
- **Verificação de E-mail Catch-All (Item 4.1)**:
  - `EmailVerificationService.probe_smtp_catchall`: probe SMTP ativo via `RCPT TO` configurável por opt-in (`enable_catchall_probe`). Mantém a análise 100% passiva por padrão (Lei 12.737/2012).
- **Validação Tátil em Dispositivos Móveis (Item 4.17)**:
  - Menu de ações rápidas ("Mover para"), drag-handle com `touch-none` e `MobileBottomNav` revisados para targets de toque `>= 44px`.
- **Verificação**: `compileall` OK, 342 testes pytest passando, `npm run lint`, `npx tsc --noEmit` e `npm run build` do Next.js 16 limpos.

### Qualificação Universal por Setor (Engenharia CAD, MDF/Troféus, ERPs, etc.) ✅ (2026-08-18)

Branch `feat/universal-sector-scoring`:

- **Enriquecimento Semântico de Conteúdo (`technical_enrichment_service.py`)**:
  - `_extract_domain_copy`: extrai títulos, meta description, H1/H2 e detecta dicionários de palavras-chave industriais/negócio (`keywords_mechanical` [usinagem, torno, CNC, caldeiraria, CAD/CAM, SolidWorks], `keywords_custom_craft` [MDF, troféus, chaveiros, acrílico, corte laser, brindes], `keywords_systems` [sistema, portal, ERP, área logada]).
- **Fatos de Negócio e Cadastrais Ampliados (`scoring_service.py`)**:
  - `extract_business_facts` e `extract_technical_facts` agora formatam a vocação operacional do prospect (capacidades industriais, CNAE, porte cadastral e trechos do site) para fundamentar a avaliação da IA.
- **Seeds e Templates por Arquétipo (`scoring_templates.py`)**:
  - `Engenharia Mecânica & Desenhos Técnicos CAD`: ignora métricas de SEO/SSL e prioriza vocação fabril, usinagem e porte industrial.
  - `Corte Laser, MDF & Produtos Personalizados (Troféus / Chaveiros)`: avalia demandas de premiação, eventos, sinalização e peças sob medida.
  - `Aplicações Web & ERPs`: prioriza ausência de área logada/portal e porte operacional, sem punir por falta de SEO.
- **Geração de Templates por IA (`template_generation_service.py`)**:
  - Prompt atualizado com diretrizes para os 5 Arquétipos (Presença Digital, Sistemas/ERPs, Engenharia/CAD, Fabricação/Produtos Personalizados [MDF, Troféus], Serviços Gerais).
- **Verificação**: `compileall` OK, suíte de 347 testes Pytest passando (incluindo `test_universal_scoring.py`), `npm run lint`, `npx tsc --noEmit` e `npm run build` do Next.js 16 limpos.

### Próximo passo imediato

> **Atualizado 2026-08-19** — onde paramos:
>
> 0. **Gerenciador de vertentes na UI (branch `feat/block3-vertentes-ui`):** nova
>    página `/configuracoes/vertentes` (sidebar Gestão) — criar vertente por IA
>    em linguagem natural como rascunho (`is_generated=True`, `is_active=False`),
>    duplicar uma vertente de fábrica (`source_template_id`), ativar/inativar,
>    excluir (409 se em uso); criar/editar/gerar/apagar só MANAGER+/owner/admin;
>    editor de template extraído do wizard (`template-editor.tsx`) e humanizado.
>    Backend: `POST /scoring-templates/generate` (rate-limit 15/min),
>    `DELETE /{id}` e duplicação no POST. **Verificação:** 381 tests, compileall
>    OK, web lint/tsc/build limpos.
>
> 0. **Operações reais + reanálise seletiva (branch `feat/reanalise-nao-pontuados`, PR #94):**
>    - **Base local inspecionada**: 20 leads (todos `QUALIFICADO`), 1 campanha
>      ("Landing pages - Academia - São Carlos"); 0 leads `NOVO`/score nulo.
>    - Seed idempotente rodado → **10 templates ativos**;
>      `reprocess_stuck_leads --fix-site-evidence` → **0 leads para reprocessar**
>      (no-op — nada preso nesta base).
>    - **Novo recurso**: `POST /campaigns/{id}/reanalyze?unscored_only=true`
>      reanalisa só leads sem pontuação (score NULL ou `NOVO`) — não queima cota
>      de IA re-pontuando o que já pontuou. Botão **"Reanalisar não pontuados"**
>      na página da campanha. Verificado: 279 tests, compileall OK, web
>      lint/tsc/build limpos.
>
> 0. **Inspeção geral (branch `fix/inspecao-geral`, PR #93):** revisão + regressão de
>    toda a suíte (307 teste) e das três camadas. Corrigido no frontend:
>    - `use-api.ts`: invalidação da cadência usava chave errada
>      (`["lead-cadence", id]` → `["leads", id, "cadence"]`) — o painel de
>      cadência não atualizava após gerar mensagens/editar variante;
>    - `types/index.ts` + `lib/api.ts`: `Campaign.scoring_template_id` agora
>      tipado (e PATCH devolve `Campaign` completo);
>    - `use-myOrganization` deduplicado com `useOrgMembership` (mesma chave
>      `["org","me"]` — antes havia dois fetches do `/orgs/me`);
>    - `today-actions.tsx`: "hoje" recalculado por render (não congela na
>      virada do dia);
>    - acessibilidade: `aria-label` em botões-icon (voltar, kebab de campanha,
>      remover sinal, menu de usuário).
>    - Verificado: `SelectItem value=""` é válido no Base UI (sem mudança);
>      `SelectValue` com função-rótulo é o padrão documentado. `pytest`,
>      `compileall`, lint/tsc/build limpos.
>
> 0. **Varredura geral + troca do modelo de LLM (branch `fix/sweep-bugs`):**
>    revisão completa do sistema encontrou e corrigiu:
>    - **LLM centralizado**: modelos agora vêm do `.env`
>      (`GROQ_MODEL_CLASSIFY`/`GROQ_MODEL_GENERATION`), sem constante espalhada
>      em 6 serviços (a descontinuação do modelo antigo motivou a troca);
>      segment/brief/router/geração de template migrados para
>      `provider_client.groq_json_chat` (pacing global + retry 429/5xx + cota)
>      — antes só scoring/outreach tinham isso; cota de `suggest-segment`/
>      `from-brief` corrigida (consumo central no provider, sem duplicar).
>    - **Críticos**: auto-envio de cadência quebrava por `NameError`
>      (`org_sends_today` → `sends_today`); `change-password` nunca gravava a
>      nova senha; import CSV com coluna de contato quebrava FK
>      (`bulk_save_objects` misto → `add_all` na ordem Lead→Contact, com
>      `imported_count` só de leads + novo `contacts_count`).
>    - **Altos**: playbooks (admin/owner não editavam — comparação de enum por
>      string); templates globais agora read-only via PATCH (400); **org
>      switcher real** — frontend envia `X-Organization-Id` (HTTP e WS) e o
>      backend resolve org/membership por ele (fallback p/ primeira).
>    - **Housekeeping**: imports `datetime` no topo de `leads.py`, `member`→
>      `target_member`, tipo de `_user`→`Organization` em `orgs.py`, `.is_(None)`.
>    - Verificação: **307 passed** (+22 testes), `compileall` OK, web lint/tsc/
>      build limpos.
>
> 0. **Erros de produção reportados (`docs/erros.md`, branch
>    `fix/erros-coleta-kanban-outreach`):** os 3 bugs que atrapalhavam a
>    operação corrigidos e verificados:
>    - **Coleta zerando (UniqueViolation):** `pipeline_worker` agora filtra a
>      2ª loja da mesma rede no lote (`filter_new_batch_items`) e insere com
>      `db.flush()` por lead em SAVEPOINT — um conflito isolado não derruba mais
>      o lote inteiro;
>    - **Kanban travando (MenuGroupContext):** labels dos dropdowns do kanban e
>      da lista de leads envoltos em `DropdownMenuGroup`;
>    - **"Falha ao gerar mensagem":** outreach migrado para
>      `provider_client.groq_json_chat` (pacing + retry 429/5xx + cotas) e
>      `max_tokens` 6000; rotas passam `db`/org e o consumo de cota ficou
>      centralizado.
>    - Verificação: **285 passed** (+9 testes), `compileall` OK, web lint/tsc/
>      build limpos.
>
> 0. **Leads score 0 + contatos de decisores (`feat/contatos-e-pontuacao-0`,
>    2026-08-16/17):** investigação de banco mostrou que os leads "score 0"
>    eram **NOVO nunca pontuados** — a coleta trazia uma página inteira
>    (pageSize=20) mesmo com `max_leads: 10` (overshoot), e o scoring só
>    processava 10. Correções:
>    - **A1** `places_service`: `max_results` respeitado dentro da página;
>    - **A2** `pipeline_worker`: seleção NOVO determinística + resumo do job
>      com `queue_remaining` (a UI avisa "N aguardando pontuação");
>    - **B1** Hunter **domain-search** implementado (rota já existia, nunca
>      usada): nomes/cargos/e-mails reais do domínio quando a Receita não tem;
>    - **B2** descoberta reversa de **CNPJ por nome** (busca passiva +
>      checksum) alimenta a Receita → sócios/decidores reais;
>    - **B3** regex de e-mail não captura mais URL/CDN (falso
>      `//unpkg.com/leaflet@1.7.1` era gravado como e-mail da Bluefit);
>    - **B4** fallback honesto: sem CNPJ o contato vira "Decisor" sem nome
>      inventado; heurística de e-mail só roda para nome real de pessoa.
>    - **Operacional (base local):** 10 leads NOVO re-pontuados → QUALIFICADO
>      (85–95); e-mail bugado removido. Suíte **276 passed**.
>
> 0. **Limpeza de docs (2026-08-17, `docs/cleanup-roadmaps`):** `docs/roadmap-leads.md`
>    **deletado** — 100% implementado (Partes A–E; histórico preservado neste
>    arquivo e em `decisions.md`). Referências sincronizadas
>    (`business-rules.md`, `roadmap-vendas.md`) e status do `roadmap-vendas.md`
>    unificados (4.17 → ✅; C2/C3 → "fix aplicado, falta rodar na base real";
>    §11 sem pendências do 4.17 que já foram entregues).
>
> > **Histórico anterior (2026-08-15):**
>
> 0. **P3 finalizado (2026-08-15, `fix/p3-review`):** em cima do P3 completo
>    (4.18–4.21, 4.26, 4.27 subset + review pass `d555c56`), fechada a lacuna de
>    **medição A/B real (4.19)** — `messages.variant` + `Message.is_response`
>    do inbound; `message_variants()` sem proxy. Também corrigido o teste de
>    threshold que o tie-break de F1 (limiar atual) havia quebrado. Suíte
>    **244 passed**. Pendência operacional: rodar `reprocess_stuck_leads
>    --apply --fix-site-evidence` na base real (C2/C3).
>
> 0. **Consultor dashboard + fechamento 4.17 (2026-08-15,
>    `feat/consultor-dashboard-mobile`):** KPIs da planilha Alphamec
>    (roadmap-leads C.2) por consultor — `pitch_sent`/`pitch_rate`,
>    `responded_leads`/`response_rate`, `contracts_approved`/`contract_approval_rate`,
>    `ticket_medio`/`ticket_count`, `avg_cadence_days`, `avg_close_days`,
>    `negotiation_distribution`, `contracts_by_outcome`, `channel_distribution`
>    — em `AnalyticsService.consultants()`; novos endpoints
>    `GET /analytics/consultants/{id}` (perfil: KPIs + funil ponta-a-ponta) e
>    `/analytics/consultants/{id}/activity` (trilha com filtro de período);
>    `GET /leads` aceita `consultant_id` (ANALYST/MANAGER/owner só, UUID
>    validado → 400). Web: `/relatorios/consultores/[id]` (KPIs, funil, trilha,
>    carteira buscável), card "Desempenho por consultor" com os rates da
>    planilha, **`MobileBottomNav`** + kanban com drag-handle isolado e fallback
>    "Mover para" por toque (fecham os pendentes do 4.17) e KPIs da planilha na
>    tabela de consultores do **PDF executivo**. Testes
>    `test_consultant_planilha_kpis.py` (8) + `test_consultor_acesso_restrito.py`
>    (10 — CONSULTOR convidado, não dono, tem 403 em analytics/BI/manager e
>    escopo restrito de leads). Suíte **264 passed**. Resta validar o DnD do
>    kanban em device real.
>
> **Histórico (2026-08-11):**
>
> 1. **Frontend — 3 temas + logo padrão** (apps/web): **Claro comum, Escuro e
>    AlphaMec** (padrão `alpha`). Logo oficial no login/registro (carrossel
>    Nortear/fotos + membros) e na sidebar/header via `brand-logo.tsx`.
> 2. **Correções levantadas em 2026-08-11** — ver `docs/roadmap-vendas.md §10`:
>    - **C1** Selects com valor cru (`web_presence` etc.) — **corrigido**.
>    - **C2** 53 leads presos em `ANALISADO`/score 0 (falha transitória do Groq);
>      fix aplicado (falha mantém `NOVO`) + script `reprocess_stuck_leads.py`
>      (validado; **rodar na base real**).
>    - **C3** IA alega "sem site próprio" em leads que TÊM site — fix aplicado
>      (prompt + guard determinístico + 5 testes); re-pontuar na base real.
>    - **C4** Leads sem site (público-alvo) voltam a pontuar após o C2.
>    - **C5** Decisão aberta: ERP/web apps — **recomendação registrada** no
>      roadmap-vendas §10 (criar template de categoria, sem terceiro perfil).
> 3. **LGPD removido dos docs/roadmap** (software interno): itens 4.11–4.13
>    retirados do backlog; menções neutralizadas. Features mantidas
>    (opt-out/STOP, exclusão de lead, CPF mascarado) + sinais comerciais
>    (Adequação LGPD/SEO do prospecto). Lei 12.737/2012 (passivo) preservada.
> 4. **Item 4.22 entregue (2026-08-11)** — LinkedIn assistido: `linkedin-query`
>    + `PATCH .../linkedin` (validação passiva, `manual:<user>`, action
>    `LINKEDIN_ASSOCIATED`) + Dialog guiado na aba Contatos. Testes (8).
> 5. **PR #68 mergeado (2026-08-11): 4.14–4.16 entregues** — cotas por org,
>    observabilidade/restore e paginação/índices (P2 confiabilidade fechado).
> 6. Próximos passos (backlog): **4.17 mobile-first** → **3.3.4** auditoria →
>    LinkedIn 4.23–4.25 → P3 (4.18–4.21, 4.26–4.27).
> 7. **PR #70 mergeado (2026-08-11):** setup/dev **Windows sem Docker**
>    (`setup.ps1`/`dev.ps1` + launchers `.cmd`), scoring "sem site = público-alvo"
>    (sinal no seed + instrução dinâmica + guard `has_website`) e fixes de UI.
>    Docs sincronizadas nesta sessão.
> 8. **4.11 entregue (2026-08-12, `feat/funnel-end-to-end`):** funil ponta-a-ponta
>    (achados → prospectados → responderam → reunião diagnóstica → fecharam) —
>    `AnalyticsService.funnel()` + `GET /api/analytics/funnel` (filtros
>    `from/to/campaign_id/consultant_id`), card "Funil ponta-a-ponta" no
>    `/relatorios` e seção no PDF executivo. Suíte em **140 passed**.
> 9. **Regra `PERDIDO`/90d implementada (2026-08-12, `feat/perdido-requeue-90d`):**
>    job em background (`_lost_requeue_loop` no `main.py`) re-enfileira
>    `PERDIDO → NOVO` após a carência (`LOST_REQUEUE_DAYS`, default 90) — perda
>    por ausência de resposta e não-`opt_out`; perdas deliberadas não voltam.
> 10. **Auto-`PERDIDO` no encerramento da cadência (2026-08-12,
>    `feat/cadence-auto-perdido`):** job (`_cadence_close_loop`) marca
>    `CONTATADO` → `PERDIDO`/`NAO_RESPONDEU` quando o `CLOSING` (dia 14) foi
>    enviado e não houve resposta em `CADENCE_CLOSE_GRACE_DAYS` (default 7) —
>    só transiciona `CONTATADO` e nunca marca `opt_out`. Fecha o ciclo do
>    `PERDIDO` com o requeue (item 9): entrada + saída automáticas.
> 11. **Pendências abertas:** **C5** (ERP/web apps) aguardando decisão da
>    diretoria; backlog → **4.17 mobile-first** → **3.3.4** auditoria →
>    LinkedIn **4.23–4.25** → P3 (4.18–4.21, 4.26–4.27).
> 12. **Sessão 2026-08-13 (apps/web):** correções de erros de console/hydration —
>    sessão pré-carregada no `SessionProvider` via `getServerSession` no
>    `layout.tsx` (elimina mismatch de hydration e warning de `defaultValue`);
>    `isActive` dos temas em `/configuracoes` agora guarda por `mounted`;
>    `next-themes` **substituído** por `components/theme-provider.tsx` próprio
>    (elimina aviso de `<script>` do React 19.2). Assets AlphaMec: logo
>    `logo-alphamec.png` (transparente) e foto `zenon.png` movidos de
>    `static/` para `apps/web/public/imgs/alphamec/`; `auth-shell.tsx` usa a
>    foto do Zenon; `logo-alphamec.webp` removido.
> 13. **Sessão 2026-08-13 — pipeline confiável + grounding + background
>    (`feat/background-pipeline-e-scoring-confiavel`):**
>    - **Frente C (rate-limit):** 18 de 20 leads de uma rodada ficaram sem score
>      por HTTP 429 da Groq (retry de 1.5s era inútil contra a janela de ~60s).
>      `provider_client.py` agora lê `Retry-After`/backoff exponencial
>      (`GROQ_MAX_RETRIES`, default 5) + **pacing global** entre chamadas
>      (`GROQ_MIN_INTERVAL_SECONDS`, default 20) → todo lead pontua; batch de 10
>      ≈ 4-5 min. Prompt de scoring enxuto (menos tokens = mais chamadas/min).
>      Feed honesto: `score: null`/`status:"falha"` quando não pontuou e summary
>      com `scored`/`failed` (acabou o "Score: 0 (analisado)" forjado).
>      `max_leads` default 10 (campanha + CNAE).
>    - **Frente A (grounding do pitch):** gancho de abordagem alegava "sem
>      responsividade"/"sem formulário/CTA"/"site atualizado" sem nenhuma
>      evidência (o enriquecimento nem media isso). Agora `_check_ux` mede
>      viewport/form/tel/WhatsApp/mailto (facts determinísticos), e o
>      `_normalize_response` valida cada alegação de risco contra as evidências
>      aprovadas; se reprovar, gera pitch determinístico da evidência mais forte
>      (sempre factual). Sinais do template clarificados como CRITÉRIOS.
>    - **Frente B (background de verdade):** coleta/enriquecimento saiu do
>      `asyncio.create_task` da request para um **job-consumer dedicado**
>      (`src/jobs_consumer.py`, loop no lifespan, claim atômico
>      `FOR UPDATE SKIP LOCKED`, um job por vez). Endpoints só agendam
>      (`status:"queued"`); `GET /api/pipeline/jobs` restaura status/resumo na
>      UI após sair/recarregar (banner "em andamento" + resumo Pontuados/Falhas);
>      log da UI limitado às últimas 150 linhas (anti-congelamento).
>    - **Próximo passo:** rodar seed (`python -m src.seeds.scoring_templates`) e
>      **"Reanalisar leads"** na campanha para pontuar os 18 leads que ficaram
>      `NOVO` por rate-limit antes do deploy desta correção.
> 14. **Sessão 2026-08-14 — pendências operacionais + C5
>    (`feat/erp-webapps-template-seed`):**
>    - **C5 fechado:** template de categoria **"Aplicações Web / ERP"** no seed
>      (mesmo perfil `web_presence`; sinais de processo manual/planilha vs.
>      portal/painel/API). Seed reaplicado → **7 templates ativos**. Testes
>      `tests/test_erp_template_seed.py` (5); suíte em **181 passed**.
>    - **Validação de fluxo (base local, 0 leads):** `reprocess_stuck_leads
>      --apply --fix-site-evidence` roda limpo (0 leads — no-op); seed OK.
>    - **PENDENTE na base real** (chaves `GROQ_API_KEY`/`GOOGLE_API_KEY` e dados
>      não disponíveis nesta máquina): rodar
>      `python -m src.scripts.reprocess_stuck_leads --apply --fix-site-evidence`
>      (C2/C3 — 56 leads) e reanalisar os 18 leads `NOVO` por rate-limit
>      (seed + `POST /campaigns/{id}/reanalyze`). Comandos documentados no
>      `roadmap-vendas.md §11`.
> 15. **Sessão 2026-08-14 — 4.17 mobile-first portado p/ `main`
>    (`feat/mobile-first-4-17`):**
>    - **Porta seletiva** do commit original (baseado no PR #68) sobre `main`
>      atual — só a parte responsiva útil; os assets/auth-shell (já entregues
>      no PR #76) e o hunk de regressão do `sortByOptions` foram **excluídos**.
>    - Arquivos: `ui/dialog` (max-h+scroll), `ui/tabs` (overflow/w-max),
>      `kanban-board` (touch targets 44px + flex-wrap + dica mobile),
>      `lead-list` (presets/ações `h-9 sm:h-8` + flex-wrap), `campanhas/[id]`,
>      `oportunidades/[id]`, `campaign-list`, `brazil-state-map`.
>    - Verificação: `npm run lint`, `npx tsc --noEmit` e `npm run build` limpos.
>    - Pendente (próximo ciclo): bottom-nav opcional, DnD em touchscreen,
>      validação em device real.
> 16. **Sessão 2026-08-14 — auditoria de membros e acessos (3.3.4)
>    (`feat/org-audit-backend`, backend only):**
>    - Tabela `org_audit_log` + enum `OrgAuditEvent` (14 eventos) — migration
>      `bff05fb7eb01` aplicada.
>    - `org_audit_service`: `log_org_event` (actor denormalizado) +
>      `list_org_audit`; nunca grava valor de secret (só `key_name`).
>    - Instrumentado em `orgs.py` (create/rename/settings, sales_role,
>      remove/leave/transfer-owner, secrets, sales-targets) e `invites.py`.
>    - `GET /orgs/{org_id}/audit-log` — MANAGER/owner/admin, filtro por evento.
>    - Testes `tests/test_org_audit.py` (7) — suíte em **188 passed**.
>    - Pendente: UI da tabela de auditoria em `/configuracoes/membros` (PR
>      futuro), limpeza de comentários/docstrings com etiquetas de roadmap.
>
> 17. **Sessão 2026-08-14 — templates de e-mail com identidade AlphaMec**
>    (`feat/org-audit-backend`, backend only):
>    - Novo `services/api/src/services/email_templates.py` — shell HTML padrão
>      da indústria (tabelas 600px, preheader, CSS inline + dark mode via
>      `prefers-color-scheme`/`[data-ogsc]`, botão CTA com fallback MSO/Outlook,
>      typo system-stack) com a paleta vinho `#910001/#4c0000`, marca do radar.
>    - **Cadência/outreach** (`_build_html_tracked`) agora usa template discreto
>      com assinatura do remetente — antes era `<p>` sem marca.
>    - **Reset de senha** ganhou HTML transacional com CTA.
>    - **Convite** passou a ser **enviado de fato** (`POST /orgs/{org_id}/invites`
>      chama `send_invite_email` com link `{APP_BASE_URL}/aceitar-convite`) —
>      antes o docstring dizia que enviava, mas nenhum e-mail saía.
>    - Testes `tests/test_email_templates.py` (5) — suíte em **193 passed**.
>
> 18. **Sessão 2026-08-14 — UI da auditoria 3.3.4 (`feat/org-audit-ui`):** fecha
>    o ciclo do item 3.3.4 (o backend veio na sessão 16):
>    - `orgsApi.listAuditLog` + hook `useOrgAuditLog` + tipos `OrgAuditEvent`/
>      `OrgAuditEntry`; componente `OrgAuditLog` (filtro por evento, tabela
>      Quando/Evento/Quem/Detalhe, estados de carga/erro/vazio) montado em
>      `/configuracoes/membros`. `tsc --noEmit`, `eslint` e `build` limpos.
>    - `docs/agents.md` reescrito como runbook completo ("/init melhorado"):
>      fluxo graphify-first, matriz de skills por tarefa, convenções, regras de
>      negócio, verificação por camada, DoD e pitfalls operacionais.
>    - **Decisão de produto em aberto:** a página `/configuracoes/membros` é
>      owner/admin-only; MANAGER acessa `GET /orgs/{id}/audit-log` por API mas
>      não tem a tabela na UI (expor para MANAGER = decisão separada).
>
> 19. **Sessão 2026-08-14 — limpeza de comentários de rastreio:** removidas de
>    código/UI/testes as referências a itens de roadmap ("Item 4.x", "Fase X.Y",
>    "(4.2)", "roadmap-leads C.3"), datas de entrega e numerações — comentários
>    viraram concisos e descritivos. Migrations **não** foram tocadas (regra).
>    Regra nova gravada no `docs/agents.md` §3 e no `AGENTS.md` (proibido
>    rastreio de item/sessão/PR em comentários, docstrings e textos da UI).
>
> 20. **Sessão 2026-08-14 — nomenclatura de UI ("SLA" → PT-BR):** removida a
>    sigla "SLA" dos textos visíveis (kanban, "Ações de hoje", Configurações):
>    passou a usar "leads parados", "Prazos de atendimento" e o badge
>    "Parado há Xd". Identificadores de código/API (`sla_*`, `SlaAlertItem`,
>    endpoints) ficam inalterados por contrato de dados.
>
> 21. **Sessão 2026-08-14 — 4.24 match semântico + fechamento 3.3.4/3.3.5
>    (`feat/linkedin-match-semantico`):**
>    - **4.24:** `linkedin_match_status(url, source, confidence)` (puro, em
>      `linkedin_assist_service`) → NOT_FOUND/CANDIDATE/NEEDS_REVIEW/VERIFIED;
>      exposto em `_contact_to_dict`; badge semântico na aba Contatos
>      (Confirmado/Revisar/Candidato) no lugar do limiar de 50%. Testes (6) —
>      suíte em **199 passed**.
>    - **3.3.5 (decisão):** MANAGER define `sales_role` (`PATCH /members/{id}`
>      agora `require_manager`); convites/remoção/transferência/chaves/metas
>      continuam owner/admin-only.
>    - **3.3.4 (decisão):** `/configuracoes/membros` liberada para MANAGER —
>      vê membros + auditoria; cria convites/metas e ações admin ficam só para
>      owner/admin.
>    - **Limpeza:** docstrings das migrations sem referências a Fase/Item/
>      Roadmap/sprint (só texto; `revision`/código intactos).
>
> 22. **Sessão 2026-08-14 — 4.23 LinkedIn da empresa (company page)
>    (`feat/linkedin-empresa`):**
>    - Migration `d4e5f6a7b8c9` — `leads.company_linkedin_url` (aplicada no
>      Postgres local).
>    - `ContactEnrichmentService`: busca passiva `"<empresa>" linkedin`
>      (DuckDuckGo→Bing) no enriquecimento + helpers puros
>      `extract_linkedin_company_slug` / `pick_linkedin_company_url` (exige
>      overlap mínimo de 1 termo — nunca associa company page sem relação).
>    - API: `company_linkedin_url` em `_lead_summary` e no `identity` do pitch.
>    - UI: link "Empresa no LinkedIn" em "Informações do Lead" e no card de
>      Identidade do Pitch One-Pager.
>    - Testes `tests/test_linkedin_company.py` (5) — suíte em **204 passed**.
>
> 23. **Sessão 2026-08-14 — 4.25 estado do enriquecimento + TTL**
>    (`feat/enrichment-ttl`):
>    - Migration `e6f7a8b9c0d1` — `leads.enrichment_timestamps` (JSONB por
>      fonte: linkedin/site/reviews). Aplicada no Postgres local.
>    - `services/enrichment_ts.py` (fonte única, workers): `TTL_HOURS`
>      (LinkedIn 30d · site 7d · reviews 24h), `read/get/stamp`, `is_fresh` e
>      `freshness_snapshot`.
>    - Gate real de idempotência: contato/empresa LinkedIn não re-busca dentro
>      de 30d (TTL); orquestrador carimba `site` (pós análise técnica) e
>      `reviews` (quando há rating).
>    - API: `enrichment_freshness` (fresh/stale/never) no detalhe do lead;
>      UI: aviso "Dados antigos" (LinkedIn/análise do site/avaliações) em
>      "Informações do Lead".
>    - Testes `tests/test_enrichment_ttl.py` (5) — suíte em **209 passed**.

### Item 4.11 — Funil ponta-a-ponta ✅ (2026-08-12)

Branch `feat/funnel-end-to-end` (pedido da diretoria, roadmap-vendas 4.11):

- **Backend:** `AnalyticsService.funnel()` — etapas cumulativas ("pelo menos"):
  achados → prospectados (status de contato + `FollowUp.sent_at` +
  `Message.sent_at`) → responderam (+ `Message.is_response`) → reunião
  diagnóstica (+ `LeadActivity` STATUS_CHANGED→REUNIAO_MARCADA/MEETING_SCHEDULED)
  → fecharam (`Conversion`). `build_funnel_stages` calcula conversão entre
  etapas e % do total (função pura). Endpoint `GET /api/analytics/funnel`
  (ANALYST/MANAGER-only, org-scoped) com filtros `from/to/campaign_id/consultant_id`.
- **Frontend:** card **"Funil ponta-a-ponta"** em `/relatorios` (barras que
  afunilam em degradê teal + conversão entre etapas e "vazou X%").
- **PDF executivo:** seção "Funil ponta-a-ponta (achados → fechamento)" com
  leads, conversão (etapa anterior) e % do total.
- **Testes:** `tests/test_analytics_funnel.py` (6) — suíte em **140 passed**;
  `compileall` OK; web lint + `tsc --noEmit` + `npm run build` OK.

### Regra `PERDIDO` volta à fila (90 dias) ✅ (2026-08-12)

Branch `feat/perdido-requeue-90d` (business-rules — fechada a pendência):

- **Job:** `_lost_requeue_loop` no `services/api/main.py` (lifespan), poll
  `LOST_REQUEUE_POLL_SECONDS` (default 1h), carência `LOST_REQUEUE_DAYS`
  (default 90; 0 desativa). `services/requeue_service.py` —
  `requeue_expired_lost(db, now, days)`, elegibilidade em Python:
  `_is_time_based_loss` (nulo/`NAO_RESPONDEU`) + não-`opt_out`.
- **Data de perda:** última `LeadActivity` `status_to=PERDIDO` (fallback
  `Lead.updated_at`). Destino `NOVO`, limpa `lost_reason`, mantém consultor
  atribuído e registra trilha `STATUS_CHANGED PERDIDO→NOVO`.
- **Decisão registrada:** perdas deliberadas (`PRECO/CONCORRENTE/PRAZO/OUTRO`)
  não reabrem automaticamente.
- **Testes:** `tests/test_requeue_lost.py` (14).

### Auto-`PERDIDO` no encerramento da cadência ✅ (2026-08-12)

Branch `feat/cadence-auto-perdido` (business-rules — fecha o ciclo do
`PERDIDO`; o requeue acima é a "saída", este é a "entrada"):

- **Job:** `_cadence_close_loop` no `services/api/main.py` (lifespan), poll
  `CADENCE_CLOSE_POLL_SECONDS` (default 1h), carência
  `CADENCE_CLOSE_GRACE_DAYS` (default 7; 0 desativa).
  `services/cadence_close_service.py` — `close_expired_cadences(db, now, grace_days)`
  com guardas em Python (`_grace_elapsed` + status/opt-out).
- **Regra:** quando o `CLOSING` (dia 14) foi **enviado** e o lead segue
  `CONTATADO` sem resposta após a carência → `PERDIDO`/`NAO_RESPONDEU`.
  Nunca sobrescreve `RESPONDIDO+`/reunião/proposta e nunca marca `opt_out`.
- **Trilha:** STATUS_CHANGED + action `LOST` — alimenta a data de perda usada
  pelo requeue de 90 dias.
- **Testes:** `tests/test_cadence_close.py` (12).
- **Decisão registrada:** comportamento automático (antes usado manual); o
  consultor continua podendo reverter status (transições não são travadas).

### Gaps residuais do roadmap-leads (branch `fix/lead-scoring-residuals`, 2026-08-05)

Após o merge do PR #47 (S1–S4 no `main`), fechados os dois gaps que ainda
atrapalhavam prospecção:

- **CSV import tratava Canva/WhatsApp/marketplace como "tem site"**: `csv_import_service`
  usava só `normalize_domain` (dedupe) e gravava `website` no lead — lead via CSV com
  `canva.link`/`api.whatsapp.com` era enriquecido tecnicamente e a LLM inventava dor de
  site (P3 reincidindo). Fix: novo helper `normalize_import_website()` (anula via
  `is_social_domain`, mesmo comportamento de `places_service`); `website=None` → o lead
  vira "sem site" e é pontuado pelo caminho business em campanhas web (P4).
- **S5 sem depender de reset do banco**: novo script one-off
  `src/scripts/fix_generated_web_templates.py` (idempotente, dry-run por padrão) que
  detecta templates `is_generated=True` ainda com "presença online/site próprio" como
  sinal positivo (assinatura pré-S1), desvincula as campanhas e as realinha ao seed
  global "Desenvolvimento de Sites", e exclui o template corrompido — sem tocar em
  leads. Para a operação real: `POST /api/campaigns/{id}/reanalyze` nos leads impactados.

**Verificado**: smoke determinístico (CSV + S3 domains) e detecção do script OK;
`py_compile` limpo; novos testes `test_normalize_import_website_*` e
`tests/test_fix_web_templates.py`.

### Quick wins do roadmap-vendas (2026-08-05) — 4.4 e 4.6

Close dos itens P0 (4.4) e P1 (4.6) de `docs/roadmap-vendas.md`, em branches
prontas p/ merge (PR #49/#50):

- **4.4 Threading completo** (`fix/threading-chain`): `_thread_headers` em
  `cadence_service.py` passa a acumular **toda a cadeia** de Message-IDs das
  etapas anteriores em `References` (ordem cronológica) e `In-Reply-To` = mais
  recente (antes: só o último). Exigência do Gmail/exchange para agrupar
  conversa. Teste `tests/test_cadence_threading.py` (db fake).
- **4.6 Rating/reviews no scoring** (`feat/places-rating-scoring`):
  `places_service` coleta `rating`/`userRatingCount`/`googleMapsUri`;
  `leads.google_rating`/`google_rating_count`/`google_maps_uri` (migration
  `d8e9f0a2b3c4`) persistidos na coleta; `extract_business_facts` vira
  evidência "Reputação Google: X.Y★ com N avaliações" no scoring; exposto no
  pitch one-pager e no summary do lead. Teste `tests/test_places_rating.py`.

**Verificado**: `py_compile` dos tocados OK; smokes dos dois (threading 6,
rating 4) OK.

### Tracking de abertura/clique (roadmap-vendas 4.2, branch `feat/email-tracking`, 2026-08-05)

Sinal mais quente de cold outreach (quem leu/clicou), antes inexistente.

- **Modelos/migração `e2f3a4b5c6d7`**: `messages.tracking_token` (unique),
  `messages.opened_at`, `messages.clicked_at`; `follow_ups.tracking_token`.
- **Rotas públicas** (`routes/tracking.py`, registradas sem `/api` — o cliente
  de e-mail acessa): `GET /t/{token}` → pixel 1×1 grava `opened_at` (token
  desconhecido não quebra o e-mail); `GET /c/{token}?url=` grava `clicked_at` e
  redireciona (302); valida http(s).
- **Injeção** (`email_service`): `send_email` ganhou `tracking_token`; quando
  `settings.TRACKING_BASE_URL` está configurada, anexa a parte **HTML** com
  pixel + links reescritos para o redirect (texto puro intacto). Sem base → só
  texto (tracking off em dev).
- **Cadência** (`cadence_service.send_step`): gera `tracking_token` por etapa e
  persiste no `FollowUp`; o `Message` criado carrega o mesmo token.
- **API**: `GET /leads/{id}/cadence` expõe `opened_at`/`clicked_at` por etapa.
- **Frontend**: badge "abriu"/"clicou" no `CadencePanel` (detalhe do lead);
  `FollowUpItem` ganhou os campos. `tsc --noEmit` e eslint limpos.
- Testes `tests/test_email_tracking.py` (5) OK.

> Deploy: definir `TRACKING_BASE_URL` (domínio público da API) para ativar.

**Vistoria geral concluída (2026-08-04)** — pendências mapeadas e corrigidas na
branch `fix/go-live-prep` (abaixo). Prioridade para o go-live:

1. **Bloqueadores**: corrigir crash de CSV/CNAE (`Lead.name/cnpj/address`
   ausentes), completar requirements.txt (API e workers) e parar a rajada da
   cadência no `auto_send_email`.
2. **Prontidão mínima**: deploy (compose + proxy/TLS + README), smoke tests,
   backup pg_dump — antes de colocar a empresa para prospectar.
3. **Eficácia**: kanban clicável, bounce handling, inbound STOP, gate de
   e-mail heurístico.

**Eixo 3 entregue (2026-08-04)** — kanban NOVO/QUALIFICADO, notas + próxima ação
no lead, painel "Ações de hoje", ações em massa + exportar CSV, WhatsApp wa.me.
Próximos eixos sugeridos: **Eixo 1 (volume: CNAE real, CNPJ automático p/ Places,
pontuar sem site)** e **Eixo 4 (UI/UX: master-detail no lead, dashboard central
de comando, filtros/paginação)**.

### Correção go-live (branch `fix/go-live-prep`, 2026-08-04)

A vistoria gerou a branch `fix/go-live-prep` com correções. Entregue até aqui:

- **Bloqueadores**: CSV e coleta CNAE corrigidos (colunas `leads.name/cnpj/
  address/normalized_domain` + migration `a5b6c7d8e9f0`); requirements.txt
  completos e pinados (API + workers, cryptography adicionado, playwright
  removido); rajada da cadência eliminada (o scheduler `run_due` respeita
  `scheduled_at`).
- **E-mail**: bounce handling (`follow_ups.attempts/message_id` + tabela
  `email_suppressions`, migration `b6c7d8e9f0a1`), threading headers,
  remetente por org (`organizations.email_from`), e-mail heurístico não sai
  no envio automático, sem corpo de e-mail em logs, SMTP síncrono fora do
  event loop.
- **Inbound (3.3)**: `POST /api/webhooks/email/inbound` detecta resposta
  (→ `RESPONDIDO`, cancela cadência) e STOP (→ `opt_out`).
- **API**: rate limits nos endpoints de custo, cap de CSV (10MB/10k linhas),
  `max_leads` limitado a 200, WS com auth na 1ª mensagem (sem token na URL),
  error-shape `detail` no frontend, `PATCH /leads/{id}` (notas/whatsapp/
  next_action), `DELETE /leads/{id}` (exclusão do lead), CORS/settings por env,
  `/health` com ping no banco, N+1 reduzido (leads/campaigns), código morto
  removido.
- **Segurança/privacidade**: CPF mascarado + `raw_data` de contatos saneado;
  remoção da varredura de caminhos sensíveis (só robots/sitemap).
- **Scoring**: evidência com origem "inferência LLM" filtrada; `evidence_ref`
  validado; leads sem site agora são pontuados (business) em vez de
  descartados.
- **Frontend**: kanban abre o lead, "Enviar mensagem" funcional, menu de
  campanha operacional (pausar/duplicar/rodada/arquivar), debounce na busca,
  CSP de prod com origem da API/WS, lint + typecheck + build limpos.
- **Deploy/ops**: Dockerfiles (api/workers/web standalone), `docker-compose`
  com os 4 serviços, README, `.env.example` atualizado, backup
  `scripts/backup.sh`, pytest (27 testes) + CI (`ci.yml`), `provider_client`
  compartilhado (5.1 parcial).

Pendente de validação: rodar migrations em Postgres real, build das imagens
Docker e o CI.

### Limpeza de docs (2026-08-04)

Removidos da pasta `docs/` por estarem finalizados/superados: `roadmap.md`
(→ `roadmap-combined.md`), `tracking.md` (→ `context.md`), `evolution-analysis.md`,
`product-vision.md` (→ `roadmap-combined.md`), `interface.md`.
Em `2026-08-04` também foram removidos (todos os itens entregues): `roadmap-combined.md`
(roadmap totalmente ✅) e `auditoria.md` (vistoria go-live); o vistoria está
resumido acima em "Próximo passo imediato".
Canônicas atuais: `context.md`, `architecture.md`, `business-rules.md`,
`decisions.md`, `coding-standards.md`, `agents.md`.

### Eixo 3 — Fluxo de vendas "Apollo" (itens 9–12) ✅ (2026-08-04)

Pacote de melhorias de execução de vendas sobre a branch `fix/go-live-prep`:

- **Item 9 — Kanban com NOVO + QUALIFICADO**: `/vendas` agora tem as colunas
  `Novos` e `Aptos para contato` antes de `Mensagem enviada`. Cards ordenados por
  score (depois prioridade HOT>WARM>COLD) dentro de cada coluna. Badge "Sem score"
  para NOVO; indicador "Aguardando 1º contato" em QUALIFICADO.
- **Item 10 — Notas + próxima ação + fila de ações**:
  - Card **Acompanhamento** no detalhe do lead (componente `FollowUpCard`):
    WhatsApp, próxima ação (datetime-local) e notas editáveis → `PATCH /leads/{id}`
    (backend já aceitava; UI criada). Nada de `setState` em effect (padrão child
    com estado inicializado do lead).
  - Painel **"Ações de hoje"** no dashboard (`today-actions.tsx`): follow-up
    vencido/hoje (via `next_action_before`) + aptos sem dono (via `assigned=none`)
    com botão "Atribuir a mim".
  - Backend: `GET /api/leads` ganhou filtros `assigned` (`me|none|any`) e
    `next_action_before` (data simples vira fim do dia).
- **Item 11 — Ações em massa na lista de leads**: seleção por card + "selecionar
  todos visíveis"; barra de ações com **atribuir a mim**, **atribuir para**
  (consultores da org, MANAGER+), **mover para** (status) e **exportar CSV**
  (client-side, BOM UTF-8 p/ Excel BR).
- **Item 12 — WhatsApp**: helper `toWhatsAppNumber`/`whatsAppLink` em `lib/utils.ts`;
  botão WhatsApp no kanban, no cabeçalho do lead e **"Abrir no WhatsApp"** no modal
  de mensagem gerada (abre `wa.me` com `whatsapp_short` preenchido).

**Verificação:** `tsc --noEmit` limpo, `npm run lint` limpo, `npm run build` OK,
`py_compile` do `routes/leads.py` OK. Testes pytest requerem venv (não instalado).

### Bugfix — contrato `role` maiúsculo (2026-08-04)

- Sintoma: usuário owner via "Apenas o dono ou administrador..." na página de
  membros e no toggle de envio automático; não conseguia gerenciar nada.
- Causa: o backend serializava `OrganizationRole` pelo valor do enum no banco
  (`"owner"`/`"admin"`/`"member"`, minúsculo), mas o tipo TS `OrgRole` e todas
  as comparações do frontend usam maiúsculo (`'OWNER'`/`'ADMIN'`). Com isso
  `canManage` nunca era verdadeiro para o próprio dono. Criação de convite
  também enviava `"MEMBER"` maiúsculo, rejeitado pelo Pydantic.
- Fix: `routes/orgs.py` (`_member_dict`, `/orgs/me`, `/orgs/my-organizations`)
  e `routes/invites.py` (`_invite_dict`, aceite) passam a serializar `role` com
  `enum.name` (OWNER/ADMIN/MEMBER). `CreateInviteRequest.role` ganhou
  `field_validator` que aceita maiúsculo e minúsculo. `SalesRole` já era
  maiúsculo — inalterado. Banco continua com valores minúsculos (nada a migrar).
- Testado via API real: `/orgs/me` → `"role":"OWNER"`; convite com `"MEMBER"` → 200.

### Bugfix — colisão `normalized_domain` de redes sociais (2026-08-04)

- Ao coletar campanha (ex.: crossfit em Araraquara), negócios sem site próprio
  têm `website` = perfil social (Instagram/Facebook) e todos normalizavam para
  `normalized_domain='instagram.com'`, violando `uq_leads_org_normalized_domain`
  e fazendo o batch inteiro falhar (rollback, 0 leads salvos).
- Fix: `domain_utils.normalize_domain` agora retorna `None` para domínios sociais
  genéricos (`_SOCIAL_DOMAINS`: instagram/facebook/linkedin/x/twitter/youtube/
  wa.me/whatsapp/linktr.ee/tiktok/behance/medium/blogspot/wixsite/business.site),
  mantendo a dedupe por `place_id`/CNPJ e por domínio próprio. Testes
  `test_domain_utils.py` ampliados (8 passando).

### Ambiente local sem root — sessão atual (2026-08-04)

Máquina de trabalho (usuário `aluno`, sem sudo/Docker) — ambiente inicializado
de novo nesta sessão:

- **Grafo do código gerado**: `graphify-out/graph.json` (1543 nós, 3676 arestas,
  117 comunidades) via `graphify extract . --code-only && graphify cluster-only . --no-label`.
  CLI em `/tmp/opencode/graphify-venv`. Relatório: `graphify-out/GRAPH_REPORT.md`.
- **`scripts/setup.sh` rodado com sucesso (idempotente, sem root)**:
  - PostgreSQL 16 embarcado (zonky) em `~/.local/agente-prospeccao` — 127.0.0.1:5432
  - venvs `services/workers/venv` + `services/api/venv` com requirements instalados
  - `.env` na raiz criado (JWT_SECRET gerado; chaves de API vazias)
  - banco `agente_prospeccao` criado; `alembic upgrade head` OK (todas as migrations até `b6c7d8e9f0a1`)
  - seed de 9 templates de scoring OK; `apps/web/.env.local` + `npm ci` OK
- **`scripts/dev.sh start` no ar**: PostgreSQL, API (`/health` → `{"status":"ok","database":"ok"}`)
  e Web (login em `http://localhost:3001`, 200).

Pendente: preencher `GROQ_API_KEY` e `GOOGLE_API_KEY` no `.env` da raiz (e
`HUNTER_API_KEY` opcional) e reiniciar a API para coletar/qualificar leads.

### Ambiente local sem root (2026-08-04)

Máquina de trabalho sem sudo e sem Docker. Setup validado:

- **PostgreSQL 16 embarcado**: binários zonky (Maven Central,
  `io.zonky.test.postgres:embedded-postgres-binaries-linux-amd64:16.14.0`)
  extraídos em `~/.local/agente-prospeccao/` (`bin/`, `pgdata/`, `pg.log`).
  `initdb` com auth `trust`, porta 5432, só `127.0.0.1`. Sem `psql` (os
  binários zonky não trazem clientes — usar o Python/psycopg2).
- **`.env` na raiz** criado (gitignored): `DATABASE_URL`, `JWT_SECRET` gerado,
  placeholders vazios para `GROQ_API_KEY`/`GOOGLE_API_KEY`/`HUNTER_API_KEY`.
- **venvs**: `services/workers/venv` e `services/api/venv` (deps instaladas).
- **Migrations + seed**: `alembic upgrade head` OK (após corrigir in-place o
  backfill de `normalized_domain` da migration `a5b6c7d8e9f0` — ver seção
  "Ambiente local sem root" abaixo); seed de 9 templates OK.
- **Web**: `.env.local` com `NEXTAUTH_SECRET` (NextAuth JWT).
- **`scripts/dev.sh`**: `start|stop|status` para Postgres + API + Web.
- Usuário inicial criado: `admin@agente-prospeccao.com` (trocar a senha).

### Sessão atual — grafo + limpeza de docs (2026-08-04)

- **Grafo atualizado**: `graphify extract . --code-only && graphify cluster-only .`
  → `graphify-out/graph.json` (1562 nós, 3813 arestas, 109 comunidades; backup
  do grafo anterior em `graphify-out/backups/2026-08-04/`).
- **Docs removidas**: `CLAUDE.MD` (apontava para `docs/roadmap.md` deletado e
  estado da Fase 1), `docs/roadmap-combined.md` (100% entregue) e
  `docs/auditoria.md` (vistoria go-live já aplicada). Referências a elas foram
  removidas de `context.md` e `README.md`.
- **`docs/architecture.md` reescrita** para o estado atual (orgs/papéis, BI+PDF,
  CSV/CNAE, cadência+inbound, BYOK, WS com auth, endpointos reais).
- **`docs/agents.md`**: caminho do grafo corrigido para `graphify-out/graph.json`
  (era `.ua/knowledge-graph.json`); removido `/add` (convenção Claude).
- **`docs/coding-standards.md`**: orquestração corrigida — exceção documentada
  em `enrichment_orchestrator.py` (antes dizia "só no main.py").
- **`docs/roadmap-vendas.md` (novo)**: mapa-norte de evolução para a EJ —
  diagnóstico do multi-org/papéis (gaps: criar/renomear org, onboarding de
  convidado sem conta, remover/transferir membro, metas/forecast) + backlog
  completo de entregabilidade, WhatsApp, dados, gestão e confiabilidade.
  Regra preservada: **CONSULTOR mantém autonomia de criar/gerenciar campanhas**.

### Entregável 1 — Verificação de e-mail (roadmap-vendas 4.1) ✅ (2026-08-04)

Branch `feat/email-verification`. Fase 0 — entregabilidade:
- `EmailVerificationService` (`services/workers/src/services/email_verification_service.py`):
  sintaxe + blocklist de domínios descartáveis + **MX via Cloudflare DoH**
  (sem dependência nova); fail-closed.
- Migration `c7d8e9f0a1b2`: `contacts.email_verified` (default false) +
  `contacts.email_verified_at`.
- `contact_enrichment_service` roda a verificação após o e-mail; **heurístico
  nunca é marcado verificado** (padrão não comprovado). Badge "E-mail
  verificado"/"Não verificado" na aba Contatos (`email_verified`/
  `email_verified_at` expostos em `_contact_to_dict` da API e workers).
- `cadence_service:_recipient_email`: envio **automático** exige
  `email_verified=True` (fail-closed para dados legados sem o campo).
- Verificado: `py_compile` OK; `tsc --noEmit` limpo; smoke test real (MX
  gmail → verificado; domínio inexistente/descartável/sintaxe → não verificado).
- ⚠️ Catch-all não implementado (probe SMTP é não-passivo — decisão de produto).


### Bugfix — Web caía / 500 após `dev.sh stop && start` (2026-08-05)

Sintoma: após `stop && start`, o web mostrava `rodando` e em seguida `PARADA`, e
o acesso a `http://localhost:3001` dava 500 ("Internal Server Error").

**Duas causas distintas corrigidas:**

1. **Root errado do Turbopack** (500 ao carregar): um `package-lock.json` órfão em
   `~/` fazia o Next 16 inferir o workspace root como `/home/aluno` em vez de
   `apps/web`, quebrando a resolução de módulos do `next/*`
   (`next/dist/server/app-render/work-async-storage.external.js` — MODULE_NOT_FOUND).
   - Fix: `apps/web/next.config.ts` ganhou `turbopack: { root: __dirname }`; órfão
     `~/package-lock.json` removido; cache `.next/` limpo.
   - CUIDADO: o órfão `~/package-lock.json` é reaparecia/estava lá com mtime antigo
     — o `rm` inicial não chegou a rodar (timeout). Reconfirmado e removido.
   - O cache persistente do Turbopack servia chunks corrompidos mesmo após
     `stop/start`; `web_start` agora remove `~/.../apps/web/.next` antes de subir
     (compilação sempre limpa). `turbopackFileSystemCacheForDev` existe no tipo TS
     mas a validação do Next 16.2.10 NÃO a reconhece (warning "Invalid next.config")
     — então não é usada; o `rm -rf .next` no start cobre.
   - API (separado): `SMTP_PORT=` (vazio) no `.env` sobrescrevia o default 587 e
     quebrava o pydantic no boot — setado para `587`.

2. **`dev.sh` não reconhecia/derrubava o web** (web "PARADA" sem motivo): o
   processo real do Next se chama `next-server (v1...)`, que NÃO casa com o
   padrão `next.*dev` usado em `web_is_up`/`web_stop` (pgrep/pkill). Após um
   `stop`, um `next-server` órfão ficava segurando a porta 3001, e o `start`
   reportava "Web já está rodando" sem subir nada.
   - Fix em `scripts/dev.sh`: detecção/parada passam a ser **por porta** via um
     novo helper `port_pids()` (`ss -ltnp`), e `web_start` usa `setsid` para
     desprender o processo. `api_is_up`/`web_is_up`/`status`/`stop` consistentes.

Estado após a correção: Postgres, API (200 em `/docs`) e Web (200 → `/login`)
subindo e estáveis via `scripts/dev.sh start`.

### Bugfix — JWT_SESSION_ERROR "decryption operation failed" ao criar conta (2026-08-05)

Sintoma: após criar a conta e o auto-login, o redirect para `/dashboard`
falhava com `[next-auth][error][JWT_SESSION_ERROR] "decryption operation
failed"` em `ProtectedLayout` (RSC).

Causa: `apps/web/.env.local` não tinha `NEXTAUTH_SECRET` (o log mostrava
`[next-auth][warn][NO_SECRET]`). Sem secret fixo, o NextAuth gera um aleatório
**em memória por processo** — o cookie do login é criptografado no route handler
e, no render seguinte, o RSC usa outro secret → falha na descriptografia.

Fix: `NEXTAUTH_SECRET` estável adicionado ao `apps/web/.env.local` (gitignored,
gerado com `openssl rand -base64 32`). Documentado em `/.env.example` (seção
Web, rastreado) para não regredir. Requer restart do web para ler o env; cookie
antigo (do secret perdido) fica inválido e o login precisa ser refeito.

### Novo roadmap — leads/scoring/funil (2026-08-05)

Criado `docs/roadmap-leads.md` (mapa-norte): documenta as **soluções propostas**
para 4 problemas de qualificação (template invertido, pitch "matrícula" copiado
do exemplo do prompt, domínios de ferramenta/marketplace tratados como site
próprio, lead sem site nunca pontuado em campanha web) e a **análise da planilha
Alphamec** (`docs/planilha_alphamec_atual.xlsx`) + plano de adaptá-la ao sistema.

**Decisões registradas**: não reanalisar dados atuais (teste); `canva`/
`api.whatsapp.com`/marketplaces = "sem site próprio"; **pontuar leads sem site**
em campanhas `WEB_PRESENCE` (muda regra "sem site fica NOVO"). Funil interno
`RD/ORÇAMENTO/RP` e `CONTRATO FINAL` (APROVADO/REPROVADO/EM ANÁLISE) e módulo de
pós-venda ficam como fases futuras (C.3 do roadmap).

### Roadmap-leads implementado — P1–P4 corrigidos (2026-08-05)

Branch `fix/roadmap-leads-scoring`. As 4 soluções do roadmap foram aplicadas no
código (parte A–C de `docs/roadmap-leads.md` → marcadas Implementado):

- **S1 (P1)** `template_generation_service.py`: regra de inversão p/ serviços
  digitais no `SYSTEM_PROMPT` (presença ausente/fraca = comprador; madura = negativo).
- **S2 (P2)** `scoring_service.py`: removidos exemplos copiáveis do schema
  (`pitch_angle`/`suggested_subject` "matrícula/alunos") + regra anti-copy e gancho
  obrigatório p/ lead sem site.
- **S3 (P3)** `domain_utils.py`: `canva.com`/`canva.link`, `api.whatsapp.com`
  (**subdomínio de raiz social**) e marketplaces (`instadelivery.com.br`, iFood,
  etc.) ∈ "sem site próprio" em `normalize_domain`/`is_social_domain`. Coleta
  (`places_service`) e CSV já herdam da correção.
- **S4 (P4)** `pipeline_worker.py` e `main.py`: removido o filtro
  `Lead.website.isnot(None)` — leads sem site em campanha web agora são pontuados
  pelo caminho business do orquestrador.
- **S5** resolvida por **reset total do banco** (dado de testes): `DROP schema
  public` → `alembic upgrade head` → `python -m src.seeds.scoring_templates`.
  Template `is_generated` corrompido eliminado; seed "Desenvolvimento de Sites"
  já correto. Nenhum dado reanalisado.

**Verificação**: smoke teste B.6 — confeitaria sem site (Canva) `85 HOT` com
pitch "não tem site próprio... Instagram"; clínica com site moderno `40 COLD`
(para campanha de site); nenhum pitch com "matrícula/alunos". `domain_utils`
checado para `api.whatsapp.com`/`canva`/`instadelivery` → sem site próprio.
Commits: `43d874c` (fix scoring S1-S4) + docs nesta sessão.

## Sessão atual — Windows plug-and-play + scoring de lead sem site (2026-08-11)

Branch `feat/setup-windows`.

**Windows sem Docker (validação completa nesta máquina):**
- `scripts/setup.ps1` (equivalente do `setup.sh`) — validado no caminho embarcado
  (zonky `embedded-postgres-binaries-windows-amd64:16.14.0`, jar baixado e
  extraído em `$HOME\.local\agente-prospeccao`, `initdb` + `pg_ctl start` OK) e
  no caminho "Postgres já existente". Re-execução leva ~3s (idempotente via
  sha1 dos requirements).
- Otimizações de velocidade: download com `curl.exe` (fallback
  `Invoke-WebRequest`), `$ProgressPreference='SilentlyContinue'`, extração com
  `tar.exe` do Windows (fallback lzma do Python), console em UTF-8, fix do print
  da versão do Python ("Python: 3.14").
- `scripts/dev.ps1` validado: `start` (subiu API :8000 e Web :3001, HTTP 200) /
  `status` / `stop` (mantém Postgres externo). `start` remove `.next` antes de
  subir (Turbopack limpo).
- **Launchers de duplo clique** para o pessoal da EJ (sem abrir terminal):
  `scripts/setup.cmd` e `scripts/dev.cmd` (`chcp 65001` + `-ExecutionPolicy
  Bypass` + pause em erro). Documentados no `QUICKSTART.md`/`README.md`.
- `.gitignore`: logs `uvicorn.err.log`/`next-dev.err.log` ignorados.

**Scoring — lead SEM site em campanha de presença digital (score 0):**
- Porquê: lead sem site (ou site = rede social → `places_service` zera o
  `website`) ia para `score_business_lead`; o template "Desenvolvimento de
  Sites" só tinha sinais positivos de site **existente e com problema**, o prompt
  não orientava e o LLM devolvia 0 ("não se encaixa").
- Fix:
  - `seeds/scoring_templates.py`: sinal positivo **"Sem site próprio / sem
    presença digital"** (high) + instrução explícita de que empresa sem site é
    público-alvo prioritário (seed reaplicado).
  - `scoring_service.py`: regra dinâmica no `build_prompt` — se o
    `target_service` vender presença digital (`_SELLS_WEB_PRESENCE`), ausência
    de site é oportunidade FORTE (aumenta score); senão, NEUTRA. `SYSTEM_PROMPT`
    alinhado. `score_business_lead` agora passa `has_website=bool(website)` —
    guard determinístico remove evidência "tem site" de lead sem site.
  - Smoke testado: guard/instruções corretos (web → PÚBLICO-ALVO, mecânica → NEUTRA).

**Wizard/weights quebrando:**
- `template-selector.tsx`: salvar com sinal de label vazio dava 422 no backend e
  erro não tratado. Agora valida antes (toast) + `toast` de sucesso/erro no save.

**Selects/ordenação:**
- Verificado: nenhum "biggest_to_lowest" existe no código (git log não acha);
  o select de ordenação de `/oportunidades` já exibia "Maior aptidão primeiro"
  etc. (padrão `SelectValue` com função é suportado pelo Base UI 1.6.0).
  Refatorado para renderizar as opções a partir de `sortByOptions` (fonte única).
  Se o usuário ainda vir inglês, é cache/build antigo → Ctrl+Shift+R.

**Verificação:** `python -m compileall` OK; seed OK (9 templates); smoke de
scoring OK; `tsc --noEmit` limpo; `eslint` limpo. `dev.ps1 start/stop` OK.
Suite pytest **134 passed** (api venv, 1.10s); `npm run build` OK (17 rotas).
Grafo atualizado: `graphify extract . --code-only && graphify cluster-only . --no-label`
→ `graphify-out/graph.json` com **2410 nós, 5012 arestas, 190 comunidades**.

## Como rodar

**Workers (backend):**
```bash
cd services/workers
source venv/bin/activate
python -m src.main
```

**API REST:**
```bash
cd services/api
source venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8000
# Docs: http://localhost:8000/docs
```

**Frontend:**
```bash
cd apps/web
npm run dev
# http://localhost:3001
```

## Commits Recentes

| Hash | Descrição |
|------|-----------|
| `11b56a1` | feat(workers,api,web): pontuação sem overshoot + contatos de decisores mais encontrados (Hunter domain-search, CNPJ reverso, regex email) |
| `2278671` | feat: consultor dashboard móvel — KPIs da planilha por consultor + perfil, bottom-nav, kanban touch |
| `0363d71` | feat(api,web): 4.27 visibilidade de duplicatas + decisão registrada |
| `1ef5161` | feat(api,web,workers): 4.26 sinal de Instagram |
| `4e4d243` | feat(api,web,workers): 4.21 playbooks por consultor |
| `8b08cb4` | feat(api,web,workers): 4.20 webhook genérico + link de agenda |
| `d89c8c3` | feat(api,web,workers): 4.19 variantes A/B de mensagem + medição por variante |
| `af0a369` | feat(api,web,workers): 4.18 threshold de qualificação por org |
| `1a36009` | docs: 4.25 estado do enriquecimento + TTL entregue |

## Sessão 24 — Entrega 7 (P3 · Aprofundamento) ✅ (2026-08-14)

Branch: `feat/p3-aprofundamento` (a partir de `origin/main` — inclui PR #84 já mergeado).

**Itens entregues:**
- **4.18** Threshold de qualificação por org: `Organization.qualification_threshold`
  (default 60, 1–100) aplicado em `enrichment_orchestrator._persist_scoring`.
  `GET /api/analytics/threshold-suggestion` (F1 por faixa 30–90 passo 5) +
  `ThresholdCard` em `/relatorios` com botão **Aplicar** (owner/admin). Sugestão
  manual — nada muda silenciosamente.
- **4.19** Variantes A/B de cadência: `OutreachService.generate_sequence
  (generate_variants=True)` pede 2 sequências em uma única chamada Groq
  (custo de token similar a 2 sequências concatenadas, latência à metade).
  `FollowUp.variant` (String 32); `PATCH /api/leads/{id}/cadence/step/{step}`
  registra a escolha. `GET /api/analytics/message-variants` calcula
  abertas/cliques/respostas por variante; `MessageVariantsCard` em `/relatorios`
  destaca a vencedora.
- **4.19 (medição real, 2026-08-15):** `messages.variant` (migration
  `f7a8b9c0d1e2`) — o `Message` criado no envio da cadência agora carrega o
  `variant` do `FollowUp`; o inbound de resposta grava uma `Message` espelho
  (`is_response=True`) com a variante da última `Message` enviada antes da
  resposta. `message_variants()` passou a ler `Message.variant` (uma linha por
  envio) — fim do proxy por `FollowUp.variant` + status do funil.
- **4.20** Integrações (subset): webhook genérico de saída
  (`Organization.webhook_url`+`webhook_secret`) com eventos `lead.created`,
  `lead.status_changed`, `conversion.created`. `httpx.AsyncClient` com retry
  (0.5s, 1s, 2s); fire-and-forget via `BackgroundTasks`/`asyncio.create_task`.
  `Organization.scheduling_url` injetado como CTA preferencial no prompt do
  outreach. `OrgIntegrationsCard` em `/configuracoes`. **Drive/Sheets via OAuth
  adiado** (registrado no ADR — webhook genérico cobre o caso via n8n/Make/Zapier).
- **4.21** Playbooks por consultor: tabela `consultant_playbooks` (org, author,
  vertical, subject, body, tags); CRUD `/api/playbooks` (todos leem, autor ou
  admin edita/remove). `PlaybooksCard` em `/configuracoes` + botão
  **"Salvar no playbook"** no modal de mensagens do lead.
- **4.26** Sinal de Instagram: `Lead.instagram_url` (String 255, nullable).
  Detecção em 3 fontes — Places (`websiteUri` Instagram → `instagram_url` +
  `website=None`), scan passivo do HTML (`technical_enrichment_service`),
  CSV (coluna `instagram` + regex fallback). Aparece no pitch como link e no
  prompt do outreach como fato. Helpers `extract_instagram_url`/`is_instagram_url`
  em `domain_utils`. Followers não capturados (leitura passiva não confiável).
- **4.27 pragmático**: `GET /api/leads/{id}/duplicates` (org-scoped) detecta
  matches prováveis por CNPJ, domínio normalizado, e-mail ou LinkedIn de
  contato. Banner âmbar no detalhe do lead com até 3 matches. **Modelo 3
  entidades (Company/Person/Employment) adiado** — ADR em `decisions.md`
  justifica o custo (> 1 semana, alto risco) e a abordagem atual.

**Migrations aplicadas:** `a3b4c5d6e7f8` (qualification_threshold),
`b3c4d5e6f7a8` (follow_ups.variant), `c4d5e6f7a8b9` (webhook + scheduling),
`d5e6f7a8b9d0` (consultant_playbooks), `e6f7a8b9c0d2` (leads.instagram_url),
`f7a8b9c0d1e2` (messages.variant).

**Testes adicionados (29):** `test_threshold_suggestion` (5), `test_outreach_variants` (5),
`test_webhook_outbound` (3), `test_playbooks_route` (2), `test_instagram_signal` (7),
`test_duplicate_detection` (7). Suíte total **238 passed**.

**Verificação final:** `pytest -q` 238; `compileall` services limpo;
`tsc --noEmit`/`eslint`/`npm run build` limpos; `alembic upgrade head` aplicou
todas as 5 migrations no Postgres local.

**Backlog pós-P3 (adiado, registrado em `decisions.md`):**
- 4.20 Drive/Sheets OAuth (alto custo de auth público).
- 4.27 modelo Company/Person/Employment (refactor > 1 semana, alto risco).

## Sessão 2026-08-15 — P3 finalizado: medição A/B real (4.19)

Branch `fix/p3-review`:

- **`messages.variant` (migration `f7a8b9c0d1e2`)**: o `Message` criado no
  envio da cadência (`cadence_service.send_step`) agora espelha
  `follow_up.variant` — uma linha por envio, sem o proxy por FollowUp.
- **Inbound**: `inbound_email_service` cria uma `Message` espelho
  (`is_response=True`, mesma `tracking_token` e `variant` da última `Message`
  enviada do lead) quando uma resposta chega. Sem duplicata em re-chamada do
  webhook.
- **`AnalyticsService.message_variants()`** reescrito: conta `opened/clicked`
  por `Message` enviada e `responded` por `Message.is_response` — taxa de
  resposta por variante sem depender do status atual do funil.
- **Testes**: `tests/test_message_variants.py` (5) + ajustes em
  `test_threshold_suggestion.py` para o tie-break de F1 (limiar atual vence
  empate) que havia quebrado no review pass `d555c56`.
- **Verificação**: `pytest` **244 passed**; `compileall` services limpo;
  migration aplicada no Postgres local (`f7a8b9c0d1e2` head).

---

### Bloco B2B/Infra de melhorias (2026-08-24)

Branch `feat/melhorias-b2b-infra` � itens 6, 7, 8, 9, 12 e 14 de
`docs/melhorias.md`:

- **Fix CI**: `services/api/src/db/models.py` reexporta `Notification`
  (`ImportError` no job de unit do GitHub Actions).
- **Item 14 � E2E com banco real no CI**: job `e2e` no `ci.yml` (Postgres
  service + `alembic upgrade head` +
  `pytest tests/e2e_outreach_cycle.py -q -m e2e`). Deps via
  `requirements-dev.txt`; `E2E_DATABASE_URL` aponta para o service.
- **Item 6 � M�ltiplos decisores na cad�ncia**: `_recipient_email` roteia por
  etapa � abertura/followup_1 v�o ao decisor principal; FOLLOWUP_2/CLOSING
  escalam para outro contato por autoridade (`SOCIO > CEO > DIRETOR >
  ADMINISTRADOR > OUTRO`, prim�rio � frente), sem repetir quem j� recebeu.
  Gate de `email_verified` mantido no envio autom�tico.
  `FollowUp.recipient` (migration `a9b8c7d6e5f4`) registra o destinat�rio
  efetivo; `GET /cadence` exp�e `recipient` planejado por etapa pendente;
  trilha grava "Enviado: <etapa> ? <e-mail>"; CadencePanel mostra o destino.
- **Item 7 � Sequ�ncia de conte�do por est�gio**: `playbook.stage_angles`
  (JSONB, sem migration) declara o eixo por etapa
  (`body_opening/followup_1/followup_2/closing`); `outreach_service.build_prompt`
  injeta como diretriz obrigat�ria quando presente. Editor de vertentes ganhou
  a se��o "Foco de conte�do por mensagem"; CRUD aceita/exibe `stage_angles`.
- **Item 9 � Loop de aprendizado por vertente**:
  `AnalyticsService.template_insights()` + endpoint
  `GET /api/analytics/template-insights` correlacionam `score_factors[]` de
  convertidos � perdidos (frequ�ncia relativa; m�nimo de amostra dos dois
  lados + gap = 15pp) e sugerem refor�ar/reduzir caracter�sticas � sugest�o
  apenas, edi��o segue manual. Card "O que os resultados dizem sobre suas
  vertentes" em `/configuracoes/vertentes` (manager+).
- **Item 12 � Split da p�gina de oportunidade**: `page.tsx` de 1191 ? ~430
  linhas. Extra�dos `follow-up-card`, `overview-tab`, `conversion-dialog`,
  `outreach-messages-modal`; `contacts-tab` atualizado com a vers�o rica
  (c�pias + associar LinkedIn) e `activities-tab` agora � usado pela p�gina.
- **Testes**: `tests/test_cadence_routing_and_insights.py` (14) � roteamento
  multi-decisor (escala, n�o repete, gate verificado, ordem de papel,
  prim�rio) + insights (refor�ar/reduzir/neutro, base m�nima, dedup por lead).
  Su�te em **421 passed**; compileall, lint, tsc e build limpos; migration
  aplicada no Postgres local (head `a9b8c7d6e5f4`).
