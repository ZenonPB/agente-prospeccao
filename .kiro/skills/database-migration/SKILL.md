---
name: database-migration
description: Criar, revisar e validar alterações de banco no agente-prospeccao: SQLAlchemy models, PostgreSQL, Alembic, índices, constraints, backfill e compatibilidade. Use sempre que uma feature exigir schema ou migration.
---
# Database Migration

Fonte de verdade ORM: `services/workers/src/database/models.py`.

## Processo
1. descubra a head Alembic;
2. inspecione model/migrations relacionadas;
3. prefira mudança expand-compatible;
4. altere model;
5. crie migration nova;
6. revise SQL;
7. valide banco vazio/upgrade quando aplicável;
8. rode `scripts/verify_migrations.py`;
9. rode testes afetados.

## Regras
Nunca editar migration compartilhada. Não dropar coluna abruptamente. Prefira expand → backfill → switch → contract posterior. Índice em FKs/hot paths quando justificado. JSONB crítico exige schema/versionamento. Multi-tenant exige avaliar `organization_id`, índices e unicidade.

Para scoring/learning, preserve versão histórica reproduzível.

Backfill deve ser idempotente, observável, em lote e sem inventar dado.

Reporte migration, risco de lock, backfill, compatibilidade e validações.
