# Auditoria Final Pré-Lançamento — Sistema Completo

Quero que você atue como um **Senior Software Engineer, Security Engineer, especialista em QA, SEO, acessibilidade e arquitetura de aplicações web**.

Este sistema está entrando na fase final antes do lançamento. Sua tarefa é realizar uma **auditoria completa do projeto**, identificar problemas e implementar as melhorias necessárias para deixá-lo o mais preparado possível para produção.

**Não faça alterações superficiais. Analise o projeto inteiro, entenda sua arquitetura, tecnologias, fluxos de autenticação, rotas, APIs, banco de dados, variáveis de ambiente e interface antes de começar a modificar qualquer coisa.**

---

# 1. ACESSIBILIDADE — eMAG E WCAG

Faça uma auditoria completa de acessibilidade visando conformidade com:

* **eMAG (Modelo de Acessibilidade em Governo Eletrônico)**
* **WCAG 2.1 ou superior**
* Objetivo mínimo: **nível AA**

Revise e corrija, quando necessário:

* Contraste entre textos e fundos.
* Tamanho e legibilidade dos textos.
* Navegação completa por teclado.
* Indicadores visuais de foco (`focus`).
* Ordem lógica de navegação.
* Uso correto de elementos HTML semânticos.
* Hierarquia correta de headings (`h1`, `h2`, `h3` etc.).
* Labels corretamente associados a inputs.
* Mensagens de erro acessíveis.
* Formulários utilizáveis por leitores de tela.
* Botões e links com nomes acessíveis.
* Uso correto de ARIA, **sem adicionar ARIA desnecessariamente quando HTML semântico resolver o problema**.
* Modais, menus e componentes interativos acessíveis.
* Estados de loading e feedback adequados para tecnologias assistivas.
* Verificação de elementos clicáveis pequenos demais para dispositivos móveis.
* Imagens decorativas corretamente identificadas e imagens informativas com descrições adequadas.

**Não apenas liste os problemas: corrija os problemas encontrados no código.**

Ao final, informe quais critérios relevantes do **eMAG/WCAG AA** foram revisados e quais limitações ainda existirem.

---

# 2. SEGURANÇA — AUDITORIA COMPLETA

Faça uma revisão de segurança do sistema como se estivesse preparando a aplicação para produção.

## 2.1 Segredos e credenciais

Verifique cuidadosamente:

* Chaves de API expostas no código.
* Tokens.
* Senhas.
* Credenciais de banco de dados.
* Secrets de autenticação.
* Variáveis sensíveis expostas no frontend.
* Arquivos `.env` sendo versionados.
* Dados sensíveis presentes no histórico ou arquivos do projeto que possam ser encontrados na estrutura atual.
* Configurações inseguras de produção.

Garanta que:

* Nenhum segredo esteja hardcoded no código.
* Dados sensíveis estejam usando variáveis de ambiente.
* Arquivos `.env` estejam corretamente ignorados pelo Git.
* Apenas variáveis explicitamente seguras sejam expostas ao frontend.
* Arquivos de exemplo, como `.env.example`, não contenham credenciais reais.

**Nunca exponha ou imprima valores secretos encontrados durante a auditoria. Apenas informe o tipo e localização geral do problema e faça a correção necessária.**

---

## 2.2 Autenticação e autorização

Revise completamente o sistema de autenticação e autorização.

Verifique:

* Todas as rotas privadas.
* Todas as APIs/endpoints.
* Rotas administrativas.
* Operações de criação, edição e exclusão.
* Acesso entre diferentes usuários.
* Controle de permissões e papéis.
* Possibilidade de acessar recursos alterando IDs manualmente.
* Possibilidade de um usuário acessar dados de outro usuário.
* Proteção correta no backend.

**Importante: não confie apenas na proteção do frontend.**

Garanta que a autorização seja validada também no servidor/backend.

Procure especialmente por vulnerabilidades como:

* IDOR/BOLA (acesso a recursos de outros usuários manipulando IDs).
* Escalonamento de privilégios.
* Endpoints sem autenticação.
* Rotas administrativas expostas.
* Falta de validação de ownership dos recursos.
* Sessões/tokens mal protegidos.
* Falta de expiração ou validação adequada de credenciais.

Faça testes seguros e controlados dentro do ambiente/local do projeto para verificar se usuários sem permissão conseguem acessar recursos que não deveriam.

---

## 2.3 Segurança geral da aplicação

Revise e corrija vulnerabilidades comuns relevantes à stack utilizada, incluindo:

* XSS.
* CSRF, quando aplicável à arquitetura de autenticação.
* SQL Injection.
* NoSQL Injection, se aplicável.
* Validação inadequada de inputs.
* Dados não sanitizados.
* Upload de arquivos inseguro, se existir.
* Open Redirect.
* Rate limiting ausente em endpoints sensíveis.
* Falhas no tratamento de erros.
* Vazamento de informações internas em mensagens de erro.
* Dependências vulneráveis.
* Configurações inseguras de CORS.
* Headers de segurança relevantes.
* Exposição de stack traces em produção.

