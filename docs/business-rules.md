# Regras de Negócio

## Funil de Status dos Leads
NOVO
→ ANALISADO      (após enriquecimento/scoring)
→ QUALIFICADO    (score >= 60)
→ DESQUALIFICADO (score < 60)
→ CONTATADO      (1ª mensagem enviada)
→ RESPONDIDO     (lead respondeu)
→ REUNIAO_MARCADA
→ REUNIAO_FEITA  (reunião realizada)
→ PROPOSTA_ENVIADA
→ PERDIDO        (volta à fila após 90 dias de carência; perdas deliberadas não voltam)

## Critérios de Scoring (0-100)

### Scoring Contextual por Campanha

A pontuação **NÃO** é genérica — ela depende do serviço que a campanha quer vender
e do segmento prospectado. Cada `CampaignScoringTemplate` (tabela no banco)
define critérios relevantes para uma categoria de serviço (por exemplo:
"Desenvolvimento de Sites" valoriza SEO/HTTPS/performance; "Engenharia Mecânica"
valoriza porte/fábrica/expansão — e **desvaloriza** qualidade do site como
critério primário).

O pipeline carrega o template por ordem de precedência:
1. `campaign.scoring_template_id` (vínculo explícito do usuário).
2. Match case-insensitive de `template.service_label` com `campaign.target_service`.
3. Fallback ao template `Genérico` ativo.
4. `None` — caso em que a LLM infere os critérios a partir do contexto e explica-os
   em `priority_reasoning`.

Os critérios do template podem ser editados via UI futura (gerenciamento de
templates) ou diretamente via SQL/seed — sem mudar código. Para adicionar uma
nova categoria de serviço basta inserir um novo row em `campaign_scoring_templates`
ou estender o seed em `services/workers/src/seeds/scoring_templates.py` e
re-executar `python -m src.seeds.scoring_templates`.

### Faixas do Score

| Faixa | Significado |
|---|---|
| 80-100 | Múltiplas evidências positivas fortes para ESTA campanha |
| 60-79  | Fito razoável + alguns sinais positivos → QUALIFICADO |
| 40-59  | Fito parcial / sinais mistos |
| 20-39  | Poucos sinais relevantes para a campanha |
| 0-19   | Não se encaixa ou sinais contrários |

**Score >= 60 → QUALIFICADO → entra na fila de outreach**
**Score < 60 → DESQUALIFICADO → não entra no outreach automaticamente**

### Prioridade (Quente / Morno / Frio)

A `priority` é uma decisão **LLM**, NÃO uma derivação matemática do score. Ela
pondera urgência, fito com o serviço e sinais de compra:

| Valor | Quando |
|---|---|
| HOT (Quente)  | Urgência + fito + sinais de compra claros |
| WARM (Morno)  | Fito razoável, alguns sinais |
| COLD (Frio)   | Poucos sinais / fito baixo |

A LLM devolve também `priority_reasoning` justificando a escolha — exibido no
card "Evidências" da tela de detalhe do lead.

### Explicabilidade (campos em `leads`)

Toda qualificação vem acompanhada de:

- `executive_summary` — resumo consultor comercial (2-4 frases)
- `score_factors[]` — lista de fatores + (positivos) / − (negativos) com `rationale` e `evidence_ref`
- `evidence[]` — lista de evidências estruturadas (`type`, `severity`, `title`,
  `description`, `source`). As evidências técnicas são FATOS coletados
  passivamente (CMS real, SSL medido, load_time medido, etc.) — a LLM apenas
  interpreta, sem inventar valores.
- `qualification_reason` — argumento de venda textual
- `priority_reasoning` — justificativa da prioridade

O frontend exibe tudo isso na aba "Evidências" do detalhe do lead.

## Confiança de Contato (contact_confidence)

| Faixa | Significado |
|---|---|
| 90-100 | Dono/CEO confirmado via Hunter ou CNPJ |
| 70-89 | Cargo relevante encontrado (diretor, sócio) |
| 50-69 | E-mail genérico de empresa (contato@, comercial@) |
| 0-49 | Fonte incerta ou inferida |

## Regras do Pipeline

- Lead sem website **não passa pelo enriquecimento técnico**, mas é pontuado
  pelo **caminho business** em campanhas `WEB_PRESENCE` (fatores cadastrais +
  sinais do template direcionados a quem não tem site próprio — roadmap-leads
  S4). Nunca fica invisível/`NOVO` esperando por um site.
- Lead sem contato com `email_verified = True` não sai no **envio automático**
  da cadência (gate 4.1); humano ainda pode enviar não-verificado com aviso.
- **Leads `PERDIDO` voltam à fila após 90 dias** (implementado 2026-08-12):
  job em background (`LOST_REQUEUE_DAYS`, default 90) re-enfileira
  `PERDIDO → NOVO` quando a perda é **baseada em tempo** (`lost_reason` nulo ou
  `NAO_RESPONDEU` = "ciclo encerrado sem resposta") e o lead **não** é
  `opt_out`. Perdas deliberadas (`PRECO`/`CONCORRENTE`/`PRAZO`/`OUTRO`) **não**
  voltam automaticamente. Data de perda = última `LeadActivity` com
  `status_to=PERDIDO` (fallback `updated_at`); mantém o consultor atribuído e
  registra trilha. Carência configurável (`LOST_REQUEUE_DAYS=0` desativa).
