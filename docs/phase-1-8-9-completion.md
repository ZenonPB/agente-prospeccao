# Unified Data Network, CRM e aprendizado comercial

Esta entrega fecha as lacunas estruturais remanescentes da Unified Data Network, amplia a fundação de workflows/CRM e torna as métricas de aprendizado comercial operacionais sem alterar os princípios de segurança já adotados.

## Rede federada de dados

A federação passa a ter dois componentes genéricos:

- `ProviderPlanner`: ordena fontes por capability considerando custo, cobertura, precisão, histórico de qualidade, quota e limite de gasto;
- `FederatedProviderRegistry`: executa waterfalls assíncronas mantendo `success`, `empty`, `failed`, `disabled` e `budget_exceeded` como estados distintos.

O planner é **free-first por padrão**, mas não assume que gratuito significa melhor. Quando existe amostra histórica suficiente, cobertura e precisão observadas podem substituir os priors declarados. Métricas desconhecidas usam priors conservadores; `UNKNOWN` não vira zero.

A camada nova é aditiva: registries especializados existentes continuam válidos e podem migrar gradualmente para o contrato comum sem quebrar campanhas atuais.

## Integrações comerciais

O contrato `CRMAdapter` agora possui implementações concretas para:

- Pipedrive;
- HubSpot;
- Salesforce.

As credenciais ficam em `organization_secrets`, criptografadas pelo mesmo cofre BYOK usado pelos demais providers. `crm_connections` guarda apenas uma referência ao nome do segredo.

Persistência adicionada:

- `crm_connections` — configuração por workspace;
- `crm_external_links` — vínculo canônico local ↔ remoto;
- `crm_sync_runs` — histórico idempotente das sincronizações;
- `prospect_lists` / `prospect_list_members` — listas operacionais usadas por workflows;
- `provider_quality_snapshots` — base para otimização futura do planner.

### Regras de sincronização

- toda leitura/mutação é filtrada por `organization_id`;
- integração nasce desativada e exige ativação explícita;
- endpoints externos exigem HTTPS;
- redirects não são seguidos automaticamente;
- tokens não entram em logs, evidence, resposta da API ou tabelas de sync;
- outbound usa chaves de idempotência e vínculos persistentes;
- inbound desconhecido não cria/mescla entidade por heurística: vira `review_required`;
- inbound só preenche campos canônicos vazios; conflito com valor local existente não é sobrescrito silenciosamente;
- Salesforce Opportunity falha fechado quando faltam campos obrigatórios do processo comercial do tenant;
- ações de workflow não mantêm transação aberta esperando rede externa.

Os modos persistidos são `manual`, `realtime` e `scheduled`. Nesta entrega, execução manual e a fundação persistente para os três modos estão prontas. Realtime depende dos webhooks do CRM configurado; scheduled depende de habilitar o scheduler da conexão no ambiente de produção.

## Workflow Engine

Além das ações já existentes, o motor passa a suportar:

- `ADD_TO_LIST` — adiciona lead a lista org-scoped de forma idempotente;
- `ASSIGN_OWNER` — atribui responsável somente se a pessoa pertence ao workspace ativo.

`CRM_SYNC` permanece desacoplado da transação síncrona do workflow: materializa uma operação/tarefa vinculada à integração, evitando prender conexão de banco durante I/O externo.

## Aprendizado e Analytics

`CommercialIntelligenceService` calcula apenas sobre resultados atribuíveis quando a causalidade exige oportunidade específica. Não existe fallback silencioso para “o maior score”.

Métricas entregues:

- saúde de atribuição;
- efetividade de sinais: taxa de resposta, reunião, venda e receita média por sinal;
- efetividade por fonte: volume, reuniões, vendas, custo, receita e ROI quando calculável;
- qualidade do topo do ranking: respostas/reuniões no top 10 e vendas no top 25;
- prior por `offer × segment`, com amostra mínima;
- cobertura comercial: empresas conhecidas, oportunidades com bom perfil, pessoas contatáveis, prospectados e ganhos.

O universo total de mercado (`TAM`) fica explicitamente `unknown` enquanto não houver uma fonte confiável para o recorte. O sistema não extrapola um número de mercado a partir da própria base.

A UI traduz chaves internas de ofertas/sinais/fontes para linguagem comercial. Dados insuficientes aparecem como “Sem dados” ou estado vazio, não como 0%.

## Learning controlado

A infraestrutura pré-existente de `CommercialComparison` e `ControlledLearningProposal` permanece como limite de segurança para alterações de OfferProfile: observar → propor → aprovação humana → publicar versão. Esta entrega não cria autoedição de pesos em produção.

A qualidade histórica de providers pode alimentar o planner porque altera somente a ordem de coleta, sujeita a quota/custo; alterações de inteligência comercial continuam passando por aprovação humana.

## Limites honestos de validação

Os adapters possuem contrato real e testes determinísticos com HTTP simulado, mas não se declara UAT real de Pipedrive, HubSpot ou Salesforce sem credenciais e contas de teste dos respectivos ambientes. Campos customizados, pipelines e regras específicas de cada conta devem ser configurados e validados no ambiente AlphaMec antes de habilitar sync automático.

Da mesma forma, cobertura/precision do sistema dependem das fontes reais configuradas. A arquitetura de federação pode escolher melhor entre fontes disponíveis, mas não inventa cobertura que os providers não oferecem.
