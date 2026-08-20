# Melhorias em aberto

> Este arquivo lista **apenas o que ainda não foi resolvido**. Itens já
> implementados foram removidos (o estado e o histórico ficam em
> `docs/context.md`). Ordenação por impacto real na operação da EJ.

## Operação

1. **Avisar o consultor quando o lead responde.** O inbound de e-mail marca
   `RESPONDIDO` (e cancela a cadência), mas ninguém é notificado — o consultor
   só descobre abrindo o app. Em vendas, velocidade de resposta decide. Mínimo
   viável: alerta in-app (badge no kanban + "Ações de hoje") para o responsável
   do lead.
2. **Reconexão automática do WebSocket.** Se a conexão cai no meio de uma
   coleta (link móvel), `campaign-pipeline.tsx` e `pipeline-monitor.tsx`
   travam ("Erro na conexão WebSocket") sem tentar reconectar. O job é
   resgatável (`GET /api/pipeline/jobs`), falta o re-connect com backoff +
   banner de re-sync do estado.
3. **Filtro "ver só os meus" no kanban.** A lista de oportunidades já tem o
   preset `my_leads`; o kanban mistura todos os consultores. Um toggle reusando
   `assigned=me` do backend resolve — cenário com 4–5 consultores.
4. **Sugerir o próximo contato (`next_action_at`).** Hoje o preenchimento é
   manual — e na prática ninguém preenche. Sugerir por estágio do funil (ex.:
   `QUALIFICADO` → +1 dia, `RESPONDIDO` → +2 dias) no PATCH de status,
   mantendo a edição manual.
5. **Histórico de versões das mensagens geradas pela IA.** Gerar ou editar uma
   mensagem descarta a anterior — sem comparar nem recuperar. Persistir versões
   (rascunho × enviada) por lead resolve a perda de trabalho de tuning de
   copywriting.

## B2B industrial / generalidade

6. **Múltiplos decisores na cadência.** `_recipient_email` envia para um único
   destinatário. Ciclos industriais têm compras + engenharia + diretoria: é
   preciso rotear etapas — ou oferecer a escolha do papel — entre os contatos
   do lead.
7. **Sequência de conteúdo por estágio (awareness → interesse → proposta).**
   Hoje os follow-ups repetem o mesmo eixo de mensagem. Conteúdo diferente por
   etapa (educativo → caso → proposta) exige declarar isso na vertente/playbook.
8. **Filtro de porte na coleta CNAE.** `cnae_discovery_service` coleta por
   código, mas sem filtrar porte (nº de funcionários / faturamento presumido
   via Simples/Lucro Real). Para B2B industrial isso importa mais que dados do
   Maps.
9. **Loop de aprendizado por vertente.** Sem correlação entre características
   (`evidence[]`) de leads convertidos × perdidos, os pesos do template nunca
   se recalibram — o feedback de conversão existe, mas a calibração é manual.
   Frequência relativa já bastaria para sugerir ajustes.
10. **Importação de listas setoriais (FIESP, ABIMAQ…).** O CSV genérico
    funciona, mas um parser específico desses formatos (colunas variáveis)
    destrava associações sem tratamento manual.
11. **Coleta via licitações públicas (PNCP).** Empresas que vencem licitações
    indicam porte e setor, sem custo de API. É o item mais pesado desta lista.

## Qualidade de código

12. **Quebrar `oportunidades/[id]/page.tsx` (~56KB).** Custo de carregamento,
    manutenção e re-renders numa tela que o consultor abre dezenas de vezes ao
    dia.

## Infra & produto

13. **Licença.** `README.md` segue `license-unspecified` — decisão pendente
    da diretoria: MIT (software interno) ou AGPL/proprietária (uso comercial).
14. **Testes de integração no CI com banco real.** `e2e_outreach_cycle.py`
    existe, mas roda só com `E2E_DATABASE_URL` (pulado no CI). Subir Postgres de
    teste no GitHub Actions (`docker compose up db`) e rodar 2–3 fluxos
    críticos (coleta → enriquecimento → scoring → cadência) elevaria a
    confiança para a operação real.