# Auditoria Técnica Completa — React, Next.js, Performance, UX e Responsividade

Quero que você atue como um **Senior Frontend Engineer especializado em React, Next.js, TypeScript, performance web, arquitetura frontend, UX/UI e responsividade**.

Este sistema está nos ajustes finais antes do lançamento. Quero que você faça uma **auditoria profunda de todo o frontend**, verificando se o projeto está utilizando corretamente as melhores práticas atuais de **React e Next.js** e identificando oportunidades reais de melhoria.

O objetivo é deixar o sistema:

* Rápido.
* Fluido.
* Responsivo.
* Bonito e consistente.
* Fácil de utilizar.
* Compatível com computadores e dispositivos móveis.
* Funcional em dispositivos com diferentes níveis de desempenho.
* Otimizado para produção.
* Fácil de manter e evoluir.

**Não faça alterações apenas porque existe uma forma diferente de escrever o código. Priorize melhorias que tragam ganhos reais de performance, qualidade, arquitetura, UX ou manutenção.**

---

# 1. PRIMEIRO: ENTENDA O PROJETO

Antes de modificar qualquer coisa:

1. Analise a estrutura completa do projeto.
2. Identifique a versão do Next.js e React.
3. Identifique se está sendo utilizado:

   * App Router ou Pages Router.
   * Server Components.
   * Client Components.
   * Server Actions, se aplicável.
   * API Routes/Route Handlers.
   * Cache e estratégias de renderização.
4. Entenda:

   * Estrutura de páginas e rotas.
   * Componentes compartilhados.
   * Gerenciamento de estado.
   * Sistema de autenticação.
   * Chamadas para APIs.
   * Bibliotecas utilizadas.
   * Estratégia de estilização.
   * Componentes mais pesados ou críticos.

**Não comece uma grande refatoração antes de entender a arquitetura atual.**

---

# 2. MELHORES PRÁTICAS DE REACT

Faça uma revisão profunda do código React.

Verifique:

## Componentização

* Componentes excessivamente grandes.
* Componentes com múltiplas responsabilidades.
* Lógicas repetidas.
* Componentes duplicados.
* Possibilidade de reutilização.
* Separação adequada entre UI e lógica.

Extraia componentes ou hooks **somente quando isso melhorar realmente a organização e manutenção**.

Evite criar abstrações excessivas.

---

## Hooks

Revise cuidadosamente o uso de:

* `useState`
* `useEffect`
* `useMemo`
* `useCallback`
* `useRef`
* Hooks customizados

Procure especialmente por:

* `useEffect` desnecessários.
* Estados que poderiam ser derivados diretamente.
* Sincronização desnecessária de estados.
* Dependências incorretas.
* Possíveis loops infinitos.
* Memory leaks.
* Funções que poderiam ser simplificadas.
* Hooks utilizados apenas por “otimização” sem benefício real.

**Não adicione `useMemo` ou `useCallback` indiscriminadamente.**

Utilize memoização apenas quando existir benefício mensurável ou uma razão técnica clara.

---

## Renderização

Verifique:

* Renderizações desnecessárias.
* Componentes que renderizam repetidamente sem necessidade.
* Context Providers causando re-renderizações excessivas.
* Estados globais mal estruturados.
* Props instáveis.
* Listas grandes sem otimização.

Quando necessário, considere:

* Melhor divisão de componentes.
* Memoização.
* Virtualização de listas grandes.
* Estruturação adequada do estado.

Mas novamente:

**Não otimize prematuramente. Priorize gargalos reais.**

---

# 3. MELHORES PRÁTICAS DE NEXT.JS

Faça uma auditoria específica do uso do Next.js.

Verifique se o projeto está utilizando corretamente:

* Server Components.
* Client Components.
* SSR.
* SSG.
* Renderização dinâmica quando necessária.
* Cache.
* Revalidação.
* Streaming, quando fizer sentido.
* Route Handlers.

---

## Server vs Client Components

