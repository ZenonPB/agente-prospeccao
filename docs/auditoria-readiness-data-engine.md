# Auditoria de readiness — Data Engine Brasil

**Escopo:** main no commit `02be028` (merge da PR #202), validada e corrigida na
branch `audit/auditoria-readiness-02be028`. **Status:** código validado
tecnicamente; validação operacional e evidência comercial continuam pendentes.

## Como ler os estados

- **IMPLEMENTADO** — o código existe e é exercitado por testes, sem prova além da
  contract test.
- **VALIDADO TECNICAMENTE** — o mesmo HEAD passou nos gates locais com
  PostgreSQL real: `compileall`, `pytest -W error`, migrations idempotentes,
  schema verifiers e build web.
- **VALIDADO OPERACIONALMENTE** — exercitado com snapshot real, providers
  autorizados e pessoas reais. Não alcançado nesta auditoria.
- **PENDENTE DE EVIDÊNCIA COMERCIAL** — depende de resposta, reunião, proposta e
  venda atribuídas. Não alcançado nesta auditoria.

## Estado por bloco

| Bloco | Estado |
|---|---|
| Data Engine Brasil (Registry, discovery, web intelligence) | VALIDADO TECNICAMENTE · PENDENTE DE EVIDÊNCIA COMERCIAL (snapshot real) |
| People & Contact Intelligence (waterfall, contatabilidade) | VALIDADO TECNICAMENTE · PENDENTE DE EVIDÊNCIA COMERCIAL |
| Lead → Conversation (outreach, cadência, inbound) | VALIDADO TECNICAMENTE · PENDENTE DE EVIDÊNCIA COMERCIAL |
| Production readiness gate + Commercial Dimensions shadow | VALIDADO TECNICAMENTE (gate imutável) · PENDENTE DE EVIDÊNCIA COMERCIAL (promoção) |
| Omnichannel + Relationship Intelligence | NÃO IMPLEMENTADO |
| Autopilot, Revenue Intelligence, Produto SaaS | NÃO IMPLEMENTADO |

## Gates executados no HEAD auditado

- `python -m compileall -q services/api services/workers` — verde;
- `pytest tests -q -W error` sem `E2E_DATABASE_URL` — 1842 passed, 45 skipped
  (os skips são os testes que exigem PostgreSQL real);
- `pytest tests -q -W error` com `E2E_DATABASE_URL` em PostgreSQL 16 local —
  1887 passed, zero skips, zero falhas;
- `alembic upgrade head` em banco novo, segunda passada sem nenhuma migration
  pendente (idempotência), `verify_migrations`, `verify_sales_operating_schema`,
  `verify_block_d_readiness` (`READY`) e seed de templates;
- web: `npm run lint`, `npx tsc --noEmit` e `npm run build` — verdes;
- isolamento por organização exercitado nos caminhos críticos (contrato de
  tenant-first, Registry, busca, templates, inbound, UAT multi-workspace).

## Achados corrigidos

1. **Opt-out ausente em follow-ups e closing (P2, corrigido).** O contrato exige
   mecanismo de opt-out em toda mensagem de e-mail da cadência; a normalização
   só o garantia na abertura. Corrigido na normalização do outreach e no
   agendamento da cadência — este último cobre conteúdo de outra origem, sem
   duplicar o rodapé. Regressões: `tests/test_outreach_opt_out_footer.py`,
   `tests/test_cadence_opt_out_footer.py`, `tests/test_outreach_uses_provider.py`.
2. **Rótulo de área/cargo promovido a pessoa (P2, corrigido).** Nomes como
   "Equipe de Vendas" ou "Atendimento" passavam pelo filtro de placeholder e
   viravam contato direto, inflando Contatabilidade. Agora tokens genéricos
   (sem acento) são rejeitados e o contato cai em `GENERIC_CHANNEL`.
   Regressão: `tests/test_contactability_generic_names.py`.
3. **Shadow em reanálise promovia fallback zero a medida (P2, corrigido).**
   "Chave presente no vetor existente" não prova observação, e o pipeline
   persiste fallbacks zero; uma segunda análise de lead não pontuado gravava
   Aderência 0/LOW em vez de `UNKNOWN`. Regressão:
   `tests/test_shadow_reanalyze_unknown.py`.
4. **Isolamento do teste de snapshot do Registry (P3, corrigido).** O teste
   deixava ledger/snapshot no banco e podia conflitar entre execuções na mesma
   base.

## Achados documentados, sem mudança de comportamento

- **`decision_maker_accessibility` é fonte declarada e nunca observada (P3).**
  Nasce aninhado no pipeline de decisor, não é projetado no Opportunity Vector e
  tem peso zero no scoring. A renormalização ignora a chave ausente, então
  Contatabilidade segue medida por `reachability` e `contactability` — a dimensão
  não fica sistematicamente UNKNOWN. Projetar esse valor altera o input do
  shadow e é decisão de produto, não correção silenciosa.
- **Escala ambígua de `confidence` em `_data_confidence` (P3).** Valores `<= 1`
  são lidos como fração e `> 1` como porcentagem; um `1` que signifique 1% vira
  100%. Aceitável enquanto as fontes seguem a convenção atual.
- **`contactable` do resumo do piloto usa `Person.routable`** enquanto a
  dimensão de Contatabilidade usa contatos do lead; são medidas diferentes e a
  divergência entre elas é observação, não erro.
- **`EmailSuppression` é global por endereço** — decisão deliberada registrada no
  contrato; alterar exige migration e decisão de produto.

## Limites desta auditoria

- Snapshot real do Brazil Company Registry não foi importado: não há arquivo em
  `dados-registry/` nem base carregada. O pipeline foi exercitado com dados
  sintéticos, o que prova o funcionamento técnico e **não** substitui a
  validação operacional do Registry real.
- Providers pagos não foram acionados; nenhuma mensagem real foi enviada.
- `promotion_allowed` permanece `false` por contrato. Um resumo sintético pode
  elevar `promotion_evidence_sufficient`, nunca `promotion_allowed` — a promoção
  exige mudança de código/configuração explícita, reversível e revisada.
- Backup/restore ensaiado roda na CI; não foi executado nesta máquina.