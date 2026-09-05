# Mapa de pendências pós-consolidação

> Documento de planejamento operacional. Ele descreve o estado real do sistema
> depois da consolidação de ofertas, discovery, oportunidades, eventos,
> outcomes e inteligência comercial. Não trate uma capacidade como completa
> apenas porque existe uma classe, endpoint ou teste isolado: o critério é o
> fluxo real integrado, persistido, observável e utilizável.

## 1. Como ler este mapa

### Status

- **✅ Operacional:** existe consumidor no fluxo principal, persistência quando
  aplicável, contrato documentado e testes relevantes.
- **🟠 Parcial:** uma parte funciona, mas falta integração, fonte real, qualidade
  de dados, UX ou garantia operacional para produção.
- **🔵 Estrutural:** existe contrato, helper ou implementação de base, mas ainda
  não há consumidor de produção suficiente para chamar a capacidade de completa.
- **⬜ Planejado:** ainda não há implementação funcional no caminho principal.
- **⏸ Adiado:** decisão consciente registrada em documentação/ADR; não deve ser
  reaberto sem uma necessidade concreta do produto.

### Definition of Done deste mapa

Uma pendência só deve ser marcada como **✅ Operacional** quando:

1. há contrato público estável;
2. há consumidor real no pipeline ou na UI;
3. a organização/tenant correto é aplicado em todas as leituras e escritas;
4. há persistência e versionamento quando o resultado precisa ser auditado;
5. erro, ausência de dados e desconhecido são estados diferentes;
6. há testes unitários e pelo menos um teste de integração do fluxo;
7. há logs/métricas suficientes para diagnosticar falhas;
8. a documentação corresponde ao comportamento real;
9. a interface não afirma sucesso quando apenas enfileirou ou tentou uma ação;
10. o fluxo foi validado com dados reais ou um ambiente controlado equivalente.

## 2. O que já está operacional hoje

Estas capacidades não são o foco imediato do backlog, mas devem ser preservadas
durante as próximas mudanças:

| Capacidade | O que funciona | Evidência |
|---|---|---|
| Scoring contextual | Templates, score 0–100, status de qualificação e evidências | `scoring_service.py`, templates e testes de scoring |
| Pré-scoring | Gate determinístico, threshold/top-k e auditoria de descartes | `candidate_pre_scoring_service.py`, `prescoring_discards` |
| Enriquecimento adaptativo | Site, Receita/CNPJ e caminhos por perfil | `enrichment_orchestrator.py` |
| OfferProfile | Resolução explícita com fallback para campanhas legadas | `offer_profile.py`, `pipeline_worker.py` |
| OfferMatcher | Uma empresa pode ter múltiplas ofertas simultâneas | `lead_opportunities`, endpoint de oportunidades |
| Discovery de empresas | Places/CNAE via executor declarativo e orçamento global | `discovery_executor.py`, `pipeline_worker.py` |
| Isolamento multi-tenant | Rotas novas filtram organização e escopo do consultor | dependências de organização + rotas de leads/intelligence |
| Jobs do pipeline | Execução em background, WebSocket autenticado e restauração de resumo | `jobs_consumer.py`, `routes/pipeline.py` |
| Outcomes básicos | Resposta, reunião, perda e conversão persistidos de modo idempotente | `commercial_outcomes`, `CommercialOutcomeService` |
| Inteligência inicial | Eventos futuros e métricas básicas por oferta na página de relatórios | `IntelligenceSection` |
| Validação técnica | Suíte Python, compileall, lint, TypeScript e build Web | estado registrado em `docs/context.md` |

## 3. Backlog priorizado

### P0 — Validação de produção e confiabilidade do fluxo atual

#### P0.1 Rodar o E2E com PostgreSQL e credenciais controladas

- **Status:** 🟠 Parcial.
- **O que falta:** executar `tests/e2e_outreach_cycle.py` com
  `E2E_DATABASE_URL`, migrations aplicadas e stubs de LLM/SMTP configurados.