Utilize as práticas recomendadas para a stack existente.

**Não faça mudanças destrutivas ou incompatíveis sem necessidade. Prefira correções seguras, incrementais e justificadas.**

---

# 3. SEO E INDEXAÇÃO

Faça uma revisão completa de SEO técnico.

## Meta tags

Garanta que as páginas relevantes possuam:

* `<title>` único e descritivo.
* Meta description única e otimizada.
* Open Graph adequado.
* Metadados para compartilhamento em redes sociais.
* Canonical URLs, quando aplicável.
* Configuração correta de idioma (`lang`).

Evite títulos e descrições genéricos ou duplicados.

---

## Textos alternativos

Revise todas as imagens da aplicação.

Garanta que:

* Imagens informativas possuam `alt` descritivo e contextual.
* Imagens decorativas usem tratamento adequado.
* Não existam textos alternativos genéricos como `"imagem"` ou `"foto"` sem contexto.
* Não haja repetição desnecessária do conteúdo visual.

---

## robots.txt

Verifique se existe um arquivo `robots.txt`.

Caso não exista, crie-o.

Configure-o corretamente para:

* Permitir a indexação das páginas públicas relevantes.
* Bloquear áreas privadas, administrativas ou que não devem aparecer em mecanismos de busca.
* Referenciar o sitemap quando aplicável.

**Não bloqueie acidentalmente páginas importantes do sistema.**

---

## sitemap.xml

Verifique se existe um sitemap.

Caso não exista, implemente uma solução adequada para a tecnologia/framework utilizado.

Inclua as páginas públicas relevantes e exclua:

* Rotas privadas.
* Rotas administrativas.
* Páginas internas.
* URLs que não devem ser indexadas.

---

# 4. CONTEÚDO E ESTRUTURA DO SITE

## Página 404

Crie ou melhore uma página personalizada de erro 404.

Ela deve:

* Manter a identidade visual do sistema.
* Explicar claramente que a página não foi encontrada.
* Oferecer uma ação clara para voltar à página inicial ou área relevante.
* Ser responsiva e acessível.

---

## FAQ — Perguntas Frequentes

Adicione ou estruture uma seção de FAQ com **pelo menos 5 perguntas e respostas relevantes ao produto/serviço real**.

Não utilize perguntas genéricas apenas para preencher espaço.

As perguntas devem refletir dúvidas que usuários reais provavelmente teriam sobre o sistema.

A seção deve ser:

* Clara.
* Organizada.
* Responsiva.
* Acessível.
* Fácil de navegar.

---

## Depoimentos e Prova Social

Estruture uma área apropriada para:

* Avaliações reais de clientes.
* Depoimentos.
* Fotos da equipe ou responsáveis, quando aplicável.
* Prova social.

**Não invente clientes, avaliações, números ou depoimentos falsos.**

Se ainda não houver conteúdo real disponível, deixe uma estrutura pronta para receber esses dados posteriormente, utilizando placeholders claramente identificados como conteúdo a ser substituído.

---

## Política de Privacidade e Termos

Crie ou revise páginas para:

* Política de Privacidade.
* Termos de Uso, quando aplicável.

Utilize um texto-base adequado à realidade do sistema, considerando especialmente:

* Dados coletados.
* Finalidade do tratamento.
* Cookies, se utilizados.
* Compartilhamento de dados.
* Armazenamento.
* Segurança.
* Direitos dos usuários.

**Não invente práticas que o sistema não realiza.**

Se houver informações jurídicas que dependam de validação profissional, deixe claro no código/comentários/documentação que o texto deve passar por revisão jurídica antes do lançamento oficial.

Considere a **LGPD**, quando aplicável.

---

# 5. CONVERSÃO E EXPERIÊNCIA DO USUÁRIO

Revise as páginas principais focando em conversão e clareza.

Garanta que exista uma **CTA clara acima da dobra**, especialmente nas páginas públicas ou comerciais.

Verifique:

* O usuário entende rapidamente o que o sistema oferece.
* Existe uma ação principal evidente.
* Botões possuem textos claros.
* Não existem CTAs concorrentes em excesso.
* O fluxo para contato, cadastro, login ou conversão está claro.

Exemplos de ações:

* Começar agora.
* Criar conta.
* Entrar em contato.
* Solicitar demonstração.

Adapte as CTAs ao objetivo real do sistema.

---

# 6. RESPONSIVIDADE

Faça uma revisão completa da interface em diferentes tamanhos de tela.

Teste especialmente:

* Desktop.
* Tablet.
* Smartphones pequenos.
* Smartphones grandes.

Verifique:

* Menus.
* Navbar.
* Botões fixos.
* Modais.
* Tabelas.
* Formulários.
* Cards.
* Dashboards.
* Textos longos.
* Overflow horizontal.
* Elementos sobrepostos.
* Componentes que ficam inacessíveis em telas pequenas.

Se o projeto utilizar Tailwind ou outro sistema de CSS responsivo, revise os breakpoints e classes.

