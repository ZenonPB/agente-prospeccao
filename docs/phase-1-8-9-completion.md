# Unified Data Network, CRM e aprendizado comercial

Esta entrega fecha as lacunas estruturais remanescentes da Unified Data Network, amplia a fundação de workflows/CRM e torna as métricas de aprendizado comercial operacionais sem alterar os princípios de segurança já adotados.

## Rede federada de dados

A federação passa a ter dois componentes genéricos:

- `ProviderPlanner`: ordena fontes por capability considerando custo, cobertura, precisão, histórico de qualidade, quota e limite de gasto;
- `FederatedProviderRegistry`: executa waterfalls assíncronas mantendo `success`, `empty`, `failed`, `disabled` e `budget_exceeded` como estados distintos.

O planner é **free-first por padrão**, mas não assume que gratuito significa melhor. Quando existe amostra histórica suficiente, cobertura e precisão observadas podem substituir os priors declarados. Métricas desconhecidas usam priors conservadores; `UNKNOWN` não vira zero.

A camada nova é aditiva: registries especializados existentes continuam válidos e podem migrar gradualmente para o contrato comum sem quebrar campanhas atuais.

## Integrações comerciais

O contrato `CRMAdapter` possui implementações concretas para Pipedrive, HubSpot e Salesforce.

As credenciais ficam em `organization_secrets`, criptografadas pelo mesmo cofre BYOK usado pelos demais providers. `crm_connections` guarda apenas uma referência ao nome do segredo.

Persistência adicionada:

- `crm_connections` — configuração por workspace;
- `crm_external_links` — vínculo canônico local ↔ remoto;
- `crm_sync_runs` — histórico idempotente das sincronizações;
- `crm_certification_runs` — evidência de certificação read-only executada contra a conta configurada;
- `prospect_lists` / `prospect_list_members` — listas operacionais usadas por workflows;
- `provider_quality_snapshots` — base para otimização do planner.

### Regras de sincronização

- toda leitura/mutação é filtrada por `organization_id`;
- integração nasce desativada e exige ativação explícita;
- endpoints externos exigem HTTPS;
- redirects não são seguidos automaticamente;
- tokens não entram em logs, evidence, resposta da API ou tabelas de sync;
- outbound usa chaves de idempotência e vínculos persistentes;
- inbound desconhecido não cria/mescla entidade por heurística: vira `review_required`;
- inbound só preenche campos canônicos vazios; conflito com valor local existente não é sobrescrito silenciosamente;
- ações de workflow não mantêm transação aberta esperando rede externa.

Os modos persistidos são `manual`, `realtime` e `scheduled`. Execução manual e a fundação persistente para os três modos estão prontas. Realtime depende dos webhooks do CRM configurado; scheduled depende de habilitar o scheduler da conexão no ambiente de produção.

### Certificação real sem escrita

Cada conexão ativa pode executar `POST /api/crm/crm-sync/connections/{id}/certify`.

A certificação:

1. resolve a credencial do workspace somente em memória;
2. executa o health/auth endpoint real do adapter;
3. para Pipedrive e HubSpot, executa também uma leitura incremental sem persistir cursor;
4. não cria, atualiza ou apaga registros remotos;
5. grava somente resultado, versão do adapter, checks e ator em `crm_certification_runs`;
6. persiste apenas a classe de eventual erro, nunca mensagem que possa carregar segredo.

No Salesforce, o healthcheck real valida autenticação no endpoint de limites. A leitura incremental genérica fica marcada como `not_applicable`, porque exige SOQL e mapeamento de campos específicos do workspace. O sistema não apresenta um retorno local vazio como se fosse UAT remoto.

A UI de Integrações oferece **Certificar conta real** e mostra a última evidência persistida. Ausência de certificação nunca aparece como aprovação.

## Workflow Engine

Além das ações já existentes, o motor suporta:

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

## Learning controlado: publicação e rollback

O ciclo da Fase 9 fica fechado como:

`observar → comparar → recomendar → aprovar → publicar → medir → rollback`

A publicação não edita o catálogo global e não faz autoajuste silencioso. Cada workspace possui versões próprias em `offer_profile_versions`.

Regras de publicação:

- somente proposta `PROPOSED` e já derivada de comparação conclusiva pode publicar;
- `key` precisa ser a mesma oferta aprovada;
- a versão do snapshot precisa ser exatamente `approved_version`;
- a versão precisa ser diferente da versão efetiva atual;
- o snapshot passa novamente pelo validador semântico do `OfferProfile`;
- erros bloqueiam a publicação; avisos não são tratados como erro;
- a primeira publicação persiste o perfil padrão atual como baseline exato;
- existe no máximo uma versão ativa por `workspace × offer` por constraint parcial no PostgreSQL;
- o conteúdo de cada versão é tratado como snapshot imutável;
- cada ativação gera registro append-only em `offer_profile_activations`.

O runtime usa o registry efetivo do workspace ao persistir novas avaliações de `LeadOpportunity`. Uma versão nova passa a valer para novas avaliações; oportunidades históricas com versão diferente não são sobrescritas sem reanálise explícita. Isso preserva a validade do A/B e da atribuição histórica.

O rollback não cria uma versão sintética nem recalcula o passado: ele reativa o snapshot histórico exato selecionado, desativa a versão corrente e registra a operação no log de ativações. O baseline anterior à primeira publicação também pode ser restaurado.

Endpoints operacionais:

- `POST /api/intelligence/learning-proposals/{proposal_id}/publish` — manager-only;
- `GET /api/intelligence/offer-profile-versions` — analyst/manager;
- `POST /api/intelligence/offer-profile-versions/{offer_key}/rollback` — manager-only.

A infraestrutura existente de comparação A/B continua sendo a porta de entrada do learning. A exploração automática permanece opcional conforme o roadmap; não é requisito para publicar uma alteração nem recebe permissão para autoeditar produção.

## Limites honestos de validação

A **infraestrutura de UAT real** dos três CRMs está pronta e produz evidência persistente. Entretanto, um provider só pode ser declarado certificado depois que a própria execução `/certify` tiver rodado com credenciais reais do workspace e gravado `PASSED`. Sem as credenciais/contas AlphaMec nesta implementação, não se afirma que Pipedrive, HubSpot ou Salesforce já passaram por UAT de produção.

Para Salesforce, `PASSED` comprova autenticação real; o check de leitura incremental informa explicitamente `not_applicable` até existir SOQL/mapeamento específico da conta. Para Pipedrive e HubSpot, `PASSED` cobre autenticação e leitura read-only do adapter.

Cobertura e precision do sistema continuam dependendo das fontes reais configuradas. A arquitetura de federação escolhe melhor entre fontes disponíveis, mas não inventa cobertura que os providers não oferecem.
