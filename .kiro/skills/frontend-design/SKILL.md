---
name: frontend-design
description: Projetar e implementar interfaces de produção no apps/web (Next.js 16, React 19, TypeScript, shadcn/ui e @base-ui/react). Use ao criar ou redesenhar páginas, dashboards, CRM, busca, tabelas, formulários, analytics, filtros, sequences ou qualquer UI relevante.
---
# Frontend Design

## Antes de escrever JSX
1. Leia `apps/web/AGENTS.md` e o `AGENTS.md` da raiz.
2. Inspecione componentes reutilizáveis em `apps/web/src/components/`.
3. Inspecione 2–3 telas semelhantes antes de criar padrão novo.
4. Identifique tokens, tipografia, espaçamento e interações existentes.
5. Para APIs/convenções do Next.js 16, consulte `node_modules/next/dist/docs/` quando relevante.

Não invente endpoint, payload ou comportamento backend para facilitar a tela.

## Defina a experiência
Pergunte internamente:
- objetivo primário do usuário;
- ação principal e secundárias;
- o que precisa ser escaneado rapidamente;
- o que deve ser revelado progressivamente;
- comportamento com 0, 1, 20, 200 e milhares de registros;
- ações individuais vs. em lote.

## Estados obrigatórios
Considere loading, empty, error, partial data, success, disabled/pending e permission denied quando aplicável. Não trate `UNKNOWN` como `FALSE`.

## UI SaaS/CRM
Prefira densidade legível, tabelas para comparação, filtros persistentes, bulk actions úteis, drawers/panels para preservar contexto, feedback de ações e hierarquia clara.

Evite excesso de cards, gradientes decorativos, sombras fortes, containers arredondados aninhados, texto introdutório excessivo, grandes áreas vazias e componentes duplicados por página.

## Domínio
### Leads/oportunidades
Mostre por que importa, evidências, confidence, oferta/profile, decisor, contatabilidade, timing, next action e histórico.
### Search
Mostre query/filtros, total, qualidade/contactability, seleção, list/enrich/action.
### BI
Mostre filtros globais, período, denominadores/amostra, drill-down e diferença entre zero e ausência de dado.

## Acessibilidade
HTML semântico, labels, teclado, foco visível, contraste e nomes acessíveis para ícones. ARIA só quando necessário.

## Responsividade
Defina o que permanece, vira drawer, pode ser ocultado e como tabelas degradam.

## Finalização
Rode lint/typecheck/build relevantes, revise estados, desktop/mobile, componentes reutilizados/novos e riscos de UX restantes.