**Não considere apenas que o layout "não quebra". A experiência deve ser realmente utilizável em dispositivos móveis.**

---

# 7. PERFORMANCE E QUALIDADE DO CÓDIGO

Faça uma revisão final do código.

Procure por:

* Código morto.
* Imports não utilizados.
* Componentes não utilizados.
* Funções duplicadas.
* Lógica desnecessariamente complexa.
* Scripts desnecessários.
* Requisições duplicadas.
* Re-renderizações evitáveis, quando relevantes.
* Queries ou chamadas de API ineficientes.
* Imagens não otimizadas.
* Dependências desnecessárias.
* Erros de console.
* Warnings.
* Código temporário de desenvolvimento.
* `console.log` esquecidos.
* TODOs críticos.
* Erros de digitação.
* Textos com português incorreto ou inconsistente.
* Textos genéricos, placeholders esquecidos ou conteúdo incompleto.

Não faça uma refatoração gigantesca apenas por preferência estética.

Priorize:

1. Bugs.
2. Segurança.
3. Acessibilidade.
4. Problemas que podem afetar produção.
5. Performance.
6. Manutenibilidade.

---

# 8. VERIFICAÇÃO FINAL DE ROTAS E PRODUÇÃO

Faça um levantamento das rotas da aplicação e classifique-as.

Verifique:

### Públicas

* Quais podem ser acessadas sem autenticação.

### Privadas

* Quais exigem autenticação.

### Administrativas/restritas

* Quais exigem permissões adicionais.

Para cada grupo, confirme que a proteção está acontecendo corretamente **no nível apropriado**, especialmente no backend.

Verifique também:

* Redirecionamentos incorretos.
* Rotas inexistentes.
* Loops de redirecionamento.
* Páginas privadas indexáveis.
* APIs acessíveis indevidamente.
* Endpoints internos expostos sem necessidade.

---

# 9. CHECKLIST FINAL DE LANÇAMENTO

Depois de analisar e implementar as correções necessárias:

1. Execute os testes disponíveis.
2. Execute linting e verificação de tipos.
3. Faça uma build de produção.
4. Corrija erros que impedirem a build.
5. Revise os warnings relevantes.
6. Verifique se não há segredos expostos.
7. Verifique se rotas privadas estão protegidas.
8. Verifique SEO.
9. Verifique `robots.txt`.
10. Verifique sitemap.
11. Verifique acessibilidade.
12. Verifique responsividade.

---

# FORMA DE TRABALHO

Siga esta ordem:

### Fase 1 — Auditoria

Primeiro, analise o projeto e identifique:

* Arquitetura.
* Stack.
* Estrutura de rotas.
* Sistema de autenticação.
* Variáveis de ambiente.
* Áreas públicas e privadas.
* Principais riscos.

### Fase 2 — Plano

Antes de fazer alterações grandes, apresente um resumo conciso com:

* Problemas críticos encontrados.
* Problemas importantes.
* Melhorias recomendadas.
* Alterações que você pretende realizar.

### Fase 3 — Implementação

Implemente as correções priorizando:

**CRÍTICO → SEGURANÇA → ACESSIBILIDADE → FUNCIONALIDADE → SEO → RESPONSIVIDADE → QUALIDADE DE CÓDIGO**

### Fase 4 — Validação

Após as alterações:

* Rode os testes disponíveis.
* Rode lint.
* Rode typecheck.
* Faça build de produção.
* Corrija problemas encontrados.

---

# RELATÓRIO FINAL

Ao terminar, entregue um relatório objetivo contendo:

## 1. Alterações realizadas

Liste os principais arquivos e alterações.

## 2. Problemas críticos encontrados

Explique o que foi encontrado e como foi corrigido.

## 3. Segurança

Informe:

* Proteções verificadas.
* Problemas corrigidos.
* Riscos que ainda precisam de atenção.

**Nunca exponha secrets ou valores de credenciais no relatório.**

## 4. Acessibilidade

Informe o que foi revisado para eMAG/WCAG AA e quais critérios ainda precisam de validação manual.

## 5. SEO

Informe:

* Meta tags.
* Alt texts.
* robots.txt.
* Sitemap.

## 6. Pendências

Liste claramente qualquer item que:

* Dependa de conteúdo real.
* Dependa de decisão do proprietário.
* Dependa de credenciais externas.
* Precise de revisão jurídica.
* Precise de teste manual.

---

# REGRA FINAL

Trate este sistema como uma aplicação que está prestes a entrar em produção.

**Não assuma que algo está seguro apenas porque existe uma proteção visual no frontend. Verifique a implementação real.**

**Não invente funcionalidades, clientes, depoimentos, políticas de privacidade ou práticas de coleta de dados que não existam no sistema.**

**Não remova funcionalidades existentes sem necessidade.**

**Faça alterações com cuidado, preservando a arquitetura e o comportamento atual sempre que possível.**

O objetivo final é deixar o sistema em um estado sólido para lançamento, identificando e corrigindo o máximo possível de problemas reais de segurança, acessibilidade, SEO, responsividade, qualidade e produção.
