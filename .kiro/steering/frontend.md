---
inclusion: fileMatch
fileMatchPattern: "apps/web/**/*"
---
# Frontend steering
- Leia `apps/web/AGENTS.md` antes de alterar Next.js/React.
- Stack: Next.js 16, React 19, TypeScript, shadcn/ui sobre `@base-ui/react`.
- Reuse componentes existentes.
- Respeite as convenções atuais do Base UI; não assuma APIs antigas.
- Não invente contratos backend.
- Telas assíncronas devem considerar loading, empty, error e partial.
- UI operacional prioriza densidade, scanability e next action.
- Preserve acessibilidade e responsividade.