- **Por que falta:** a suíte unitária prova contratos isolados, mas não prova a
  sequência completa request → job → worker → banco → WebSocket → UI.
- **Escopo:** ambiente de teste controlado; não usar chaves de produção.
- **Critério de aceite:** criação de campanha, coleta, scoring, geração de
  mensagem, cadência, resposta e conversão passam em uma execução repetível.
- **Dependências:** PostgreSQL, `alembic upgrade head`, variáveis de teste e
  fixture de organização/usuário.

#### P0.2 Validar migrations em banco limpo e banco já existente

- **Status:** 🟠 Parcial.
- **O que falta:** executar upgrade desde o primeiro head suportado e confirmar
  rollback apenas em ambiente descartável.
- **Por que falta:** a migration estar no head local não garante que a sequência
  funciona em uma instalação antiga ou em uma base com dados reais.
- **Critério de aceite:** upgrade limpo e upgrade incremental passam; índices,
  constraints e FKs das tabelas novas são confirmados no PostgreSQL.

#### P0.3 Corrigir a política de warnings Python 3.14

- **Status:** 🟠 Parcial.
- **Problema:** a execução com `-W error` encontra a depreciação de
  `asyncio.iscoroutinefunction` usada pelo `slowapi` instalado no ambiente.
- **Por que importa:** CI pode tratar warnings como erro e bloquear merges mesmo
  quando o comportamento funcional está correto.
- **Critério de aceite:** suíte com `-W error` passa, seja por atualização
  compatível de dependência, patch upstream ou política explícita de versão
  Python suportada.

### P1 — Event Discovery ponta a ponta

#### P1.1 Provider externo de eventos real

- **Status:** 🟠 Parcial.
- **Hoje:** `EVENT_DISCOVERY_URL` habilita um provider HTTP opt-in; sem a variável
  o collector externo fica desabilitado.
- **O que falta:** escolher uma fonte real, validar contrato JSON, autenticação,
  timeout, retry, limites, observabilidade e testes com respostas reais.
- **Por que importa:** sem provider configurado, o sistema apenas executa o
  fluxo e pode retornar zero eventos; isso não equivale a uma descoberta real.
- **Critério de aceite:** erro da fonte aparece como erro de coleta, não como
  “nenhum evento”; respostas inválidas são rejeitadas e o provider é monitorado.

#### P1.2 Evento → organizador → lead

- **Status:** 🟠 Parcial.
- **Hoje:** o evento é normalizado, o organizador recebe resolução best-effort,
  timing é calculado e o evento é salvo em `event_opportunities`.
- **O que falta:** procurar/criar o `Lead` do organizador, resolver CNPJ/empresa,
  associar o evento ao lead e preservar a provenance dessa associação.
- **Por que importa:** o sistema atualmente descobre um sinal, mas não o coloca
  automaticamente no funil comercial.
- **Critério de aceite:** um evento válido produz uma associação rastreável com
  empresa existente ou um estado explícito de “organizador não resolvido”, sem
  criar duplicatas.

#### P1.3 Evento → oferta → decisor → outreach

- **Status:** 🔵 Estrutural.
- **O que falta:** executar OfferMatcher para o evento/organizador, aplicar timing
  ao ranking, rodar resolução de decisor e preparar uma ação de outreach humana.
- **Por que importa:** é o critério de negócio da capacidade de eventos: evento
  futuro precisa virar oportunidade comercial rastreável, não apenas linha de
  relatório.
- **Critério de aceite:** a UI mostra a oferta, evidências, decisor sugerido,
  confiança, próxima ação e origem no evento; envio automático continua sujeito
  às regras de consentimento e opt-in existentes.

#### P1.4 Expiração e histórico de eventos

- **Status:** 🟠 Parcial.
- **Hoje:** a listagem principal filtra eventos cuja data já passou.
- **O que falta:** política explícita para `upcoming`, `expired`, `cancelled` e
  `unknown`, com job ou atualização idempotente de expiração.
- **Por que importa:** filtrar na leitura evita exibição incorreta, mas não
  organiza o histórico nem impede crescimento indefinido da tabela.
