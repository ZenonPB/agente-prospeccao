# Data Engine Brasil — piloto controlado (Fase 1H)

**Status:** RUNBOOK — CODE COMPLETE para instrumentação; execução real depende de snapshot e credenciais autorizadas.

Este documento fecha a Fase 1 com um procedimento reproduzível. Ele não declara qualidade comercial sem dados reais e não autoriza a promoção automática de Commercial Dimensions para o ranking principal.

## Objetivo

Medir, por organização e opcionalmente por campanha, o caminho já existente de descoberta até oportunidade: cobertura das quatro dimensões comerciais, comparação do score legado com a prioridade shadow, contatabilidade, saúde/custo dos providers e outcomes atribuídos.

A consulta ao diagnóstico é read-only. Consultá-lo não executa provider, não consome quota, não altera `qualification_score`, `priority`, `overall`, status, ordenação ou CRM. A materialização prévia das dimensões shadow é uma etapa separada e explícita.

## Cenários de referência

O piloto deve usar três cenários separados, cada um com sua Vertente efetiva e território explícito:

1. AlphaMec — serviços/projetos de Engenharia Mecânica;
2. AlphaMec — Troféus/Eventos;
3. desenvolvedor independente — Landing Pages.

Não misturar os três em uma única campanha.

## Pré-condições

- `main` com CI verde no SHA implantado;
- snapshot real do Brazil Company Registry importado e conferido pelo ledger;
- organização e membros corretos;
- Vertente efetiva revisada para o cenário;
- território/região e limites de busca explícitos;
- providers externos somente com credenciais autorizadas;
- quotas e budget configurados antes da execução; provider pago permanece desabilitado quando não houver autorização;
- Commercial Dimensions continua em shadow;
- nenhuma automação de contato é necessária para este piloto.

## Execução

Para cada cenário:

1. criar uma campanha controlada e executar o fluxo normal;
2. habilitar `COMMERCIAL_DIMENSIONS_SHADOW_ENABLED` somente no ambiente controlado do piloto;
3. materializar as dimensões da amostra pelo caminho persistente de recompute/análise já existente, sem promover o shadow para ranking;
4. confirmar que os leads da amostra possuem `score_vector.commercial_dimensions` antes de interpretar cobertura;
5. consultar `GET /api/commercial-intelligence/pilot-readiness?campaign_id=<uuid>`;
6. ao terminar a execução controlada, restaurar a configuração de shadow conforme a política do ambiente.

O endpoint é protegido pelo mesmo contexto de organização e papel de analista usado pelos demais endpoints de inteligência comercial. O `campaign_id` é apenas filtro adicional: nunca remove o filtro de tenant.

Se a cobertura de dimensões vier zerada, isso deve ser tratado primeiro como **dimensões não materializadas** e não como evidência de baixa qualidade comercial. Não alterar thresholds para mascarar ausência de materialização.

Registrar o SHA implantado, campaign id, Vertente/versão, território, horário inicial/final e eventuais indisponibilidades externas. Não registrar chaves, tokens, e-mails pessoais ou conteúdo sensível no relatório.

## Métricas mínimas

O diagnóstico deve abranger tamanho da amostra, taxa qualificada, taxa contatável, cobertura das quatro dimensões, cobertura da Prioridade Comercial shadow, diferença entre score legado e prioridade shadow, pares comparáveis, saúde/custo dos providers e outcomes comerciais atribuídos (respostas, reuniões, ganhos/contratos e receita quando disponíveis). A saúde de atribuição deve permitir distinguir outcome atribuído de outcome sem vínculo confiável.

`UNKNOWN` é ausência de observação e não equivale a zero. Métricas sem denominador retornam `null`, não 0%.

## Gate de revisão

O sistema pode marcar `ready_for_review=true` somente quando houver amostra mínima e cobertura observacional suficiente. Esse sinal significa **pronto para revisão humana**, não pronto para substituir o ranking.

Os critérios iniciais são deliberadamente conservadores e versionáveis no código: pelo menos 30 leads, 20 pares legado/shadow, cobertura de Aderência >= 80%, Momento >= 60%, Confiança dos dados >= 80% e taxa de falha de providers <= 10%.

`promotion_allowed` permanece sempre `false` nesta fase. A promoção exige revisão dos resultados reais, falsos positivos, outcomes e diferenças por Vertente.

## Critérios comerciais a observar manualmente

Revisar se a empresa combina com a oferta; se a justificativa explica empresa/oferta/momento; se a evidência existe e está atual; se falha de coleta permaneceu UNKNOWN; se baixa Contatabilidade preservou boa Aderência; se o contato participa da decisão; se houve gasto sem autorização; e se existem duplicatas de Company/Person/Lead.

## Saída do piloto

Para cada cenário, guardar apenas agregados e exemplos sanitizados necessários à revisão. Comparar os três cenários separadamente e em conjunto. A decisão seguinte pode ser manter shadow e corrigir cobertura, ajustar fórmula/configuração declarativa ou preparar promoção controlada posterior.

Não alterar pesos ou thresholds para "fazer o piloto passar". Mudanças precisam ser justificadas pelas evidências e cobertas por testes.
