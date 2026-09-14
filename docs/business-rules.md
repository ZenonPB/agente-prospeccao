# Regras de negócio

> **LIVE · atualizado em 2026-09-13.** Regras aqui devem corresponder ao código
> e testes atuais; histórico de decisões fica em `decisions.md`/`adr/`.

## Workspace e acesso

1. Dados comerciais pertencem a uma `Organization`.
2. Membership define papel administrativo e papel de vendas.
3. OWNER/ADMIN e ANALYST/MANAGER têm acesso total da organização.
4. CONSULTOR vê leads atribuídos a si e pool não atribuído conforme helper
   canônico de escopo.
5. UUID de outro workspace nunca concede acesso.

## Campanha e oferta

1. Campanha pertence a um workspace.
2. `offer_profile_key` identifica a oferta declarativa quando conhecida.
3. O catálogo base é fallback; versão ativa publicada no workspace prevalece.
4. Uma Company/Lead pode ter múltiplas oportunidades/ofertas simultâneas.
5. Alterar OfferProfile futuro não reescreve snapshots/outcomes passados.

## Discovery

1. Providers externos são opt-in quando exigem credencial/custo.
2. Quotas e secrets são resolvidos por organização.
3. Candidates são deduplicados por identidade forte antes de enriquecimento caro.
4. CNPJ/domínio/source ids têm precedência sobre fuzzy merge.
5. Fuzzy match cria revisão, não merge destrutivo automático.
6. Provider caro roda depois de gates baratos sempre que possível.

## Evidência

1. `UNKNOWN` não equivale a negativo.
2. FACT/INFERENCE/HYPOTHESIS são distintos.
3. Sinal usado em score precisa ser explicável por dado observado/regra.
4. Provenance deve ser preservada quando o dado é externo.

## Pre-scoring e scoring

1. Pre-scoring reduz custo, não deve apagar silenciosamente auditoria de
   candidatos descartados.
2. OfferMatcher usa sinais/pesos declarados pela oferta.
3. Score breakdown e evidência são persistidos com oportunidade/snapshot.
4. Re-scoring de versão nova preserva histórico.

## Pessoas e contato

1. Person é canônica; Contact legado pode existir durante transição.
2. Buyer role/role fit e identity confidence são gates explícitos.
3. Dados incertos não são promovidos a decisor confirmado.
4. Routability é separada de identidade: saber quem é não implica saber como
   contactar com segurança.
5. Opt-out/suppression sempre bloqueiam envio automático permitido.

## CRM

1. Lead guarda estado comercial (owner/status/valor/previsão/próxima ação).
2. `CommercialTask` é fonte de verdade para tarefas.
3. `LeadActivity` é trilha auditável de mudanças/eventos comerciais.
4. Opportunity 360/Company 360/Person 360 são composições, não novas fontes.
5. Timeline é derivada.
6. Motivo de perda deve ser explícito quando fluxo exigir.

## Outcomes

1. Outcome real deve pertencer ao workspace e Lead corretos.
2. Quando houver múltiplas oportunidades, attribution deve apontar a
   `LeadOpportunity` correta.
3. BI não inventa attribution ausente.
4. Conversão/outcome são insumo de learning, não comando automático de mudança.

## Learning

1. Feedback é auditável e privado ao workspace.
2. Learning produz proposta/evidência.
3. Publicação exige ação humana explícita.
4. Uma versão ativa por offer key/workspace.
5. Rollback é exato para snapshot publicado.
6. Nenhum loop paralelo de template pode sobrescrever silenciosamente a mesma
   responsabilidade do OfferProfile.

## Importação histórica

1. Preview/dry-run antes de escrita.
2. Mapping de coluna explícito.
3. Dedupe por entidades canônicas.
4. Erro por linha reportado.
5. Reimportação não deve duplicar registros já reconhecidos.
6. Arquivo/origem fica auditável.
7. O lifecycle persistido usa `DRAFT`, `PREVIEWED`, `QUEUED`, `RUNNING`,
   `SUCCEEDED`, `PARTIAL`, `FAILED`, `CANCEL_REQUESTED` e `CANCELLED`; estados
   terminais não aceitam novas mutações.
8. A confirmação é idempotente por `(organization_id, idempotency_key)` e o
   consumer só reivindica importações com `organization_id` válido.
9. Identidade ambígua ou baseada somente em nome vira revisão explícita; não há
   merge destrutivo, e `UNKNOWN` permanece diferente de não encontrado.
10. Fórmulas são rejeitadas, HTML é tratado como texto escapado em preview e
    URLs importadas não são buscadas pelo servidor.

## Operações em massa de leads

1. `GET /api/leads` mantém compatibilidade offset e oferece cursor estável para
   paginação incremental.
2. O bulk expõe somente as operações allowlist `status` e `assign`, com máximo
   de 100 registros por operação.
3. O fluxo é sempre preview → confirmação → execute; cada item pode resultar em
   `accepted`, `duplicate`, `rejected` ou `failed`.
4. `expected_updated_at` é validado fail-closed para evitar sobrescrever uma
   alteração concorrente.
5. Tenant/RBAC são aplicados na seleção e na execução; `CommercialBulkOperation`
   funciona como ledger técnico da operação.
6. Bulk status usa a transição canônica, registra `LeadActivity`/outcome e
   cancela a cadência quando o estado for terminal.
7. A UI limita a seleção, preserva estados parciais, repete com a mesma
   idempotency key e mantém rejeitados/falhos selecionados disponíveis.
8. A migration `f2b3c4d5e6f7` garante o backfill/default de `Lead.updated_at`,
   usado pelo controle de concorrência.

## Automação e mensagens

1. Sequence/workflow não criam bypass de opt-in/suppression.
2. Automação materializa tarefas/ações por caminhos persistidos e auditáveis.
3. Nenhuma integração externa pode enviar em nome do usuário sem gate e
   configuração prevista no produto.

## Regra do RC

Uma capability só é considerada concluída se o fluxo real, segurança e testes
necessários estiverem entregues; helper/placeholder/registry isolado não basta.
