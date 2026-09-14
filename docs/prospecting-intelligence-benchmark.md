# Prospecting Intelligence — benchmark e evidência

> **LIVE · 2026-09-14.** Este documento descreve o gate técnico do Bloco A. Resultados comerciais reais continuam dependendo de campanhas reais e outcomes atribuídos.

## Objetivo

O motor permanece genérico enquanto cada `OfferProfile` e configuração externa do portfólio descrevem o que torna uma oportunidade comercialmente forte. O núcleo não recebe branches por oferta/vertical; diferenças de ICP, evidência, timing, decisores e qualificação ficam em configuração versionável e testável.

Golden Paths cobertos neste corte:

- landing pages e páginas de conversão;
- sistemas web sob medida;
- projetos de engenharia mecânica;
- desenho técnico e documentação de máquinas;
- troféus gerais;
- troféus para eventos esportivos;
- troféus para eventos do MEJ;
- ofertas já existentes de impressão 3D e corte/personalização a laser.

## Política epistêmica

O ranking preserva `UNKNOWN != FALSE`.

- **FACT**: dado observado na fonte ou entidade canônica.
- **INFERENCE**: conclusão derivada de evidência observada; deve manter a evidência que a sustenta.
- **HYPOTHESIS**: possibilidade comercial ainda não validada.
- **UNKNOWN**: não há evidência suficiente para afirmar ou negar.

`quality_gates` não transformam informação ausente em negativa. Eles apenas limitam a confiança máxima até existir evidência comercial forte. Sinais negativos só penalizam quando foram explicitamente observados.

## Event Intelligence

O core de eventos recebe `EventContextRule`; o vocabulário AlphaMec fica em `services/alphamec_event_intelligence.py`, fora do núcleo genérico. Assim o serviço de eventos não precisa conhecer MEJ, esporte ou uma chave concreta de oferta.

A configuração atual prioriza:

- contexto MEJ → oferta de troféus para MEJ;
- contexto esportivo → oferta de troféus esportivos;
- fallback de evento → oferta geral de troféus.

A classificação textual é **INFERENCE** e fica em `EventOpportunityRow.provenance.intelligence`. A ausência de sinal continua `UNKNOWN`. Quando a fonte fornece `category_count` e `placements_per_category`, a quantidade mínima estimada é calculada, mas permanece **INFERENCE** — não é tratada como pedido confirmado.

A identidade de série remove ruído de ano/edição para relacionar edições recorrentes. O timing considera venda, aprovação e execução: evento imediato não recebe nota máxima, e uma janela suficientemente antecipada pode ser marcada como ideal. Nenhuma dessas inferências dispara mensagem automaticamente.

## Benchmark sintético

`services/workers/src/services/prospecting_quality_benchmark.py` contém anchors e hard negatives anonimizados. Ele fica fora de `services/prospecting/` porque conhece ofertas concretas do portfólio e não pertence ao core genérico.

O gate verifica:

- 100% de roteamento correto dos anchors pelo mesmo `OfferProfileResolver` usado no fluxo de campanha;
- cobertura de evidência para os anchors;
- recall mínimo de alta confiança;
- zero falso positivo de **alta confiança** nos hard negatives curados;
- capacidade de uma oferta não prevista pelo core atravessar o mesmo matcher apenas por configuração.

O score do lead e o roteamento da campanha são verificados separadamente de propósito: primeiro a campanha resolve qual oferta deseja vender; depois o matcher avalia o fit do candidato para essa oferta.

### O que o benchmark NÃO prova

Ele não prova `precision@20` real, taxa de resposta, reuniões, contratos ou receita. Esses números só podem ser publicados quando vierem de campanhas reais, com outcome atribuído à oportunidade/oferta/versão correta.

## Gates do Bloco A

O Bloco A só pode ser mergeado quando o mesmo HEAD passar:

1. `compileall` do backend;
2. suíte Python completa com `-W error`;
3. quality gate sintético de Prospecting Intelligence;
4. ratchet de genericidade sem novo acoplamento por oferta;
5. Event Intelligence + Golden Paths persistidos e testados em PostgreSQL real;
6. migrations reais, segundo upgrade idempotente, schema verifier e seed;
7. E2E críticos existentes;
8. frontend com lint, `tsc --noEmit` e production build;
9. documentação LIVE coerente com o comportamento provado.

A criação de campanha permanece natural-language-first: o usuário informa o que quer vender e para quem, sem precisar conhecer provider, query, template, profile ou outras estruturas internas.