- **Critério de aceite:** eventos vencidos não entram em novas ações; o histórico
  continua auditável e a limpeza/arquivamento é mensurável.

### P1 — Intent Collection real

#### P1.5 Provider de vagas e outros sinais temporais

- **Status:** 🟠 Parcial.
- **Hoje:** `IntentProvider` e interpretação existem, mas parte do contexto,
  como vagas externas, precisa ser fornecida pelo caller.
- **O que falta:** job opt-in para `JobPostingIntentProvider` e, depois, providers
  de notícias, social e procurement conforme prioridade comercial.
- **Por que importa:** interpretar um sinal sem coletá-lo no fluxo de produção
  deixa o intent score vazio ou dependente de dados manuais.
- **Critério de aceite:** cada provider tem contrato, provenance, timestamp,
  confidence, TTL e distinção entre “não encontrado” e “provider falhou”.

### P1 — Outcomes e Learning Metrics

#### P1.6 Atribuição explícita de outcome à oferta

- **Status:** 🟠 Parcial.
- **Hoje:** quando uma conversão não informa a oferta, o sistema usa a
  oportunidade de maior score como fallback.
- **Problema:** um lead pode ter várias ofertas; a de maior score não é
  necessariamente a que foi vendida.
- **O que falta:** campo `offer_key`/`offer_version` na conversão e seleção da
  oportunidade na UI, mantendo o fallback apenas para dados históricos.
- **Critério de aceite:** toda nova conversão comercial tem oferta explícita ou
  estado `unknown` revisável; o BI não atribui silenciosamente uma oferta errada.

#### P1.7 BI por oferta, versão e variante

- **Status:** 🟠 Parcial.
- **Hoje:** endpoint e cartão exibem total, ganhos, taxa de conversão e ticket
  médio por oferta/versão.
- **O que falta:** comparação por período, vertical, consultor, etapa, canal,
  variante e tamanho de amostra.
- **Por que importa:** uma taxa simples não explica se a oferta é melhor ou se há
  apenas poucos dados enviesados.
- **Critério de aceite:** métricas têm filtros, período, amostra mínima e
  indicação clara de ausência de significância quando aplicável.

#### P1.8 A/B estatístico e aprendizado controlado

- **Status:** 🔵 Estrutural.
- **O que falta:** intervalo de confiança, regra de amostra mínima, comparação
  A/B por etapa/canal, recomendação de vencedor e processo de aprovação humana.
- **Por que importa:** primeiro medir; depois recomendar; só então permitir ajuste
  controlado. O sistema não deve alterar scoring ou outreach automaticamente por
  uma amostra pequena.
- **Critério de aceite:** nenhuma recomendação é exibida sem amostra mínima e
  toda alteração aplicada guarda versão, autor e evidência.

### P1 — Decisores e qualidade de dados

#### P1.9 Entidade canônica de pessoa/decisor

- **Status:** 🟠 Parcial.
- **Hoje:** contatos são persistidos e snapshots legados continuam sendo usados
  para compatibilidade.
- **O que falta:** consolidar `PersonContact`/entidade equivalente como fonte
  canônica, com identity resolution, vínculo empresa-pessoa e histórico de
  fontes.
- **Por que importa:** o mesmo decisor pode aparecer com nomes, cargos e fontes
  divergentes; isso prejudica confiança, roteamento e métricas.
- **Critério de aceite:** cada pessoa tem identidade estável, fontes/provenance,
  confidence, status de verificação e regra de merge auditável.

#### P1.10 Resolução real de decisores

- **Status:** 🟠 Parcial.
- **O que falta:** completar a sequência OfferProfile → cargos-alvo → empresa →
  pessoas → identidade → cargo → contato → verificação → ranking de canal.
- **Por que importa:** cargos desejados não são pessoas encontradas. O sistema
  precisa declarar falha quando não há decisor verificável.
- **Critério de aceite:** o pipeline retorna pessoas reais ou um estado explícito
  de falha/necessidade de revisão; nunca transforma apenas um role configurado em
  “decisor encontrado”.