Analise todos os componentes marcados com:

`"use client"`

Verifique se realmente precisam ser Client Components.

Sempre que possível e apropriado:

* Mantenha componentes como Server Components.
* Reduza JavaScript enviado ao navegador.
* Isole partes interativas em pequenos Client Components.

Não transforme componentes em Client Components sem necessidade.

---

## Data Fetching

Revise todas as chamadas de dados.

Verifique:

* Onde os dados são buscados.
* Se existem requisições duplicadas.
* Waterfalls desnecessários.
* Requisições sequenciais que poderiam ocorrer em paralelo.
* Dados sendo buscados no cliente quando poderiam ser obtidos no servidor.
* Estratégias de cache.
* Loading states.
* Error states.

Otimize quando houver ganhos reais.

---

# 4. PERFORMANCE

Faça uma auditoria completa de performance.

Verifique possíveis problemas relacionados a:

## JavaScript

* Bundle excessivamente grande.
* Bibliotecas muito pesadas.
* Dependências desnecessárias.
* Código enviado ao cliente sem necessidade.
* Imports que poderiam ser otimizados.
* Código que poderia utilizar carregamento dinâmico.

Considere `dynamic import` para funcionalidades pesadas que não precisam ser carregadas imediatamente.

---

## Imagens

Revise todas as imagens.

Verifique:

* Uso adequado de otimização do Next.js.
* Dimensões corretas.
* Layout shifts.
* Imagens excessivamente pesadas.
* Carregamento prioritário apenas para imagens realmente críticas.
* Lazy loading quando apropriado.

Evite carregar imagens desnecessariamente.

---

## Fontes

Verifique:

* Carregamento otimizado.
* Fontes excessivas.
* Muitos pesos de fonte.
* Possível impacto no carregamento.
* Layout shift causado por fontes.

---

## Layout Shift

Procure por problemas de:

* CLS.
* Elementos mudando de posição após o carregamento.
* Imagens sem dimensões adequadas.
* Conteúdo aparecendo e empurrando outros elementos.
* Loading states mal estruturados.

---

# 5. CORE WEB VITALS

Analise e otimize o sistema visando bons resultados em:

* LCP — Largest Contentful Paint.
* INP — Interaction to Next Paint.
* CLS — Cumulative Layout Shift.

Identifique os principais elementos que podem prejudicar essas métricas.

Priorize melhorias reais, especialmente nas páginas mais importantes.

---

# 6. RESPONSIVIDADE — QUALQUER DISPOSITIVO

Faça uma revisão profunda da responsividade.

Teste e analise o sistema considerando:

### Desktop

* Monitores menores.
* Notebooks.
* Monitores grandes.

### Tablets

* Tablet vertical.
* Tablet horizontal.

### Mobile

* Smartphones pequenos.
* Smartphones médios.
* Smartphones grandes.

Verifique:

* Overflow horizontal.
* Textos cortados.
* Botões pequenos demais.
* Elementos difíceis de clicar.
* Menus quebrados.
* Modais problemáticos.
* Tabelas impossíveis de utilizar.
* Inputs inadequados.
* Elementos fixos cobrindo conteúdo.
* Espaçamentos excessivos ou insuficientes.
* Layouts que ficam estranhos em telas intermediárias.

**Não considere apenas que a página “cabe na tela”.**

A experiência deve ser realmente boa em cada tamanho de dispositivo.

---

# 7. UX E UI

Faça uma auditoria visual e de experiência.

Avalie:

* Consistência visual.
* Hierarquia de informações.
* Espaçamento.
* Tipografia.
* Contraste.
* Estados de hover.
* Estados de focus.
* Estados disabled.
* Estados loading.
* Estados de erro.
* Feedback após ações.
* Feedback de sucesso.
* Navegação.
* Clareza dos botões.
* Consistência dos componentes.

Verifique se existem:

