# Learning comercial controlado

O learning comercial é derivado de uma comparação A/B estatisticamente
conclusiva e aprovada por um gerente. A aprovação não altera pesos, thresholds
ou qualquer `OfferProfile` ativo.

## Fluxo

```text
outcomes
  → comparação A/B com amostra mínima e Wilson
  → aprovação humana (`AB_COMPARISON_APPROVED`)
  → proposta versionada (`PROPOSED`)
  → publicação manual futura
```

Cada proposta é vinculada à organização e à comparação de origem. O snapshot de
evidência contém apenas veredicto, recomendação, delta e intervalos/estatísticas
das duas versões; não contém comandos de edição de configuração.

## API

- `POST /api/intelligence/comparisons/{id}/approval`: aprova a versão vencedora
  e cria, na mesma transação, uma proposta pendente.
- `GET /api/intelligence/learning-proposals`: lista propostas da organização;
  aceita o filtro opcional `offer_key`.

A criação é idempotente por `(organization_id, source_comparison_id)`. Uma
segunda aprovação da mesma versão não regrava a auditoria; tentar aprovar outra
versão é rejeitado. A proposta recebe uma versão sequencial por oferta e o
estado inicial `PROPOSED`.

Não existe nesta etapa endpoint de publicação. Aplicar uma recomendação exige
um fluxo posterior de publicação explícita, com versionamento do `OfferProfile`,
rollback e auditoria própria.