### P2 — Extensibilidade comercial

#### P2.1 OfferProfile administrável sem alterar código

- **Status:** 🟠 Parcial.
- **Hoje:** perfis declarativos são resolvidos e versionados, mas os perfis
  padrão/customizados ainda são registrados em código.
- **O que falta:** persistência/configuração administrativa, tela de gestão,
  validação de schema, publicação de versão e auditoria de alterações.
- **Por que importa:** a promessa do modelo é adicionar oferta sem editar os
  engines centrais nem publicar código.
- **Critério de aceite:** um administrador cria, testa, publica e desativa uma
  oferta pela UI/API; campanhas antigas continuam funcionando por fallback.

#### P2.2 Remover mapeamentos legados apenas quando houver cobertura

- **Status:** 🟠 Parcial.
- **Hoje:** o caminho declarativo é prioritário, mas mappings legados ainda
  existem para compatibilidade.
- **O que falta:** medir uso do fallback, migrar campanhas, comparar resultados e
  só então remover caminhos mortos.
- **Critério de aceite:** nenhum mapping removido sem telemetria, migration de
  dados e plano de rollback.

### P2 — Frontend e contrato de interface

#### P2.3 Internacionalização/normalização de textos

- **Status:** 🟠 Parcial.
- **Hoje:** os fluxos novos estão traduzidos e os termos principais foram
  padronizados em PT-BR.
- **O que falta:** catálogo central de mensagens, labels de status/enum,
  normalização de mensagens WebSocket e cobertura automatizada contra textos em
  inglês.
- **Por que importa:** strings espalhadas em componentes permitem inconsistência
  e tornam outro idioma caro.
- **Critério de aceite:** textos de UI usam chaves/catálogos; códigos internos
  como `HOT`, `event_http` e `PROPOSTA_ENVIADA` nunca aparecem sem label humana.

#### P2.4 Contrato de eventos do WebSocket

- **Status:** 🟠 Parcial.
- **Hoje:** o backend envia eventos com mensagens livres e o frontend os renderiza.
- **O que falta:** códigos estáveis, parâmetros tipados e tradução no frontend.
- **Por que importa:** mensagens livres acoplam backend à cópia da UI e podem
  exibir nomes internos ou inglês.
- **Critério de aceite:** cada evento de UI tem schema versionado, código,
  parâmetros e fallback seguro para eventos desconhecidos.

#### P2.5 Auditoria em dispositivos reais

- **Status:** ⬜ Planejado.
- **O que falta:** validar pipeline, WebSocket, kanban drag-and-drop, navegação,
  foco de teclado e layout em pelo menos um celular/tablet real.
- **Por que importa:** build e responsividade CSS não provam interação por toque,
  rede instável ou viewport pequeno.
- **Critério de aceite:** checklist de QA com evidências e correções registradas.

### P2 — Segurança, performance e operação

#### P2.6 Backlog de segurança/performance

- **Status:** 🟠 Parcial.
- **Itens a acompanhar:** Swagger em produção, CORS restrito, limite de upload,
  redaction de e-mail em convite, rate limit de webhook, security headers,
  HTTPS/HSTS, claims `iss`/`aud`, invalidação de reset token, health check sem
  environment, isolamento de inbound email, lockout de login e otimizações de
  analytics/CSV/webhook.
- **Por que importa:** são riscos independentes do pipeline comercial e não devem
  desaparecer por a consolidação funcional estar verde.
- **Critério de aceite:** cada item tem teste/regra de deploy e status individual;
  não usar um único “backlog concluído” para esconder itens não verificados.

#### P2.7 Observabilidade operacional

- **Status:** 🟠 Parcial.
- **O que falta:** métricas de duração e falha por job/provider, contagem de
  eventos ignorados, taxa de organizadores resolvidos, outcomes desconhecidos,
  fallback de OfferProfile e uso de cotas.
- **Por que importa:** logs textuais não bastam para operar providers externos e
  diagnosticar diferenças entre “zero resultados” e “provider indisponível”.