* Componentes visualmente inconsistentes.
* Botões diferentes para ações semelhantes.
* Espaçamentos aleatórios.
* Fontes inconsistentes.
* Bordas inconsistentes.
* Ícones desalinhados.
* Layouts visualmente poluídos.

O sistema deve parecer **profissional, moderno, consistente e bem acabado**.

---

# 8. EXPERIÊNCIA EM COMPUTADORES MAIS FRACOS

Considere que o sistema pode ser utilizado em:

* Computadores modernos.
* Notebooks mais antigos.
* Celulares intermediários.
* Celulares com menor capacidade de processamento.

Procure por:

* Animações excessivamente pesadas.
* JavaScript desnecessário.
* Renderizações excessivas.
* Processamentos pesados na thread principal.
* Listas grandes.
* Componentes que carregam dados demais.
* Bibliotecas pesadas utilizadas para tarefas simples.

Priorize uma experiência fluida.

Reduza trabalho desnecessário no navegador.

---

# 9. ANIMAÇÕES

Revise todas as animações.

Verifique:

* Se melhoram realmente a experiência.
* Se não prejudicam performance.
* Se são excessivas.
* Se funcionam corretamente em dispositivos móveis.
* Se respeitam `prefers-reduced-motion`.

Evite animações pesadas ou desnecessárias.

Priorize animações fluidas e discretas.

---

# 10. ESTADOS DE CARREGAMENTO E ERRO

Revise toda a aplicação.

Garanta que ações importantes possuam feedback adequado.

Verifique:

* Loading de páginas.
* Loading de dados.
* Skeletons.
* Botões durante envio.
* Estados vazios.
* Erros de API.
* Falhas de conexão.
* Estados sem dados.

Evite:

* Tela completamente vazia durante carregamentos.
* Usuário sem saber se uma ação está acontecendo.
* Botões que podem ser clicados múltiplas vezes enquanto uma ação está sendo processada.

---

# 11. FORMULÁRIOS

Revise todos os formulários.

Verifique:

* Validação.
* Mensagens claras.
* Feedback imediato quando apropriado.
* Prevenção de envios duplicados.
* Estados de loading.
* Campos corretamente configurados.
* Experiência em dispositivos móveis.
* Teclado adequado para cada tipo de input.

Exemplos:

* `type="email"` para e-mails.
* Tipos numéricos quando apropriado.
* Autocomplete adequado.
* Autofill funcionando corretamente.

---

# 12. CSS / TAILWIND

Faça uma auditoria completa dos estilos.

Procure por:

* Classes duplicadas.
* Estilos conflitantes.
* Valores arbitrários excessivos.
* Breakpoints inconsistentes.
* Código CSS morto.
* Componentes visualmente inconsistentes.
* Responsividade improvisada.

Se o projeto utilizar Tailwind:

* Não reescreva classes apenas por preferência.
* Melhore consistência quando necessário.
* Evite abstrações desnecessárias.
* Verifique se os breakpoints estão sendo utilizados corretamente.

---

# 13. ACESSIBILIDADE E USABILIDADE

Mesmo que já exista uma auditoria separada, durante esta revisão frontend verifique novamente:

* Navegação por teclado.
* Focus states.
* Contraste.
* Elementos clicáveis.
* Labels.
* Semântica.
* Uso em telas pequenas.
* Leitores de tela.

O sistema precisa ser bonito **sem sacrificar usabilidade ou acessibilidade**.

---

# 14. QUALIDADE E MANUTENIBILIDADE

Revise:

* TypeScript.
* Tipagem excessivamente permissiva.
* Uso desnecessário de `any`.
* Tipos duplicados.
* Código morto.
* Imports não utilizados.
* Funções duplicadas.
* Componentes abandonados.
* Lógicas complexas.
* Arquivos excessivamente grandes.

Busque um equilíbrio entre:

**Código limpo + simplicidade + performance + facilidade de manutenção.**

Não faça abstrações desnecessárias.

---

# 15. DEPENDÊNCIAS

Analise as dependências do projeto.

Verifique:

