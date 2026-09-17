# Omnichannel + Relationship Intelligence

## Objetivo

Este bloco consolida os canais assistidos e a memória comercial sobre as fontes já existentes. Ele não cria automação agressiva de LinkedIn/WhatsApp e não cria um segundo CRM.

## Fontes canônicas já existentes

- `Lead`, `Contact`, `LeadActivity`, `Message`, `FollowUp` e `Conversion` formam a trilha operacional.
- `WHATSAPP_SENT` registra uma ação humana iniciada no sistema.
- `LINKEDIN_ASSOCIATED` registra associação/revisão assistida de um perfil.
- e-mail/cadência permanecem sob `CadenceService`/`InboundEmailService`.
- opt-out, suppression e estados terminais têm precedência sobre qualquer sugestão de novo contato.

## Contrato de relacionamento

Relationship Intelligence é **derivada da trilha persistida**, não um segundo status mutável. A leitura deve responder, com provenance:

- `NEVER_CONTACTED`: nenhuma ação comercial observada;
- `PROSPECTING`: houve contato, mas nenhuma resposta observada;
- `ENGAGED`: houve resposta/reunião/proposta observada;
- `CUSTOMER`: existe conversão/venda persistida;
- `LOST`: oportunidade comercial marcada como perdida;
- `DISQUALIFIED`: lead inadequado; não equivale a perda;
- `DO_NOT_CONTACT`: opt-out/suppression tem precedência sobre todos os demais estados.

Estados mais fortes prevalecem sobre estados anteriores. Uma empresa cliente continua cliente mesmo que tenha histórico de prospecção. `DO_NOT_CONTACT` é uma restrição de contato, não evidência de baixa aderência.

## Canais assistidos

### WhatsApp

O produto prepara o link/mensagem e registra a ação somente quando o usuário efetivamente aciona o canal. O backend nunca afirma que a mensagem foi entregue ou lida a partir de um clique em `wa.me`.

### LinkedIn

O produto ajuda a localizar e associar o perfil. Associação manual precisa manter `source`, confiança e estado de validação. Não há scraping agressivo nem envio automático.

## Invariantes

1. toda leitura/escrita comercial é org-scoped;
2. CONSULTOR continua limitado ao próprio funil segundo as regras existentes;
3. nenhum canal pode contornar opt-out/suppression;
4. canal institucional não vira contato pessoal por inferência;
5. `UNKNOWN` não vira `FALSE`;
6. ação assistida não é apresentada como entrega/resposta confirmada;
7. memória de relacionamento é derivada de eventos persistidos e determinística;
8. não criar novo enum/coluna se a informação puder ser derivada com segurança da trilha existente;
9. o bloco deve permanecer backward-compatible e sem provider pago obrigatório;
10. CI oficial verde no HEAD exato é requisito para merge.
