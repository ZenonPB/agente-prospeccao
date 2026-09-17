# Omnichannel + Relationship Intelligence

Este bloco estende o CRM existente sem criar um segundo motor de outreach.

## Objetivo

Preservar contexto comercial antes de qualquer abordagem e tratar LinkedIn/WhatsApp como canais assistidos. A memória de relacionamento deve impedir que uma empresa já cliente, parceira ou explicitamente bloqueada volte silenciosamente ao fluxo de prospecção fria.

## Invariantes

- `Company`, `Person`, `Lead`, `LeadActivity`, `Message`, `FollowUp`, `SequenceService`, `CadenceService` e `OutreachService` continuam canônicos.
- WhatsApp e LinkedIn permanecem **assistidos**: o sistema pode preparar a ação, mas não executa automação externa agressiva.
- opt-out, suppression, bounce e bloqueio explícito têm precedência sobre qualquer sugestão de canal.
- relacionamento é tenant-scoped e não pode vazar entre organizações, mesmo para o mesmo CNPJ/domínio/e-mail.
- uma oportunidade comercial e um relacionamento institucional são dimensões diferentes: parceiro/cliente não deve ser reclassificado como cold lead só por novo scoring.
- toda mudança humana de relacionamento é auditável e usa concorrência otimista.
- estados desconhecidos não são convertidos em `PROSPECT` por ausência de dados.

## Estados

O estado canônico de relacionamento é independente do `LeadStatus` operacional:

- `UNKNOWN`: ainda não classificado.
- `PROSPECT`: relação comercial de prospecção confirmada.
- `ENGAGED`: já houve interação comercial relevante.
- `CUSTOMER`: cliente atual.
- `FORMER_CUSTOMER`: cliente anterior.
- `PARTNER`: parceiro institucional/comercial.
- `DO_NOT_CONTACT`: não abordar.

A origem (`relationship_source`) e a observação (`relationship_observed_at`) devem acompanhar o estado para diferenciar classificação humana de inferências futuras.

## Canais

LinkedIn e WhatsApp devem expor uma ação preparada com destino, contexto e mensagem sugerida. O clique/execução humana pode gerar `LeadActivity`, mas não equivale a confirmação de entrega ou resposta. Uma resposta só deve avançar o relacionamento quando registrada por evidência própria do canal ou ação humana explícita.

## Gate de cold outreach

Antes de preparar/enviar cold outreach, a política deve consultar o relacionamento da Company. `CUSTOMER`, `PARTNER` e `DO_NOT_CONTACT` bloqueiam cold outreach. `FORMER_CUSTOMER` exige abordagem de relacionamento/reativação, não cold outreach. `UNKNOWN` permanece desconhecido e não é evidência positiva nem negativa.
