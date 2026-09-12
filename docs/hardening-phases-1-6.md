# Hardening transversal — Fases 1–6

Este documento registra o hardening transversal aplicado sobre as entregas das Fases 1–6. O objetivo foi aumentar segurança, correção semântica, desempenho, manutenibilidade e clareza operacional sem alterar as invariantes comerciais já consolidadas.

## Segurança e integridade

- Convites novos armazenam somente o SHA-256 do token; o segredo em texto puro existe apenas durante a criação do link enviado ao convidado.
- A migration `8e0f2a4c6d7b_hash_invite_tokens` normaliza convites persistidos existentes e mantém compatibilidade de rollout para tokens legados ainda em circulação.
- Convites continuam proibidos de conceder `OWNER`; transferência de propriedade permanece um fluxo separado e auditável.
- Verificação de e-mail passou a distinguir domínio com MX válido, domínio catch-all, verificação inconclusiva e caixa individual efetivamente elegível. MX válido isoladamente nunca promove a caixa para envio automático.
- Destinos externos usados por inteligência contínua permanecem sujeitos a validação contra SSRF, quotas e opt-in do workspace.

## Qualidade e freshness dos dados

- Data Health separa freshness por dimensão. Telefone não reutiliza mais `last_verified_at` genérico como se fosse observação específica do canal.
- O painel explicita a cobertura da análise e evita apresentar uma amostra limitada como saúde global da base.
- O histórico de verificação de e-mail é limitado, auditável e preserva incerteza em vez de inventar certeza.

## Busca e desempenho

- Filtros simples e seletivos de empresas e pessoas são aplicados no PostgreSQL antes do limite de candidatos sempre que possível.
- A lógica ternária `MATCH / NO_MATCH / UNKNOWN` continua preservada para campos heterogêneos ou ausentes.
- A UI de busca foi decomposta em painéis menores para empresas e pessoas e deixou de sincronizar estado de formulário por effects; uma nova interpretação assistida remonta o painel com os filtros revisáveis como estado inicial.

## Inteligência contínua

- Chamadas de providers independentes operam com concorrência limitada.
- I/O externo utiliza snapshots dos dados necessários e evita manter transações de banco abertas durante a espera de rede.
- Antes de persistir resultados, os registros são novamente resolvidos no workspace ativo, preservando isolamento multi-tenant.
- Monitoramento externo continua fail-closed: sem opt-in/cota, nenhuma fonte externa é chamada.

## UX e linguagem de domínio

- Códigos internos de oferta, sinais, papéis de compra e estados técnicos foram centralizados em mapeamentos reutilizáveis e apresentados em linguagem comercial em português.
- Inputs técnicos que tinham domínio finito passaram a usar controles adequados, como `Select` e `Switch`.
- `/buscar`, `/data-health` e `/monitoramento` ganharam estados de loading/empty/error mais claros, sem esconder incerteza dos dados.
- O catálogo declarativo AlphaMec passou a usar `alphamec_offer_profiles.py`; os modelos comerciais canônicos vivem em `commercial_intelligence_models.py`. O antigo caminho `phase56_models.py` fica apenas como seam de compatibilidade temporário para imports existentes, sem definir schema próprio.

## Contrato de validação antes do merge

O PR só pode sair de draft e ser integrado quando o **mesmo HEAD final** passar por todos os gates abaixo:

1. Backend: `python -m compileall` e `pytest tests -q -W error`.
2. Migrations: PostgreSQL real, `alembic upgrade head`, segundo upgrade idempotente, verificação de schema e smoke do seed.
3. E2E: ciclo crítico em PostgreSQL real e invariável de concorrência de conversões.
4. Web: `npm run lint`, `npx tsc --noEmit` e `npm run build`.

Alterações posteriores a uma execução verde invalidam aquela evidência e exigem novo CI no novo HEAD.

## Limites da validação automatizada

CI verde comprova os contratos automatizados acima. Ele não substitui UAT manual em navegador nem validação real de providers externos que dependem de credenciais, quotas e ambiente AlphaMec. Essas validações não devem ser declaradas concluídas sem execução no ambiente correspondente.
