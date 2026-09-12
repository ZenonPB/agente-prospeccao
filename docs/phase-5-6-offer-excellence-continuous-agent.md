# Fases 5 e 6 — Excelência por oferta e agente contínuo

Este documento registra a implementação das próximas duas fases do roadmap comercial: especialização por oferta AlphaMec e automação contínua com controle humano, isolamento por workspace e defaults free-first.

## Fase 5 — Excelência por oferta

O `OfferProfile` continua sendo a unidade declarativa da inteligência comercial. A Fase 5 não cria engines paralelas: ela amplia o mesmo registry com sinais canônicos e pesos específicos por oferta.

### Ofertas existentes aprimoradas

- **Landing Page**: Ads, CTA fraco, ausência de formulário e fluxo de conversão fraco; personas Founder, Marketing e Comercial.
- **Projeto Mecânico**: linha de produção, máquinas customizadas, automação, equipamento novo, expansão fabril e contratação de engenharia mecânica.
- **Desenho Técnico**: usinagem, peças customizadas, reposição, engenharia reversa e manufatura sob encomenda.
- **Manual de Máquinas / NR-12**: fabricante de máquinas, NR-12, segurança industrial, documentação técnica e máquina nova.
- **Troféus**: eventos agendados e sazonalidade passam a complementar o Golden Path já existente.

### Novas ofertas

- `web_systems_erp` — sistemas web/ERP sob medida, com foco em complexidade operacional, múltiplas unidades, processos manuais, limitações de SaaS e contratação de Ops/TI.
- `3d_printing` — impressão 3D/prototipagem, com sinais de P&D, novo produto, protótipo e peças customizadas.
- `laser_cutting_technical` — corte técnico para manufatura, usinagem e peças sob especificação.
- `laser_custom_products` — produtos personalizados a laser para eventos, brindes e demandas sazonais.

Os sinais foram adicionados ao `Signal Registry`; portanto, continuam sujeitos ao contrato epistêmico já existente. Um sinal não vira fato apenas porque uma oferta o referencia.

## Recorrência de eventos e recompra

`EventSeriesService` normaliza nomes retirando ruído como ano e edição e agrupa eventos por organizador, nome-base e família. O serviço persiste:

- `series_key`;
- quantidade de eventos conhecidos;
- evento anterior e mais recente;
- intervalo mediano entre ocorrências;
- `recurrence_confidence`;
- janela estimada da próxima edição.

A janela de recompra considera somente séries com confiança mínima e cuja próxima ocorrência estimada entra no horizonte comercial de 30 a 120 dias. A inferência permanece auditável e nunca substitui uma data oficial de evento.

## Case Study Matcher

`CaseStudy` é persistido por oferta e pode ser global ou específico de workspace. O matcher só seleciona cases cadastrados. Não gera provas, clientes ou resultados fictícios.

A seleção atual é determinística e explicável: oferta compatível + sobreposição de segmentos do lead com os segmentos do case. O retorno expõe `match_score` e os tokens efetivamente coincidentes.

## Fase 6 — Saved Searches, Alerts e Continuous Agent

### Saved Searches

`SavedProspectingSearch` persiste filtros, oferta, dono, política de notificação e agendamento. A primeira implementação executa filtros sobre a base já consolidada do workspace, incluindo texto, cidade/UF, score mínimo, canais disponíveis e oferta.

Executar uma Saved Search não chama providers externos. Matches novos geram alertas idempotentes por fingerprint.

### Alerts

`ProspectingAlert` centraliza:

- matches de buscas salvas;
- janelas de recompra de eventos recorrentes.

Estados disponíveis: `new`, `read`, `dismissed` e `actioned`. A constraint lógica de fingerprint evita recriar o mesmo alerta em execuções repetidas.

### Estado operacional do agente

Cada lead pode ter um `ProspectingAgentState` com histórico limitado e justificativa. Estados canônicos:

1. `DISCOVERED`
2. `NEEDS_ENRICHMENT`
3. `READY_TO_SCORE`
4. `READY_FOR_CONTACT`
5. `AWAITING_ACTION`
6. `IN_SEQUENCE`
7. `WAITING`
8. `REENGAGE`
9. `CLOSED`

A transição é derivada de dados persistidos — status comercial, oportunidade, decisor roteável e próxima ação. A classificação não envia mensagem nem muda status comercial sozinha.

## Radar comercial no frontend

A nova tela `/monitoramento` reúne:

- resumo de Saved Searches, alertas, séries recorrentes e leads prontos para contato;
- criação e execução de buscas salvas;
- leitura de alertas;
- recomputação de séries de eventos;
- funil de estados do agente;
- execução manual do monitoramento contínuo.

A interface deixa explícito que o monitoramento externo depende de opt-in. O botão de execução manual ignora apenas o relógio do scheduler; não ignora quotas ou permissões.

## Segurança, tenancy e custo

- Todas as consultas operacionais são filtradas por `organization_id`.
- Saved Searches, alertas, séries e estados são isolados por workspace.
- Ações gerenciais exigem `MANAGER`; visualização e operação analítica exigem `ANALYST` ou superior conforme as dependências existentes.
- A Fase 6 reutiliza o Continuous Intelligence da Fase 3/4, que continua com quotas zero por padrão para providers externos.
- Nenhum case real é inventado ou seedado como prova social.
- Nenhum alerta dispara outreach automaticamente.

## Critérios de aceite técnico

Antes do merge, o mesmo HEAD deve passar:

- `pytest tests -q -W error`;
- `compileall` backend/workers;
- migrações PostgreSQL reais, incluindo segunda execução idempotente;
- schema contract e seed smoke;
- E2E crítico em PostgreSQL;
- frontend lint;
- TypeScript `--noEmit`;
- build de produção Next.js.

A validação comercial de providers externos específicos continua dependendo de endpoints/tokens reais. Isso é UAT operacional, não será representado por mocks como se fosse cobertura real do fornecedor.