- Scoring é recalculado quando novos dados de enriquecimento chegam
  (`POST /campaigns/{id}/reanalyze`).
- Mensagem de outreach nunca é genérica — deve referenciar dados reais do lead.

## Cadência de follow-up e envio (3.7/4.3)

- Etapas `FollowUpStep`: `OPENING` (dia 0) → `FOLLOWUP_1` (dia 3) →
  `FOLLOWUP_2` (dia 7) → `CLOSING` (dia 14) + `POST_SALE` (pós-venda, mesmo
  motor). Status: `PENDING/SENT/SKIPPED/CANCELLED`.
- **Humano no loop por padrão**; envio automático só com opt-in da org
  (`auto_send_email`), e respeita:
  - teto diário por org (`daily_email_limit`, default 40) e janela de
    espalhamento (`send_window_start/end`, default 09:00–17:00, fuso do
    servidor) — etapas que não couberem ficam `PENDING` (postergadas, nunca
    falham);
  - remetente dedicado por consultor (`organization_members.email_from`) →
    org (`organizations.email_from`) → global (`SMTP_FROM_EMAIL`);
  - `opt_out` do lead cancela as etapas pendentes;
  - destinatário com `email_verified = True`.
- Inbound (`POST /webhooks/email/inbound`, valida `EMAIL_WEBHOOK_SECRET`):
  resposta → `RESPONDIDO` (cancela a cadência); STOP → `opt_out`.
- Tracking de abertura/clique por etapa (`tracking_token`) quando
  `TRACKING_BASE_URL` configurada; bounce registra em `email_suppressions`.

## Opt-out / supressão

- `POST /leads/{id}/opt-out` marca `Lead.opt_out` e torna as etapas pendentes
  da cadência `SKIPPED`; `DELETE /leads/{id}` remove o lead.
- Bounce (falha de entrega) registra em `email_suppressions` e impede novos
  envios ao mesmo endereço.

## Funil de negociação e resultado de contrato (C.3)

- `Lead.negotiation_stage`: `RD` (reunião de demonstração) → `ORCAMENTO` → `RP`
  (reunião de proposta). Gravado via `PATCH /leads/{id}/negotiation` **somente**
  quando o lead está em `RESPONDIDO / REUNIAO_MARCADA / REUNIAO_FEITA /
  PROPOSTA_ENVIADA` (400 caso contrário).
- `Lead.contract_outcome`: `APROVADO/REPROVADO/EM_ANALISE` (+ `outcome_date`);
  a conversão (`POST /leads/{id}/conversion`) marca `APROVADO`.
- Pós-venda (`POST /leads/{id}/post-sale`): registra `post_sale_contacted_at` +
  `post_sale_channel` (`WHATSAPP/EMAIL`) e agenda o lembrete `POST_SALE` quando
  há conteúdo. Somente para leads convertidos.

## Valor, forecast e metas (4.8/4.9)

- `Lead.value` (ticket estimado) + `expected_close_date` + `lost_reason`
  (`PRECO/PRAZO/NAO_RESPONDEU/CONCORRENTE/OUTRO`) — `PATCH /leads/{id}`.
- Forecast ponderado no BI: `value × win-rate do estágio` (NOVO 5% →
  PROPOSTA_ENVIADA 90%); `realized_revenue` vem de `Conversion.contract_value`.
- Metas mensais por consultor em `sales_targets` (`meetings_target`/
  `revenue_target`, mês `YYYY-MM`); `AnalyticsService.consultants()` devolve o
  atingimento (% realizado vs meta).

## SLA de leads parados (4.10)

- Prazos configuráveis por org (`organizations.sla_*_days`; defaults 5/2/2):
  `QUALIFICADO_NO_CONTACT`, `RESPONDIDO_NO_NEXT_ACTION`, `OPENED_NO_RESPONSE`.
- `GET /leads/sla-alerts` lista os alertas por dias parados, respeitando o
  escopo do consultor (`consultant_lead_scope`); alimenta o painel "Ações de
  hoje" e a notificação no kanban.

## Limites Legais (Lei 12.737/2012)

A plataforma jamais:
- Tenta explorar vulnerabilidades
- Executa injeções de qualquer tipo
- Testa autenticação
- Realiza qualquer ação não-passiva

Toda análise se restringe a informações publicamente acessíveis.

## Limites de Uso (API Keys)

As chaves de API compartilham um pool de créditos limitados.

- Google Search: 100 consultas/mês por chave
- Hunter.io: 1.000 créditos/mês por chave
- WHOIS: 50 consultas/mês por chave
- CNPJ: 20 consultas/mês por chave

Se uma chave exceder seu limite, todas as operações usarão fallback (cache local ou skipping) até o próximo ciclo.

## Sequência de Follow-up

| Mensagem | Quando | Objetivo |
|---|---|---|
| 1ª mensagem | Dia 0 | Apresentação + problema + CTA reunião |
| Follow-up 1 | Dia 3 sem resposta | Reforço leve |
| Follow-up 2 | Dia 7 sem resposta | Última tentativa |
| Encerramento | Dia 14 sem resposta | Ciclo encerrado (lead → `PERDIDO`, marcado pelo consultor; volta à fila após 90 dias se a perda for por ausência de resposta) |
| Pós-venda | Após conversão | Acompanhamento pós-cliente (canal WhatsApp/E-mail) |