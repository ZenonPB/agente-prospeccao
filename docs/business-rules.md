# Regras de Negócio

## Funil de Status dos Leads
NOVO
→ ANALISADO      (após enriquecimento técnico)
→ QUALIFICADO    (score >= 60)
→ DESQUALIFICADO (score < 60 ou sem site)
→ CONTATADO      (1ª mensagem enviada)
→ RESPONDIDO     (lead respondeu)
→ REUNIAO_MARCADA
→ PERDIDO

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

- Lead sem website entra como NOVO mas não passa pelo enriquecimento técnico
- Lead sem contato com confidence >= 50 não entra no outreach automático
- Leads PERDIDO voltam para a fila após 90 dias
- Scoring é recalculado quando novos dados de enriquecimento chegam
- Mensagem de outreach nunca é genérica — deve referenciar dados reais do lead

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
| Encerramento | Dia 14 sem resposta | Ciclo encerrado, lead volta em 90 dias |