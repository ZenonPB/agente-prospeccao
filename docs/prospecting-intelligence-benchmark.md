# Prospecting Intelligence — benchmark e evidência

> **LIVE · 2026-09-14.** Este documento descreve o gate técnico do Bloco A. Resultados comerciais reais continuam dependendo de campanhas reais e outcomes atribuídos.

## Objetivo

O motor deve continuar genérico enquanto cada `OfferProfile` descreve o que torna uma oportunidade comercialmente forte. O núcleo não recebe branches como `if trophies` ou `if mechanical`; diferenças de ICP, evidência, timing, decisores e qualificação ficam em configuração versionável.

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

Eventos são classificados por contexto sem criar uma segunda entidade:

- `mej` → `trophies_mej`;
- `sports` → `trophies_sports`;
- demais → `trophies`.

A classificação textual é **INFERENCE** e fica em `EventOpportunityRow.provenance.intelligence`. A identidade da série remove ano/edição para relacionar edições recorrentes. A previsão da próxima janela também é inferência, nunca confirmação de que um evento futuro acontecerá.

O timing para troféus considera venda + aprovação + produção. Um evento amanhã não recebe nota máxima; a janela ideal é suficientemente antecipada para contato e produção. O sistema continua sem enviar mensagens automaticamente.

## Benchmark sintético

`services/workers/src/services/prospecting/quality_benchmark.py` contém anchors e hard negatives anonimizados. O gate verifica:

- roteamento correto da oferta para todos os anchors;
- cobertura de evidência para anchors;
- recall mínimo de alta confiança;
- zero false-positive de **alta confiança** nos hard negatives curados.

O benchmark também verifica que uma oferta não prevista no core pode ser configurada via `OfferProfile` e processada pelo mesmo matcher.

### O que o benchmark NÃO prova

Ele não prova `precision@20` real, taxa de resposta, reuniões, contratos ou receita. Esses números só podem ser publicados quando vierem de campanhas reais, com outcome atribuído à oportunidade/oferta/versão correta.

## Gate para release

O Bloco A só pode ser mergeado quando:

1. suíte Python completa passa com warnings como erro;
2. benchmark sintético passa;
3. testes de Event Intelligence/OfferMatcher/Genericity passam;
4. frontend passa lint, typecheck e build;
5. migrations/schema/E2E existentes continuam verdes no PostgreSQL real;
6. a criação de campanha permanece natural-language-first e não exige que o usuário conheça provider, query, template, profile ou outras estruturas internas.
