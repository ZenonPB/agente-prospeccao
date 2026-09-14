# Bloco E — AlphaMec 1.0

Status: **release final da experiência operacional**, condicionado aos mesmos gates de CI dos blocos anteriores.

## Objetivo

O Bloco E não cria uma segunda plataforma nem muda as fontes canônicas. Ele fecha a versão 1.0 para uso cotidiano da AlphaMec sobre A/B/C/D, reduzindo atrito, jargão e dúvida operacional.

O fluxo principal da interface passa a ser explicado em linguagem comercial:

1. dizer o que a equipe quer vender;
2. revisar empresas e evidências;
3. trabalhar a carteira priorizada do dia;
4. registrar o avanço real no funil;
5. acompanhar resultados;
6. usar feedback e outcomes para propor melhorias controladas.

## E1 — UI/UX simples

A navegação mantém as rotas e contratos técnicos, mas apresenta nomes de tarefa em vez de nomes de subsistema. Exemplos: `Minha carteira`, `Buscar clientes`, `Leads qualificados`, `Follow-ups`, `Funil de vendas`, `Resultados`, `Melhorias da IA` e `O que vendemos`.

A Central de ajuda virou um guia operacional, com atalhos para o fluxo diário. Isso não remove telas avançadas: apenas deixa claro qual é o caminho principal e quais áreas são de gestão/análise.

## E2 — Tutorial utilizável de verdade

O tutorial passa por capítulos reais do produto:

- Começando;
- Encontrando clientes;
- Vendendo;
- Melhorando;
- Configuração.

Ele continua atravessando as principais áreas da aplicação, respeita RBAC, resolve campanha dinâmica quando existe, tolera elementos opcionais e pode ser pausado. Fechar o tutorial **não o descarta**: a posição é preservada e pode ser retomada em Ajuda, Configurações ou pelo menu do usuário. Também é possível recomeçar do zero.

O texto evita promessas de certeza: score é prioridade, `UNKNOWN` continua diferente de `FALSE`, sinais não são tratados como conversão e learning continua human-in-the-loop.

## E3 — Diagnóstico das conexões

Administradores podem usar `Testar conexões` em Configurações para verificar Google Places, Groq e Hunter sem expor segredos.

O backend resolve a credencial pelo mesmo `SecretService` tenant-scoped usado pelo produto e executa uma requisição mínima por provider. A resposta da aplicação contém apenas:

- provider e nome amigável;
- origem da configuração (`workspace` ou `shared`);
- estado classificado (`ok`, chave recusada, limite, indisponível, timeout etc.);
- readiness básica.

O valor da chave e o corpo bruto do provider nunca entram no payload da UI. O teste é manual: ter uma chave configurada não autoriza chamadas externas em background nem habilita outreach.

Para prospecção básica, Google + IA precisam responder. Hunter é complementar. O diagnóstico não substitui quota, provider opt-in, autorização de campanha nem as proteções do Bloco D.

## Segredos usados em desenvolvimento

Credenciais locais devem permanecer somente em `.env`/secret store. Nenhum valor real é versionado, copiado para documentação, fixtures ou logs. CI usa placeholders e mocks; o diagnóstico ao vivo consome as credenciais do ambiente/workspace em que a aplicação está rodando.

## O que “1.0 pronta” significa

A versão 1.0 fica tecnicamente pronta quando:

- A/B/C/D continuam verdes;
- API identifica versão `1.0.0`;
- provider diagnostics não vaza segredos e falha de forma legível;
- Web passa lint, TypeScript e production build;
- backend passa compileall e suíte completa com `-W error`;
- migrations, verifiers, seed e backup/restore continuam verdes;
- E2E PostgreSQL dos blocos anteriores continuam verdes;
- CI no HEAD final do PR e novamente no merge de `main` conclui com sucesso.

Isso **não** transforma rehearsal em prova de mercado. Conversão, precision@K real e receita continuam dependendo de campanhas externas autorizadas, contatos reais e outcomes corretamente atribuídos.
