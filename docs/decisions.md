# Decisões Técnicas

Consulte este arquivo antes de modificar qualquer módulo.
Se uma decisão precisar ser revertida, documente aqui o motivo.

## Ativas

| Decisão | Motivo |
|---|---|
| Tudo async (httpx.AsyncClient) | Consistência entre serviços; enriquecimento é I/O-bound |
| httpx em vez de requests | Suporte nativo a async; escolha explícita do dev |
| Google Places API (New) em vez de scraping | Oficial, sem risco de bloqueio, dados estruturados |
| Groq para IA | Free tier generoso, latência baixa |
| Modelos Groq centralizados no `.env` (`GROQ_MODEL_CLASSIFY`/`GROQ_MODEL_GENERATION`) | Trocar de modelo não deve exigir editar 6 serviços; serviços obrigados a descontinuação foram o gatilho |
| Classificação usa modelo leve (default `openai/gpt-oss-20b`) | Rotulagem/scoring são tarefas curtas; modelo maior é custo desnecessário |
| Geração de texto usa modelo de geração (default `qwen/qwen3.6-27b`) | Outreach/mensagens/brief são texto client-facing — qualidade exige modelo adequado |
| Todo consumo de LLM passa por `provider_client.groq_json_chat` (pacing global + retry 429/5xx + cota) | Rate-limit do tier free derrubava batches; um único caminho concentra resiliência e contabilidade de quota/org |
| PostgreSQL em vez de Mongo | Relacional, robusto, compartilhado entre workers e Next.js |
| Contacts como tabela separada de Lead | Um lead pode ter múltiplos decisores e fontes |
| raw_technical_data como JSONB | Permite reprocessar scoring sem revisitar o site |
| LinkedIn não automatizado | Risco de ban inaceitável; IA gera, humano envia |
| Scoring salvo mesmo se LLM falhar | Resiliência: dados técnicos não se perdem por falha de API |

## ADRs Detalhados

ADRs consolidadas inline abaixo (a pasta `docs/decisions/` não existe neste repo).

| Decisão | Motivo |
|---|---|---|
| Credentials (email/senha) em vez de OAuth externo no MVP | OAuth exige domínio público e configuração externa; email/senha funciona localmente sem dependências; tabela users já existia com password_hash |
| JWT em vez de session cookies na API | Frontend NextAuth usa JWT strategy; API FastAPI valida o mesmo token para manter sessão consistente sem backend de sessão separado |
| bcrypt em vez de argon2 | bcrypt é suficiente para o caso de uso, tem suporte nativo em Python, e é mais simples de configurar sem dependências extras de sistema |

## ADRs de Segurança (Revisão 2026-07-09)

| Decisão | Motivo |
|---|---|
| `JWT_SECRET` deve ser configurado via pydantic-settings (`settings.py`), não via `os.getenv` direto | Consistência com workers (coding-standards.md); validação em startup (fail fast se env var faltar); facilita teste com injeção de config |
| Rate limiting em auth endpoints (login/register) | Prevenir brute force; implementar como middleware FastAPI (ex: `slowapi`) ou via nginx se em produção |
| WebSocket /ws/{job_id} requer autenticação | Impedir que terceiros escutem eventos de pipeline sem token válido |
| `getSession()` não deve ser chamado em toda request de API | Substituir por leitura do token do store Zustand ou cookie — `getSession()` faz fetch HTTP a cada chamada, dobrando latência |

## ADRs de Scoring Contextual & Explicabilidade (2026-07-09)

