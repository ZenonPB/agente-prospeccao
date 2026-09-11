---
name: spec-execution
description: Executar uma Task específica de uma Spec/roadmap do agente-prospeccao de forma incremental, test-driven e sem avançar para a próxima Task. Use ao iniciar implementação de Task, milestone ou vertical slice no Kiro Spec.
---
# Spec Execution

Execute somente a Task solicitada.

## Reconhecimento
Leia requisito/aceite, consulte `AGENTS.md`, use Graphify se disponível, leia `docs/context.md`, procure implementações existentes e classifique o que já está complete/partial/ausente.

## Plano mínimo
Defina arquivos, contratos, migration?, testes, riscos e código a reutilizar. Se a Spec estiver desatualizada, adapte ao estado real em vez de duplicar arquitetura.

## Implementação
Incrementos pequenos: test → code → focused validation.

## Validação
Execute o menor conjunto suficiente e depois regressão apropriada. Verifique aceite explicitamente.

## Encerramento
Reporte o que já existia, mudanças, migrations, arquivos, testes, aceite, pendências e riscos. Termine com COMPLETE / COMPLETE_WITH_FOLLOWUPS / PARTIAL / BLOCKED.
