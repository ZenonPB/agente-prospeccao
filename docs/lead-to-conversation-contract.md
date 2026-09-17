# Lead → Conversation — contrato operacional

## Objetivo

Transformar uma oportunidade comercial em uma conversa rastreável sem criar um segundo CRM, um segundo motor de sequência ou um segundo caminho de envio. O bloco consolida `OutreachService`, `CadenceService`, `SequenceService`, `InboundEmailService`, `Message`, `FollowUp`, `CommercialTask`, supressões e o histórico comercial existentes.

## Fluxo canônico

`Opportunity/Lead → pessoa contatável → preparação baseada em evidências → revisão humana → envio → thread → resposta/bounce/STOP → pausa/cancelamento → reunião/tarefa seguinte`.

## Fontes de verdade

- `Contact`/People & Contact Intelligence decide se há pessoa/canal adequado; ausência ou falha continua UNKNOWN quando aplicável.
- `OutreachService` produz rascunho; não é fonte de fatos sobre a empresa.
- `FollowUp` representa a cadência legada de e-mail e continua sendo o único caminho de SMTP.
- `SequenceService` orquestra ações/tarefas e não cria outro sender.
- `Message` e atividades registram a conversa/histórico.
- `EmailSuppression` e `Lead.opt_out` são gates de segurança, não sugestões.

## Invariantes bloqueadores

1. Nenhum envio automático para contato heurístico/não verificado.
2. Nenhum envio após opt-out, supressão ou estado terminal.
3. Resposta recebida pausa a sequência antes de qualquer novo contato automático.
4. STOP encerra a sequência e mantém do-not-contact.
5. Bounce permanente suprime o endereço; falha transitória é limitada e observável.
6. Toda resolução inbound e toda mutação comercial é org-scoped.
7. `EmailSuppression` é deliberadamente global por endereço no schema atual: um endereço marcado por bounce permanente é bloqueado em todas as organizações. O `organization_id` registrado indica a origem da supressão para diagnóstico, não cria escopo de tenant. Alterar essa política exige migration e decisão explícita de produto/deliverability.
8. Threading preserva Message-ID/References das etapas anteriores.
9. Conteúdo gerado só pode afirmar fatos observados/provenientes. Hipóteses de scoring, `primary_need`, `pitch_angle` e inferências devem ser apresentadas como hipótese, nunca como fato observado.
10. Toda mensagem de e-mail da cadência contém mecanismo de opt-out, inclusive follow-ups e closing, mesmo se o modelo omitir.
11. LinkedIn/WhatsApp permanecem assistidos neste bloco; nenhuma automação agressiva é adicionada.
12. Falha de notificação/analytics não pode invalidar uma resposta inbound legítima, mas deve gerar diagnóstico acionável sem segredo/PII desnecessária.
13. O bloco não altera Aderência nem promove Commercial Dimensions shadow.

## Critério de pronto

O bloco só pode ser mergeado quando testes cobrirem: geração grounded, opt-out em todas as etapas, envio humano vs automático, e-mail verificado, política global de suppression, retry/bounce, reply/STOP, pausa de sequence, threading, idempotência disponível, estados terminais, tenant isolation e regressão do People & Contact Intelligence. O CI oficial deve estar verde no HEAD exato da PR.