| Decisão | Motivo |
|---|---|
| Templates de critérios em tabela `campaign_scoring_templates` em vez de hardcoded | Permite adicionar categorias de serviço sem alterar código; admin pode editar via UI futura ou SQL |
| Evidências híbridas: facts determinísticos + interpretação LLM | Reprodutibilidade — a LLM não inventa valores (CMS, SSL, load_time são facts); apenas interpreta |
| Prioridade HOT/WARM/COLD como decisão LLM (não faixa de score) | Captura nuances (ex.: lead 70 pode ser Quente se sinais de compra forem claros); reasoning separado |
| `primary_need` alargado para string livre (era enum de web) | Categorias não-web não se encaixam em `SECURITY_FIX/PERFORMANCE/etc.`; LLM define necessidade contextual |
| Sem reprocessamento automático de leads existentes | Decisão do usuário; novos leads passam pelo pipeline contextual, antigos mantêm scoring legado |
| `load_scoring_template()` com fallback a 'Genérico' | Garante que campanhas de serviços sem template específico ainda recebam análise contextual razoável |
| Score 60 continua sendo o limiar QUALIFICADO/DESQUALIFICADO | Mantém regra de negócio existente (outreach automático) sem mudança |

## ADRs de Multi-tenant / Organizações (2026-08-01)

| Decisão | Motivo |
|---|---|
| `organizations` + `organization_members` (owner/admin/member) como unidade de isolamento | Amigos/empresa compartilham workspace com papéis; usuário único continua funcionando via org pessoal |
| Org pessoal criada automaticamente no registro | Onboarding zero-config; usuário individual não precisa entender workspaces |
| `organization_id` em `campaigns`/`leads` (NOT NULL) e em `jobs` (nullable) | Isola dados por workspace; jobs legados sem campanha não quebram |
| `Lead.place_id` unique global → composta `(organization_id, place_id)` | Dois usuários podem prospectar o mesmo lugar em orgs diferentes |
| Isolamento aplicado nas queries das rotas via dependency `get_user_organization` | Toda listagem/detalhe/mutate filtra pela org do usuário; cross-tenant retorna 404 |
| Enum `organization_role` com valores minúsculos + `values_callable` no modelo | Padroniza com o padrão já usado por `AnalysisProfile`; storage lowercase no banco |
| `Invite` como tabela separada para convites por e-mail | Owner/admin convida sem expor membership; aceite via token único |

## Comentários: português, mínimos e apenas quando necessários

A partir de 2026-07-09, todo o código usa:
- Comentários em português
- Apenas comentários necessários (obviedades como `// Leads` antes de `export function useLeads` foram removidos)
- Docstrings em português e apenas quando a função não é autoexplicativa

## Decisões da auditoria de consolidação (2026-09-04)

| Decisão | Motivo |
|---|---|
| Não promover capability a `COMPLETE` apenas por possuir classe e testes | O DoD de `docs/consolidacao.md` exige consumidor operacional, persistência/provider quando aplicável e comportamento verificável. |
| Persistência temporária do `OfferMatcher` em `leads.evidence_score` | O schema ainda não possui `LeadOpportunity`; JSONB evita inventar uma tabela não migrada, mas mantém o status PARTIAL. |
| `execute_async` é o caminho oficial no código async; `execute` permanece compatível | Evita perda silenciosa de corrotinas dentro de ASGI e preserva callers síncronos. |
| Scoring não cria outcome comercial | `QUALIFICADO` é estado do funil, não venda/reunião; registrar como WON/MEETING contamina priors e A/B. |
| Verificação usa `EmailVerificationService.verify_email` | Esse é o método público existente; `check_domain_mx` não existe e causava falso negativo silencioso. |
| Status documental segue callers, persistência e providers | Evita que documentos `-FEITO` transformem scaffolding em premissa de produção. |

## Fixes Aplicados (2026-07-09)

| Decisão | Motivo |
|---|---|
| Extrair enrich+scoring para `enrichment_orchestrator.process_single_lead()` | Eliminar duplicação entre `main.py` e `pipeline_worker.py`; manutenção em um só lugar |
| slowapi para rate limiting | Biblioteca madura, decorator simples, suporte a Redis futuro |
| Token cache em memória no frontend | Elimina chamada HTTP `getSession()` em cada request de API; cache é populado após login/register |
| WebSocket auth na 1ª mensagem (token fora da URL) | `WebSocket` browser não permite headers customizados; o token enviado na 1ª mensagem de texto evita expor o JWT em query params/logs de proxy (fix de segurança do go-live) |

## ADRs do P3 — Aprofundamento (2026-08-14)

