################################
O que pode melhorar — em ordem de impacto real
1. Os dois itens do backlog adiados merecem atenção

4.27 — Separação Company/Person é o que vai começar a doer mais rápido conforme a base crescer. Hoje um lead representa tanto a empresa quanto um contato de decisor — funciona no MVP, mas quando a EJ tiver múltiplos consultores prospectando, vai ter o mesmo decisor criado N vezes em leads diferentes sem nenhuma ligação. A ADR documenta isso, mas vale reavaliar um subset menor: mesmo sem o modelo completo de 3 entidades, uma chave de dedupe por contato (email global, não só por lead_id) já evita o problema mais doloroso.

4.20 — Integração Drive/Sheets OAuth foi adiada pelo custo de configuração, mas tem uma alternativa mais rápida: um endpoint de POST /webhooks/import que aceita um JSON-array de leads já parsado permitiria que qualquer automação (n8n, Make, Zapier, até um Apps Script) postasse leads sem OAuth. O webhook de outbound já existe — o de inbound de leads seria trivial.

2. Falta licença

O README tem [![license-unspecified] e o texto final pede pra entrar em contato. Se isso for usado por outras EJs ou clientes, a ausência de licença é um problema. Pra software interno: MIT resolve. Se tiver intenção comercial: AGPL ou licença proprietária. Vale decidir logo.

3. O campo qualification_threshold por org cria um risco silencioso

A decisão de deixar o threshold configurável por org (4.18) é boa. Mas se um owner/admin baixar o threshold para 30, leads fracos entram no outreach automático sem nenhum aviso. Falta um alerta na UI quando o threshold está muito abaixo do default (60) — um banner simples nas configurações já resolve.

4. Sem monitoramento de entregabilidade pós-envio

O checklist de aquecimento está bem documentado, mas não há nenhum mecanismo de alerta quando a taxa de bounce de uma org ultrapassar um limiar. O campo email_suppressions existe, mas o dado não vira um alerta ativo. Uma regra simples: se bounced_today / sent_today > 5%, pausa o auto-send e notifica o owner — isso protege a reputação do domínio antes que o dano seja irreversível.

5. O tour guiado (guided-tour-manager) pode ser muito intrusivo

Vejo que há um sistema de tour (tour-steps.ts, guided-tour-manager.tsx, tour-card.tsx). Tours que aparecem toda vez que o usuário entra são um dos maiores motivos de abandono em ferramentas B2B. Garanta que o estado do tour é persistido no backend (a migration a1b2c3d4e5f7 adiciona onboarding_status em users — ótimo), e que o tour nunca reaparece depois de dispensado.

6. Testes de integração end-to-end estão concentrados em um arquivo

tests/e2e_outreach_cycle.py cobre o ciclo principal, mas a maioria dos ~307 testes são unitários com mocks. Para operação real da EJ, os caminhos críticos (coleta → enriquecimento → scoring → cadência) deveriam ter pelo menos 2-3 testes de integração contra banco real (mesmo que com dados sintéticos), rodando no CI. O docker-compose.yml já existe, então subir um banco de teste no GitHub Actions seria direto.

7. Pequena inconsistência de segurança

No rate_limit.py (services/api/src/middleware/rate_limit.py) o rate limiting está implementado, mas o README menciona "rate limiting em auth endpoints como middleware FastAPI (ex: slowapi)" nas ADRs de segurança — vale verificar se o slowapi está de fato aplicado especificamente nos endpoints /auth/login e /auth/register, que são os mais sensíveis a brute-force.

################################
O que limita a generalidade hoje
1. O enriquecimento técnico é enviesado para empresas com site

O technical_enrichment_service analisa CMS, SSL, load time, SEO — coisas que só fazem sentido pra quem vende serviços digitais. Pra uma campanha de engenharia mecânica prospectando indústrias, esses dados são irrelevantes ou até distorcem o score.

O sistema até tenta contornar isso com o flag requires_technical_report no template — se o template de Eng. Mecânica não seta esse flag, o enriquecimento técnico é pulado. Mas aí o lead fica com menos evidências e o score sofre por falta de dados, não por falta de fit.

O que falta: cada template precisaria declarar explicitamente quais sinais de enriquecimento importam pra aquela vertente. Hoje o flag é binário (faz ou não faz análise técnica). Precisaria ser: "pra engenharia mecânica, enriqueça CNPJ + porte da empresa + setor CNAE + localidade industrial. Ignore site."

2. As fontes de coleta são boas pra B2C local, limitadas pra B2B industrial

Google Places funciona bem pra prospectar restaurantes, salões, clínicas. Pra indústrias, distribuidoras, construtoras — os dados são escassos ou desatualizados. Uma fábrica em Sorocaba pode não aparecer no Google Maps como resultado útil.

O que falta para indústrias e B2B pesado:

Coleta via CNAE com filtros de porte (número de funcionários, faturamento presumido via Simples/Lucro Real) — isso já existe parcialmente no cnae_discovery_service, mas sem filtragem de porte
Importação de listas de associações setoriais (FIESP, ABIMAQ, etc.) via CSV já funciona, mas poderia ter um parser específico pra esses formatos
Coleta via licitações públicas (PNCP) — empresas que ganham licitações são pistas de porte e setor, sem custo de API
3. O outreach é bom pra e-mail, fraco pra ciclos de venda longos

A cadência dia 0/3/7/14 funciona bem pra serviços de ticket baixo/médio com decisão rápida. Pra engenharia mecânica ou automação industrial, o ciclo pode ser de 3 a 6 meses, com múltiplos decisores (compras, engenharia, diretoria).

O que falta:

Cadência configurável por template (dia 0/7/30/60 pra vendas longas)
Suporte a múltiplos contatos no mesmo lead com papéis diferentes ("compras", "engenheiro responsável", "diretoria") — hoje tem a tabela de contatos, mas a cadência manda pra um único destinatário
Sequência de conteúdo diferente por estágio (awareness → interesse → proposta), não só follow-ups do mesmo e-mail
4. Os critérios de qualificação são estáticos dentro de cada template

Um template define os critérios uma vez. Mas o que qualifica um lead muda conforme o histórico da própria campanha: se os primeiros 50 leads que viraram cliente tinham CNPJ com mais de 5 anos e faturamento acima de determinado porte, o sistema deveria aprender isso e recalibrar os pesos.

O loop de feedback existe (resultado ganhou/perdeu → calibra próximo ciclo), mas ele é manual e passa pelo threshold automático (4.18). Não há nada que aprenda quais características distinguem leads ganhos de perdidos dentro de cada vertente.

O que falta: após N conversões registradas, rodar uma análise de correlação simples (quais evidence[] apareciam nos leads ganhos vs. perdidos) e sugerir ajustes nos pesos do template. Não precisa ser ML sofisticado — até uma frequência relativa já ajuda.

5. Falta um "configurador de vertente" na UI

Hoje criar um template novo exige SQL ou editar o seed. Pra o sistema ser genuinamente genérico e autossuficiente, qualquer usuário com perfil de admin deveria conseguir criar uma nova vertente pela UI: nomear o serviço, descrever o ICP, definir quais sinais importam, e o sistema gera um template via LLM que pode ser refinado.

O endpoint de scoring-templates já tem CRUD. O que falta é a tela no frontend — que poderia inclusive usar a mesma LLM pra sugerir os critérios a partir de uma descrição em linguagem natural ("quero prospectar indústrias de alimentos pra vender manutenção de compressores").

Resumo do que implementar pra generalidade real

Em ordem de impacto:

Enriquecimento por perfil de vertente — cada template declara quais steps de enriquecimento ativar (técnico / CNPJ-porte / Places / nenhum). Hoje é binário, precisa ser uma lista.
Cadência configurável por template — intervalo, número de steps e tom ajustáveis. Ciclos curtos pra serviços digitais, longos pra industrial.
Tela de criação de vertente na UI — o CRUD de templates já existe na API, precisa de uma interface que qualquer analista consiga usar sem tocar em SQL.
Coleta por porte via CNAE — filtrar por faixas de funcionários/faturamento presumido via dados públicos da Receita. Pra B2B industrial isso é mais relevante que qualquer coisa do Google Maps.
Suporte a múltiplos decisores na cadência — hoje a tabela de contatos tem tudo, falta o outreach_service orquestrar envios para papéis diferentes no mesmo lead.
Loop de feedback com aprendizado de template — correlacionar características dos leads ganhos com os pesos dos critérios e sugerir calibração.


############
OUTRAS


A página de oportunidades tem 57KB em um único arquivo.
oportunidades/[id]/page.tsx tem 57 mil caracteres. Isso significa tempo de carregamento alto, dificuldade de manutenção, e provavelmente re-renders desnecessários. Pra uma tela que um consultor vai abrir dezenas de vezes por dia, isso importa.

Não há estado de "carregando" granular no pipeline.
O WebSocket transmite eventos em tempo real, mas se a conexão cair no meio de uma coleta (instável no mobile, por exemplo), não há reconexão automática. O consultor fica olhando pra uma tela travada sem saber se o processo ainda está rodando ou morreu.

O campo next_action_at não tem nenhuma lógica de sugestão.
O SLA alerta quando um lead está parado, mas o sistema não sugere quando o próximo contato deve acontecer baseado no estágio do funil. O consultor tem que preencher manualmente toda vez — o que na prática significa que ninguém preenche.

Não há busca global.
Se um consultor lembra o nome de uma empresa mas não sabe em qual campanha está, não tem como encontrar rápido. O filtro de leads aceita search, mas é dentro de uma campanha. Uma busca cross-campanha seria trivial de implementar e faz diferença no dia a dia.

O kanban não tem filtro por consultor.
Num cenário com 4–5 consultores, o kanban mostra tudo misturado. Cada consultor precisa filtrar manualmente. Um toggle "Ver só os meus" resolveria.

As mensagens geradas pela IA não têm histórico de versões.
Se o consultor gerar mensagem, editar, e depois gerar de novo — a versão editada some. Não há como comparar ou recuperar. Pra quem afina copywriting com o tempo, isso é perda de trabalho.

Não há notificação quando um lead responde.
O inbound de e-mail processa a resposta e muda o status pra RESPONDIDO — mas o consultor responsável não recebe nenhum aviso. Ele precisa abrir o app pra descobrir. Em vendas, velocidade de resposta é tudo.

O relatório PDF é gerado sob demanda mas não é cacheado.
Toda vez que alguém abre o PDF executivo, o WeasyPrint roda do zero. Pra diretores que abrem toda semana na reunião, isso é latência desnecessária. Um cache simples por (org_id, date) já resolve.

Não há modo "pausar campanha".
Se uma campanha está gerando leads ruins ou a equipe está sobrecarregada, a única opção é não usar. Não existe pausar coleta sem deletar a campanha. Um status PAUSADA evitaria que novas coletas fossem disparadas sem perder o histórico.

O lost_reason é texto livre.
Quando o consultor perde um lead, pode escrever qualquer coisa. Isso inviabiliza qualquer análise de motivos de perda — que é uma das informações mais valiosas pra calibrar o ICP. Um enum com categorias principais (preço, timing, concorrente, sem interesse, sem resposta) mais um campo opcional de observação livre seria muito mais útil.