- **Critério de aceite:** dashboards/alertas mínimos e correlation id por job,
  organização e provider.

## 4. Ordem recomendada de execução

### Onda 1 — Segurança operacional do que já existe

1. Executar E2E real e validar migrations em banco limpo/existente.
2. Resolver warnings/compatibilidade Python da suíte com `-W error`.
3. Adicionar observabilidade de jobs, providers, fallback e outcomes.
4. Fechar itens críticos de segurança/performance que ainda estiverem abertos.

### Onda 2 — Event Discovery utilizável

1. Selecionar provider externo e contrato.
2. Diferenciar provider indisponível de zero eventos.
3. Resolver organizador para empresa/lead com dedup.
4. Associar evento, oferta, evidência e próxima ação.
5. Só depois habilitar integração com decisor e outreach.

### Onda 3 — Outcomes confiáveis

1. Capturar `offer_key` e `offer_version` na conversão.
2. Corrigir atribuição de outcomes históricos e desconhecidos.
3. Criar filtros de BI por período/oferta/versão/canal.
4. Implementar amostra mínima e recomendação A/B sem aplicação automática.

### Onda 4 — Dados canônicos de decisores

1. Definir entidade estável de pessoa e vínculo com empresa.
2. Migrar contatos/snapshots com provenance.
3. Implementar identity resolution e merge auditável.
4. Tornar confidence e routability critérios reais da cadência.

### Onda 5 — Administração e experiência

1. Criar gestão de OfferProfiles e publicação de versões.
2. Criar catálogo de textos/labels e contrato tipado do WebSocket.
3. Validar mobile/tablet e acessibilidade em dispositivo real.
4. Consolidar documentação e remover apenas compatibilidades comprovadamente
   sem uso.

## 5. Dependências e decisões que precisam permanecer explícitas

- Provider externo de eventos é opt-in; não ativar scraping ou chamadas não
  aprovadas por padrão.
- Toda coleta de site e contatos continua passiva, conforme as regras de
  segurança e a Lei 12.737/2012.
- OfferProfile é a direção arquitetural, mas a remoção do legado deve ser
  incremental e observável.
- Outcomes desconhecidos devem permanecer revisáveis; não atribuir venda apenas
  por score sem indicar que foi fallback.
- Learning automático não deve alterar threshold, scoring ou outreach sem
  aprovação e versionamento.
- 4.20 (Drive/Sheets OAuth) e 4.27 (modelo completo Company/Person/Employment)
  permanecem adiados conforme `docs/decisions.md`; só voltar a eles com decisão
  de produto e escopo próprio.

## 6. Checklist de PR para cada pendência

- [ ] Atualizei `docs/context.md` e `docs/00-status-mapa.md`.
- [ ] Descrevi o contrato e o tenant scope.
- [ ] Adicionei testes de caminho feliz e falha.
- [ ] Adicionei migration nova se o schema mudou.
- [ ] Validei que UNKNOWN não virou FALSE silenciosamente.
- [ ] Validei que o backend não afirma sucesso antes do job terminar.
- [ ] Atualizei a UI para loading, erro, vazio e permissão.
- [ ] Rodei `python -m pytest tests -q`.
- [ ] Rodei `python -m compileall -q services/api services/workers`.
- [ ] Rodei `npm run lint`, `npx tsc --noEmit` e `npm run build`.
- [ ] Rodei `graphify update .` após mudanças de código.
- [ ] Registrei limitações de ambiente/dados reais no PR.

## 7. Referências

- `docs/context.md` — estado vivo e próximo passo imediato.
- `docs/00-status-mapa.md` — status das capabilities.
- `docs/consolidacao.md` — desenho alvo, fases e Definition of Done.
- `docs/roadmap-vendas.md` — prioridades comerciais e itens adiados.
- `docs/auditoria-frontend.md` — critérios de UX, performance e QA do Web.
- `docs/decisions.md` — decisões técnicas e adiamentos que não devem ser
  reabertos acidentalmente.