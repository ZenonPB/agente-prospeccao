# Plano de qualidade e BI

> **RUNBOOK/LIVE · atualizado em 2026-09-13.** A próxima evolução de BI deve
> partir de um Filter Context compartilhado e de métricas reconciliáveis com as
> entidades canônicas.

## Objetivo

Medir qualidade da aquisição, qualidade da priorização e resultado comercial
sem misturar workspaces, ofertas ou versões.

## Filter Context alvo

Contrato comum para APIs e frontend:

- `from` / `to`;
- `organization_id` implícito pela sessão;
- owner;
- campaign;
- offer key/version;
- status/negotiation stage;
- segment/category;
- city/state/region;
- provider/source;
- optional search/query.

O backend aplica filtros às queries. O frontend transmite estado de filtro e
renderiza resultados; não baixa todas as linhas para filtrar em memória.

## Métricas de aquisição

- candidatos descobertos;
- dedupe/merge;
- descartes de pre-scoring por motivo;
- leads criados;
- coverage por provider;
- custo/latência/erros/quota;
- decisores encontrados;
- contatos acionáveis/verificados.

## Métricas de qualidade

- distribuição de score;
- Precision@K por oferta/versão;
- taxa de utilidade 👍/👎;
- motivos de não utilidade;
- score feedback e direção média da correção;
- false-positive/false-negative review quando houver amostra manual;
- qualidade por provider/origem/segmento.

## Métricas comerciais

- pipeline por estágio;
- conversão por estágio;
- ganho/perda;
- ticket médio;
- tempo até resposta/reunião/fechamento;
- aging por estágio;
- forecast simples;
- tarefas vencidas e próximas ações;
- performance por owner/campanha/oferta.

## Attribution

Toda métrica de resultado deve preferir `CommercialOutcomeRow` atribuído à
`LeadOpportunity` e versão corretas. Se attribution estiver ausente, mostrar
explicitamente `unknown/unattributed`; não inferir oferta só para completar um
gráfico.

## Provider BI

Provider metrics devem ser analisadas por:
- capability;
- status;
- cobertura;
- precision/utilidade posterior;
- custo por resultado útil;
- latência;
- quota;
- campanha/oferta.

O objetivo é otimizar expected value/cost, não simplesmente escolher provider
com mais resultados brutos.

## Coaching

Dashboards gerenciais não substituem filas acionáveis. O produto de coaching
deve derivar de métricas auditáveis:
- oportunidades paradas;
- sem próxima ação;
- tarefas vencidas;
- reunião/proposta sem follow-up;
- alto score + contato não acionável;
- origem com alta taxa de não utilidade;
- divergência recorrente de score feedback.

## Qualidade estatística

Antes de recomendar calibração:
- informar tamanho da amostra;
- estabelecer mínimo por métrica;
- usar intervalos/incerteza quando pertinente;
- não comparar versões com coortes incompatíveis sem aviso;
- preservar período/filtros no resultado;
- separar correlação de causalidade.

## Testes

Cada endpoint novo de BI deve cobrir:
- isolamento de workspace;
- combinação de filtros;
- limites/paginação;
- datas/timezones;
- dados ausentes;
- reconciliação com fixture conhecida;
- query-count razoável.

Frontend deve cobrir estado vazio, loading, erro, filtro sem resultado e
responsividade. Visualização não deve esconder filtros ativos.

## DoD desta fase

1. Filter Context tipado no backend/frontend;
2. filtros compartilhados em dashboards principais;
3. métricas reconciliadas com outcomes/oportunidades;
4. feedback e provider quality integrados;
5. UAT com AlphaMec;
6. somente depois, usar BI como evidência para Controlled Learning.