| Decisão | Motivo |
|---|---|
| `Organization.qualification_threshold` configurável, default 60 (mantém histórico) | Item 4.18 — calibrar por org exige campo + endpoint; default 60 evita migração lógica de leads antigos. Sugestão via `/api/analytics/threshold-suggestion` é manual (owner/admin aplica) — evita mudar o funil silenciosamente. |
| Threshold por org lido em `enrichment_orchestrator._persist_scoring` | Item 4.18 — a regra de negócio vive no orquestrador (único local que atribui `status`); routes de listagem continuam aceitando `min_score` externo (UI não muda). |
| Variantes A/B geradas em uma única chamada Groq (não 2 chamadas) | Item 4.19 — mesma `temperature=0.7` introduz variação natural; custo de tokens é similar a 2 sequências curtas concatenadas, mas a latência cai à metade. |
| `follow_ups.variant` (String 32, nullable) — não há enum A/B/C | Item 4.19 — labels curtos ("A"/"B"/"C") variam conforme o consultor; enum rígido forçaria migration a cada novo rótulo. |
| Medição por variante com `messages.variant` (uma linha por envio) + `Message.is_response` criada pelo inbound | Item 4.19 — antes usávamos `FollowUp.variant` + status do funil como proxy (misturava etapas e o mesmo token). Agora o `Message` carrega o `variant` do FollowUp no envio e o inbound grava uma `Message` espelho (`is_response=True`) com a variante da última mensagem enviada — permite taxa de resposta por variante sem dupla contagem. Para A/B estatístico rigoroso por etapa ainda faltaria tracking individual por token por etapa (redundante hoje: token único por `FollowUp`). |
| `consultant_playbooks` como tabela nova (não reaproveita `CampaignScoringTemplate.playbook`) | Item 4.21 — playbooks por template alimentam a LLM; playbooks por consultor são um repositório pessoal do time. Conceitos diferentes, tabelas diferentes. |
| Playbooks: lista visível a toda org; edição só do autor ou admin | Item 4.21 — inspiração compartilhada, autoria preservada. |
| `webhook_outbound_service` usa `httpx.AsyncClient` + retry com backoff | Item 4.20 — alinhado ao padrão async do projeto; retry 3x (0.5s, 1s, 2s) cobre falhas transitórias sem prolongar a request. Fire-and-forget via `BackgroundTasks` (rotas) ou `asyncio.create_task` (pipeline). |
| `scheduling_url` injetado como CTA preferencial no prompt, não anexado no final | Item 4.20 — a LLM escolhe quando oferecer (cadência permite omitir se o lead já respondeu antes); manter o link no final seria estático demais. |
| Adiar importação via Google Drive/Sheets (OAuth) — registrado no backlog | Item 4.20 — exige OAuth público + custo de manter credenciais; o webhook genérico já cobre o caso de uso "planilha compartilhada" via `n8n`/Make/Zapier consumindo CSV e POSTando no webhook. Documentado como adiado. |
| Detecção de Instagram em 3 fontes (Places, scan passivo do HTML, CSV) | Item 4.26 — maximiza cobertura sem nova chamada externa. Followers não são capturados (não há leitura passiva confiável); apenas presença + link. |
| Score não muda automaticamente com Instagram ativo | Item 4.26 — manter `qualification_score` determinístico; o sinal entra como `evidence` no prompt e o consultor vê o link no pitch. |
| 4.27 pragmático — `GET /api/leads/{id}/duplicates` (visibilidade) sem mutação | Item 4.27 — reaproveitamento real entre leads exige modelo Company/Person/Employment (refactor > 1 semana, alto risco para uma branch). Por enquanto, exibimos matches prováveis (CNPJ/domínio/e-mail/LinkedIn de contato) na UI do lead e registramos a decisão de adiar. |
| ADR para registrar adios (4.20 Drive, 4.27 modelo 3 entidades) | Sem o registro, o item some do roadmap. Decisão escrita no `decisions.md` mantém rastreio. |
| Candidate como estado no pipeline, não tabela (fase 1 do plano de melhorias) | Doc 06 sugere começar lógico; gate de promoção com descarte dá o ganho de custo imediato sem migration de entidade nova. Tabela `Candidate` só quando houver métrica de retrieval/auditoria de descartes que a exija. |
| Perfil da vertical derivado de `enrichment_steps` + `prescoring_config` no template (não de regex no core) | Engine genérico: adicionar vertical = inserir config; `resolve_prospecting_profile` é o único ponto de interpretação da vertical. Regexes do `scoring_service` ficam como fallback legado até revalidação dos fixes de falso-positivo ERP. |
| Pre-scoring desligado por padrão em código; ativado por `prescoring_config.enabled` no template | Compatibilidade: campanhas/templates existentes mantêm o fluxo atual até o seed aplicar config; comportamento novo é explícito e auditável (log + `prescoring_discarded`). |
| `leads.score_vector` JSONB ao lado de `qualification_score` (sem substituir) | Doc 02 exige migração gradual; score legado é a fonte de verdade do funil (UI/BI/endpoints). Dimensões são opcionais — contrato pronto, geração vem depois. |
| Pre-scoring 100% determinístico (sem LLM), pesos no template | Custo: roda sobre sinais já coletados; doc 01 proíbe LLM no pre-score. Pesos por vertical permitem "sem site + Instagram" pontuar alto em Landing e quase nada em Engenharia. |
| Descartes do gate persistidos em `prescoring_discards` com `reason` (`below_threshold` × `top_k_cut`) | Auditoria de falsos-negativos e recalibração de threshold (docs 01/06/12) exigem rastreio; sem registro o descarte é irreversível. Upsert idempotente por (campaign_id, place_id). |
| Persistência dos descartes via callback `persist_fn` injetado no serviço | Mantém `CandidatePreScoringService` puro (sem SQLAlchemy), coerente com a regra de orquestração do repo. Auditoria é best-effort: falha de DB loga e NUNCA bloqueia o pipeline. |
| Signal Registry como módulo de código com chaves canônicas + fábrica (não tabela DB) | Doc 20 manda semântica/fonte/confiança; chaves em `SignalKey` evitam strings soltas e dão peso por vertical sem colisão. Sinais são voláteis (por candidato) — persistir tudo seria ruído; o que importa auditoria (descartes/scoring) já tem tabela. |
| FACT exige fonte+evidência; rebaixa a INFERENCE se faltar | Doc 29: fato sem prova não é fato. A fábrica impõe a regra no ponto único de criação (pre-scoring e futuros providers) em vez de depender de cada chamador. |
| `overall` do score vetorial agregado no BACKEND com pesos por perfil; `formula_version` fixada pelo backend | Doc 02: "score final calculado por estratégia da vertical". Deixar a LLM escolher `formula_version`/agregação quebra auditoria (prompt-hack testado); backend é a fonte de verdade da fórmula, LLM fornece só dimensões. |
| Ordem/parada de enrichment declaradas em `enrichment_strategy` (JSONB) no template | Doc 08: ordem é da oferta. `skip` remove capability, `stop_after` corta execução; planner devolve plano auditável (runnable/skipped com motivo). Compat total: `enrichment_steps` continua funcionando. |
| Multi-query com limite proporcional por query + dedup por `place_id` mantendo `source_queries` | Doc 04: recall por variedade semântica, não paginação cega (que degrada relevância). `source_queries` vira evidência de subnicho no candidato/inferências. Cap de 10 queries evita abuso de cota. |
| Seed "Landing Pages" como template dedicado (prescoring próprio) em vez de novo perfil | Doc 03: não é vertical nova, é variação de `web_presence` com pesos/ênfase de conversão. Reusa `resolve_prospecting_profile` + router exact/fuzzy sem tocar no engine. |
| `_serialize` do template passou a incluir `prescoring_config` (bug da fase 1) | Gate de pre-scoring lia config só de templates gerados inline; templates reais do banco perdiam a config na serialização e o gate ficava inerte. Bug corrigido junto com o plumb de `enrichment_strategy`. |

## Issues Conhecidas (resolvidas)
Todas as 11 issues da revisão de segurança foram corrigidas (2026-07-09). A lista completa com status está no histórico do `docs/context.md`.