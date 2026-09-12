# Engagement e workflows comerciais

Este ciclo evolui a cadência existente para um motor de engagement mais genérico e auditável e entrega a fundação operacional de workflows comerciais.

## Escopo

- Sequence Engine v2 reutilizando a infraestrutura de follow-ups já existente, sem quebrar a cadência 0/3/7/14;
- etapas de e-mail, ligação, LinkedIn, WhatsApp/manual, pesquisa, espera e condição;
- templates por persona/oferta e enrollment tenant-aware;
- persistência de decisões de próxima ação com `why`, `confidence`, `evidence` e `deadline`;
- reply, bounce, meeting e unsubscribe como eventos que pausam/encerram automações quando aplicável;
- auto-pause por saúde de envio;
- Workflow Engine `trigger -> conditions -> actions`, com execuções idempotentes e auditáveis;
- ações seguras: criar tarefa, notificar, re-enriquecer, re-ranquear, matricular em sequência e webhook assinado via infraestrutura existente;
- contrato de adapters CRM versionados, sem armazenar credenciais em claro e sem simular integrações externas sem credenciais reais;
- UI de sequências/workflows com estados de loading, erro e vazio, acessibilidade e linguagem comercial.

## Critério de conclusão

O ciclo só é considerado pronto quando o HEAD final passar por backend, migrations em PostgreSQL real, E2E crítico, lint, TypeScript e build de produção. UAT de providers/CRMs externos depende das credenciais reais do ambiente e não será declarado como concluído sem essa evidência.
