# Data Engine Brasil — piloto controlado (Fase 1H)

**Status:** CODE COMPLETE / OPERATIONAL VALIDATION REQUIRED.

Este runbook separa três estados que não podem ser confundidos: código pronto, telemetria suficiente para revisão e evidência operacional suficiente para discutir promoção. Nenhum deles autoriza promoção automática de Commercial Dimensions.

## Objetivo

Validar, por organização e campanha, o caminho real:

`Vertente → Registry → Discovery → Public Web → Commercial Dimensions → People → Contact → Outreach → Conversation`.

A consulta de diagnóstico é read-only: não executa provider, não consome quota e não altera ranking, status ou CRM.

## Cenários obrigatórios

Executar separadamente:

1. AlphaMec — Engenharia Mecânica;
2. AlphaMec — Troféus/Eventos;
3. desenvolvedor independente — Landing Pages.

Não misturar cenários numa campanha, pois isso destrói a interpretação por Vertente.

## Piloto Araraquara — Landing Pages → clínicas de psicologia

Primeiro cenário operacional do Registry real (Nível 1): sem outreach,
fontes gratuitas, Commercial Dimensions em shadow.

- Oferta: Landing Pages (`landing_page`); segmento: CNAE 8650-0/03;
  território: Araraquara/SP (IBGE 3503208).
- Configuração por overlay de workspace (`OfferProfileVersion`, versão
  `1.1`): `services/prospecting/araraquara_pilot.py` + CLI
  `stage_pilot_overlay --org-id <uuid>` (grava INATIVO; ativação humana
  pelo fluxo de versões). O catálogo factory não muda.
- Carga filtrada (arquivos nacionais, recorte local):
  `import_registry --snapshot-month AAAA-MM --manifest manifest.json
  --estabelecimentos ... --empresas ... --cnaes ...
  --uf SP --municipio-cod 3503208 --cnae 8650-0/03`
- Smoke do caminho (PG): `E2E_DATABASE_URL=... pytest
  tests/test_araraquara_pilot.py -q` — import filtrado, discovery
  Registry, entity resolution, Company sem duplicatas, shadow UNKNOWN,
  budget R$0, relatório com candidatos/ativas/principal/secundário,
  materializadas, custo, falhas e provenance.
- Mapeamento nome→código IBGE ainda é manual (operador informa
  `3503208`); tabela de labels de município é hardening futuro.
- Fixtures em layout oficial provam o caminho, não validação
  operacional: o gate continua sendo snapshot real + revisão humana.

## Pré-condições

- `main` com CI verde no SHA implantado;
- snapshot real do Brazil Company Registry importado e conferido pelo ledger;
- encoding e layout confirmados contra o snapshot efetivamente utilizado;
- organização, membros, Vertente e território corretos;
- providers externos somente com credenciais autorizadas;
- quotas e budget definidos antes da execução; provider pago desabilitado sem autorização;
- Commercial Dimensions em shadow;
- nenhuma alteração de threshold para fazer o piloto passar.

## Execução

Para cada cenário:

1. registrar SHA implantado, campaign id, Vertente/versão, território e janela da execução;
2. executar discovery normal sobre dados reais;
3. habilitar `COMMERCIAL_DIMENSIONS_SHADOW_ENABLED` apenas no ambiente controlado;
4. materializar as dimensões pelo caminho persistente existente;
5. confirmar `score_vector.commercial_dimensions` na amostra;
6. consultar `GET /api/commercial-intelligence/pilot-readiness?campaign_id=<uuid>`;
7. revisar manualmente falsos positivos, evidências, contatos e duplicatas;
8. trabalhar uma amostra real antes de discutir promoção;
9. restaurar a configuração do ambiente ao encerrar o piloto.

`campaign_id` é somente filtro adicional; tenant scope continua obrigatório.

## Interpretação correta

`UNKNOWN` significa ausência de observação, nunca zero. Cobertura zerada deve ser investigada primeiro como possível falta de materialização. Falha de provider não pode virar evidência negativa. Baixa Contatabilidade não reduz Aderência.

O diagnóstico separa:

- `ready_for_review`: telemetria técnica suficiente para revisão humana;
- `promotion_evidence_sufficient`: amostra técnica + amostra realmente trabalhada + outcomes confiavelmente atribuídos suficientes para uma decisão humana;
- `promotion_allowed`: permanece `false`; não existe autopromoção.

Os gates atuais exigem, no mínimo, 30 leads, 20 pares legado/shadow, Aderência >= 80%, Momento >= 60%, Contatabilidade >= 60%, Confiança >= 80% e falha de providers <= 10%. Para evidência de promoção também são exigidos 20 leads trabalhados, 10 outcomes atribuídos, atribuição >= 80% e pelo menos um outcome positivo observado.

Esses números são gates de suficiência, não prova de que a fórmula é melhor. Não ajustar pesos ou thresholds para satisfazê-los.

## Provenance de outcomes

Um `lead_opportunity_id` legado não é, sozinho, prova de atribuição causal: há caminhos históricos que podem preencher o vínculo por heurística. Só marque um outcome como atribuído para o gate de promoção quando a provenance disponível comprovar o vínculo. Na dúvida, trate como não atribuído.

Transições sucessivas do mesmo lead devem ser consolidadas por entidade para métricas de funil. Eventos brutos podem existir separadamente, mas não devem inflar contagens de leads.

## O que precisa ser observado no piloto real

- Registry encontra empresas brasileiras coerentes com CNAE/território;
- volume real não degrada busca/ingestão de forma incompatível com operação;
- fallback mantém o produto utilizável quando Registry/web/provider falha;
- caminho R$0 não consome provider pago silenciosamente;
- evidência explica empresa/oferta/momento e tem provenance/observed_at;
- Company/Person/Lead não são duplicados indevidamente;
- pessoa encontrada realmente participa da decisão quando isso for afirmado;
- e-mail heurístico não aparece como verificado;
- suppression/opt-out/reply/STOP/bounce funcionam no fluxo real;
- tenant isolation permanece intacto.

## Critério para sair de shadow

Não promover Commercial Dimensions apenas porque o CI está verde ou `ready_for_review=true`. Uma promoção futura exige todos os gates técnicos, `promotion_evidence_sufficient=true`, revisão dos falsos positivos e resultados por Vertente e uma mudança de código/configuração explícita, reversível e coberta por regressões. Até lá, o ranking legado continua canônico.

## Limite desta validação

CI automatizado prova contratos de software; ele não substitui snapshot real da Receita, credenciais autorizadas, comportamento de providers externos nem resultados comerciais de pessoas reais. Se essas evidências não estiverem disponíveis, o estado correto continua sendo `OPERATIONAL VALIDATION REQUIRED`, e não “validado em produção”.