* Dependências não utilizadas.
* Bibliotecas duplicadas.
* Bibliotecas excessivamente grandes.
* Dependências utilizadas apenas para funcionalidades simples que poderiam ser feitas nativamente.
* Pacotes desatualizados ou problemáticos.

Não remova dependências utilizadas indiretamente sem verificar cuidadosamente.

---

# 16. PROCESSO DE TRABALHO

Siga obrigatoriamente estas etapas:

## FASE 1 — AUDITORIA

Primeiro, analise completamente o projeto.

Identifique:

* Stack.
* Arquitetura.
* Pontos fortes.
* Problemas críticos.
* Gargalos de performance.
* Problemas de responsividade.
* Problemas de UX.
* Problemas de React.
* Problemas de Next.js.

---

## FASE 2 — RELATÓRIO E PLANO

Antes de grandes alterações, apresente um resumo contendo:

### 🔴 Crítico

Problemas que afetam funcionamento, performance severamente ou experiência.

### 🟠 Importante

Problemas relevantes que devem ser corrigidos antes do lançamento.

### 🟡 Melhorias

Otimizações recomendadas.

Para cada problema relevante, explique:

* Onde está.
* Por que é um problema.
* Qual será a solução.
* Qual o impacto esperado.

---

## FASE 3 — IMPLEMENTAÇÃO

Implemente as melhorias priorizando:

1. Bugs reais.
2. Problemas críticos de performance.
3. Problemas de responsividade.
4. Problemas de UX.
5. Uso incorreto de React/Next.js.
6. Core Web Vitals.
7. Qualidade e manutenção.

**Evite refatorações gigantescas sem benefício real.**

---

## FASE 4 — VALIDAÇÃO

Depois das alterações:

1. Execute o linter.
2. Execute o typecheck.
3. Execute os testes disponíveis.
4. Faça uma build de produção.
5. Corrija erros encontrados.
6. Verifique warnings relevantes.
7. Verifique se não foram introduzidas regressões.

---

# RELATÓRIO FINAL

Ao finalizar, entregue um relatório com:

## 1. Nota geral do frontend

Avalie o estado do projeto antes e depois das melhorias.

## 2. Melhorias implementadas

Liste as principais alterações realizadas.

## 3. React

Informe:

* Problemas encontrados.
* Problemas corrigidos.
* Melhorias de renderização ou arquitetura.

## 4. Next.js

Informe:

* Melhorias relacionadas a Server/Client Components.
* Data fetching.
* Renderização.
* Cache.
* Bundle.

## 5. Performance

Informe:

* Principais gargalos encontrados.
* Otimizações realizadas.
* Possíveis impactos em Core Web Vitals.

## 6. Responsividade

Informe:

* Problemas encontrados em mobile/tablet/desktop.
* Correções realizadas.

## 7. UX/UI

Informe as principais melhorias de experiência e consistência visual.

## 8. Pendências

Liste qualquer melhoria que:

* Precise de testes em dispositivos físicos.
* Dependa de dados reais.
* Exija uma decisão de produto.
* Não tenha sido implementada por risco de regressão.

---

# REGRA FINAL

O objetivo não é simplesmente ter um código “bonito”.

O objetivo é que o sistema seja:

* **Rápido na prática.**
* **Fluido na prática.**
* **Bonito e profissional.**
* **Responsivo.**
* **Usável em celulares, tablets e computadores.**
* **Compatível com dispositivos de diferentes capacidades.**
* **Construído seguindo as melhores práticas atuais de React e Next.js.**
* **Otimizado sem cair em otimização prematura.**
* **Fácil de manter e evoluir.**

Antes de fazer qualquer alteração, pergunte-se:

> **Essa mudança resolve um problema real ou traz um benefício mensurável para o usuário ou para a manutenção do sistema?**

Se a resposta for não, evite alterar apenas por preferência pessoal.

Trate esta revisão como uma **auditoria final de qualidade de um produto que está prestes a ser lançado em produção**.
