# Especificação — Integração do Sistema de Prospecção com LinkedIn

## 1. Objetivo

Construir uma integração/módulo de inteligência comercial que complemente o sistema atual de prospecção da Empresa Júnior, usando o LinkedIn como fonte de descoberta, validação e enriquecimento de leads.

O sistema deve ajudar o usuário a:

1. encontrar empresas que tenham maior probabilidade de comprar os serviços da empresa;
2. identificar as pessoas certas dentro dessas empresas;
3. localizar e validar seus perfis no LinkedIn;
4. distinguir decisores de funcionários sem poder de compra;
5. enriquecer os registros existentes da planilha/CRM;
6. evitar duplicidade de leads;
7. gerar um score de qualidade/prioridade;
8. explicar por que determinado lead é bom ou ruim;
9. preservar o fluxo atual de prospecção, incluindo responsável, pitch, follow-ups, status e pós-venda;
10. permitir pesquisa orientada por nicho/oferta, por exemplo: clínicas de psicologia interessadas em landing pages.

O sistema NÃO deve ser projetado assumindo que o LinkedIn oferece uma API pública irrestrita para pesquisa de pessoas/empresas. A implementação deve usar somente APIs, integrações, permissões e mecanismos oficialmente disponíveis para a conta/aplicação. Atualmente, integrações de Sales Navigator dependem do programa SNAP e a documentação oficial informa que novos parceiros não estão sendo aceitos no momento. Portanto, a arquitetura deve ser desacoplada e suportar fallback por pesquisa assistida pelo usuário e/ou fontes externas legítimas, sem scraping ou automação proibida pelo LinkedIn.

---

# 2. Contexto do sistema atual

A planilha atual funciona como um CRM operacional distribuído por membros da equipe.

Existem abas individuais para membros da prospecção, incluindo:

- GUI
- LEO
- Rapha
- Maria
- Zenon
- GUZZO
- ARTHUR

Também existe uma aba/modelo de planilha.

As abas individuais possuem, com pequenas variações, os seguintes campos:

| Campo atual | Função |
|---|---|
| LEAD | Pessoa que está sendo prospectada |
| Empresa | Empresa do lead |
| Prospecção | Data em que o lead entrou na prospecção |
| PITCH ENVIADO | Indica se o primeiro contato/pitch foi enviado |
| PITCH | Data do pitch |
| 1º Follow-up | Data do primeiro follow-up |
| 2º Follow-up | Data do segundo follow-up |
| 3º Follow-up | Data do terceiro follow-up |
| 4º Follow-up | Presente em algumas versões da planilha |
| RESPONDEU? | Indica se houve resposta |
| CARGO | Cargo do contato |
| Observações lead | Observações qualitativas |
| Status | Estado comercial do lead |
| DATA status | Data da alteração de status |
| CONTRATO FINAL | Resultado/estado contratual |
| ANOTAÇÕES | Informações adicionais |
| DATA CONTATO PÓS-VENDA | Data de contato pós-venda |
| Follow-up | Follow-up pós-venda |
| PÓS VENDA POR | Responsável pelo pós-venda |
| Link ou Telefone ou e-mail do Lead | Canal/contato externo |
| Colunas auxiliares | Campos livres atualmente existentes |

A integração com LinkedIn deve **enriquecer esse modelo**, e não destruir o histórico comercial já existente.

---

# 3. Conceito central

O sistema deve separar claramente três entidades:

## 3.1 Empresa

Representa a organização prospectada.

Exemplos:

- Clínica de Psicologia X
- Empresa Y
- Startup Z

## 3.2 Pessoa

Representa uma pessoa que trabalha ou trabalhou na empresa.

Exemplos:

- João Silva
- Maria Souza

## 3.3 Oportunidade/Lead

Representa a relação comercial entre uma pessoa, uma empresa, uma oferta e um responsável da equipe.

Exemplo:

> João Silva → Clínica X → Landing Page → Zenon → Em prospecção

Essa separação é obrigatória para evitar problemas quando:

- duas pessoas da mesma empresa forem prospectadas;
- uma pessoa mudar de empresa;
- uma empresa tiver vários decisores;
- dois membros da equipe encontrarem a mesma empresa;
- um mesmo contato for usado para ofertas diferentes.

---

# 4. Objetivo comercial da integração

A integração não deve simplesmente "achar pessoas no LinkedIn".

Ela deve responder:

> "Qual empresa vale a pena prospectar, quem devemos abordar dentro dela e por quê?"

O sistema deve produzir algo semelhante a:

```text
Empresa: Clínica Exemplo

Fit da empresa: 91/100
Prioridade: ALTA

Motivos:
- 11–50 funcionários
- atua em psicologia
- atende público particular
- Instagram ativo
- 4.800 seguidores
- não possui site próprio
- possui 127 avaliações no Google
- boa reputação
- presença digital relevante
- potencial para landing page

Decisor recomendado:
Ana Souza
Cargo: Fundadora / Psicóloga
LinkedIn: [perfil]

Confiança do match: 94%

Abordagem sugerida:
"Vi que a clínica possui uma presença bastante ativa..."
```

---

# 5. Arquitetura recomendada

A arquitetura deve ser modular.

```text
                    ┌───────────────────┐
                    │   Interface Web   │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ Prospecção API    │
                    └─────────┬─────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
 ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
 │ Company Finder │  │ Person Finder  │  │ Enrichment     │
 │                │  │                │  │ Engine         │
 └───────┬────────┘  └───────┬────────┘  └───────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             ▼
                    ┌───────────────────┐
                    │ Lead Scoring      │
                    └─────────┬─────────┘
                              ▼
                    ┌───────────────────┐
                    │ Deduplication     │
                    └─────────┬─────────┘
                              ▼
                    ┌───────────────────┐
                    │ CRM / Database    │
                    └───────────────────┘
```

---

# 6. Camada de descoberta

O sistema deve aceitar diferentes fontes de descoberta.

## Fontes possíveis

1. LinkedIn/Sales Navigator, quando houver acesso oficial;
2. Google Maps/Places;
3. mecanismos de busca;
4. sites institucionais;
5. Instagram ou outras fontes públicas, quando legalmente acessíveis;
6. bases de dados comerciais legítimas;
7. entrada manual;
8. importação da planilha existente.

Nenhuma fonte deve ser considerada obrigatória.

O sistema deve funcionar mesmo que a integração oficial do LinkedIn não esteja disponível.

---

# 7. LinkedIn como fonte de enriquecimento

Quando uma empresa já existir no sistema, a integração deve tentar encontrar:

### Empresa

- nome;
- LinkedIn Company Page;
- URL/vanity URL;
- domínio;
- localização;
- setor;
- tamanho estimado;
- informações públicas disponíveis;
- identificador oficial, quando disponível.

### Pessoas

Para cada empresa, procurar candidatos como:

- Founder;
- Co-Founder;
- Owner;
- Sócio;
- Sócia;
- Proprietário;
- Proprietária;
- CEO;
- Diretor;
- Diretora;
- Managing Director;
- General Manager;
- Coordenador;
- Coordenadora;
- Head;
- Manager;
- responsável pela área relacionada à oferta.

A lista de cargos deve ser configurável por nicho.

---

# 8. Matching de empresa

O sistema não deve confiar apenas no nome da empresa.

Deve calcular uma identidade provável utilizando:

1. nome normalizado;
2. domínio;
3. cidade;
4. telefone;
5. endereço;
6. site;
7. LinkedIn Company Page;
8. identificadores oficiais, quando disponíveis.

Exemplo:

```text
"Clínica São Lucas"
"Clinica Sao Lucas"
"Clínica São Lucas Psicologia"

```

devem poder ser reconhecidas como a mesma organização quando os demais sinais forem compatíveis.

---

# 9. Matching de pessoa

Ao tentar encontrar o LinkedIn de um lead existente, o sistema deve usar múltiplos sinais:

```text
nome
+
empresa
+
cargo
+
cidade
+
domínio/website da empresa
+
setor
```

Nunca deve considerar apenas o nome.

Exemplo:

```text
Entrada:
Nome: João Carlos Silva
Empresa: Clínica Exemplo
Cargo: Diretor
Cidade: Araraquara

Candidato A:
João Carlos Silva
Diretor — Clínica Exemplo
Araraquara
=> Match muito forte

Candidato B:
João Carlos Silva
Engenheiro — Empresa ABC
São Paulo
=> Match inválido
```

---

# 10. Score de confiança do LinkedIn

Cada correspondência deve possuir:

```text
linkedin_match_score: 0–100
```

Sugestão inicial:

| Sinal | Peso |
|---|---:|
| Nome compatível | 25 |
| Empresa compatível | 30 |
| Cargo compatível | 15 |
| Cidade compatível | 10 |
| Setor compatível | 10 |
| Site/domínio relacionado | 10 |

Classificação:

```text
90–100 = MATCH MUITO FORTE
75–89  = MATCH FORTE
60–74  = REVISÃO HUMANA
0–59   = NÃO CONFIÁVEL
```

O sistema nunca deve apresentar um perfil como confirmado quando a confiança estiver abaixo do limite configurado.

---

# 11. Lead scoring comercial

Além do score do LinkedIn, deve existir um score comercial separado:

```text
lead_score: 0–100
```

Esse score mede a qualidade da oportunidade.

Para landing pages, uma configuração inicial pode ser:

| Critério | Pontos |
|---|---:|
| Empresa pequena/média | +10 |
| Nicho prioritário | +15 |
| Decisor identificado | +15 |
| LinkedIn do decisor encontrado | +10 |
| Não possui site | +25 |
| Site ruim/desatualizado | +15 |
| Instagram ativo | +10 |
| Boa presença no Google | +10 |
| Muitas avaliações | +5 |
| Vários profissionais | +10 |
| Atendimento particular | +10 |
| Evidência de investimento em marketing | +10 |

O score deve ser configurável por campanha.

---

# 12. Campanhas

A prospecção deve funcionar por campanhas.

Exemplo:

```text
Campanha:
Landing Pages — Clínicas de Psicologia

ICP:
- 1–50 funcionários
- Brasil
- prioridade São Paulo
- clínica/consultório
- presença digital ativa
- site inexistente ou fraco
- potencial de aquisição de pacientes
```

Outra campanha poderia ser:

```text
Sistemas Web — Pequenas Indústrias
```

Outra:

```text
Landing Pages — Clínicas Médicas
```

O sistema não deve possuir regras de scoring fixas no código.

As regras devem ser configuráveis.

---

# 13. ICP configurável

Cada campanha deve possuir:

```json
{
  "name": "Landing Pages - Psicologia",
  "target_company_size": ["1-10", "11-50"],
  "target_industries": [
    "Mental Health Care",
    "Medical Practices"
  ],
  "locations": [
    "Araraquara",
    "São Carlos",
    "Ribeirão Preto"
  ],
  "target_titles": [
    "Founder",
    "Owner",
    "Sócio",
    "Diretor",
    "Psicólogo"
  ],
  "required_signals": [],
  "preferred_signals": [
    "active_instagram",
    "no_website",
    "good_google_reviews"
  ]
}
```

---

# 14. Descoberta do decisor

Para cada empresa, o sistema deve tentar encontrar primeiro a pessoa com maior probabilidade de decisão.

Ordem inicial de prioridade:

```text
Founder / Owner
↓
Sócio
↓
CEO
↓
Diretor
↓
Diretora
↓
Head
↓
Gerente
↓
Coordenador
↓
Especialista relacionado à oferta
```

Para empresas muito pequenas:

```text
Founder / Owner / Sócio
```

deve receber peso maior.

Para empresas maiores:

```text
Diretor / Head / Gerente
```

pode receber peso maior.

---

# 15. Vários decisores

Não assumir que uma empresa possui apenas um contato.

O sistema pode armazenar:

```text
Empresa
 ├── Pessoa A — Founder — prioridade 1
 ├── Pessoa B — Diretora — prioridade 2
 └── Pessoa C — Marketing — prioridade 3
```

O sistema deve recomendar apenas uma pessoa como:

```text
recommended_contact
```

mas manter os demais candidatos.

---

# 16. Deduplicação

Antes de criar um lead, verificar se a empresa ou pessoa já existe.

Chaves de deduplicação:

### Pessoa

Prioridade:

1. LinkedIn profile identifier;
2. e-mail;
3. telefone;
4. combinação nome + empresa;
5. combinação nome + domínio;
6. nome + cidade + cargo.

### Empresa

Prioridade:

1. LinkedIn organization identifier;
2. domínio;
3. CNPJ, quando disponível;
4. telefone;
5. combinação nome + cidade.

Se houver possível duplicidade, não criar automaticamente.

Criar:

```text
POSSÍVEL DUPLICATA
```

e permitir confirmação humana.

---

# 17. Integração com a planilha atual

A integração deve mapear os dados atuais.

Exemplo:

```text
LEAD
    ↓
person.name

Empresa
    ↓
company.name

Prospecção
    ↓
lead.created_at

PITCH ENVIADO
    ↓
outreach.first_message_sent

PITCH
    ↓
outreach.first_message_at

1º Follow-up
    ↓
outreach.followups[0]

2º Follow-up
    ↓
outreach.followups[1]

3º Follow-up
    ↓
outreach.followups[2]

RESPONDEU?
    ↓
lead.replied

CARGO
    ↓
person.current_title

Observações lead
    ↓
lead.notes

Status
    ↓
lead.status

DATA status
    ↓
lead.status_changed_at

CONTRATO FINAL
    ↓
deal.contract_status

ANOTAÇÕES
    ↓
lead.notes / deal.notes

Link ou Telefone ou e-mail do Lead
    ↓
contact_methods
```

---

# 18. Novos campos recomendados

Adicionar ao sistema:

```text
company_linkedin_url
company_linkedin_id

person_linkedin_url
person_linkedin_id

linkedin_match_score
linkedin_match_status

company_website
company_domain
company_size
company_industry
company_city
company_state

lead_score
lead_priority

recommended_contact
recommended_contact_reason

icp_match
icp_match_reasons
icp_mismatch_reasons

website_status
website_quality_score

instagram_url
instagram_activity

google_rating
google_review_count

discovery_source

last_enriched_at
```

---

# 19. Estado do enriquecimento

Cada lead deve possuir um estado:

```text
NOT_ENRICHED
SEARCHING
ENRICHED
NEEDS_REVIEW
VERIFIED
FAILED
```

Isso evita repetir pesquisas desnecessariamente.

---

# 20. Explicabilidade

Toda recomendação do sistema deve possuir justificativa.

Não retornar somente:

```text
Score: 92
```

Retornar:

```text
Score: 92

Razões:
+ Empresa possui 11–50 funcionários
+ Atua em psicologia
+ Instagram ativo
+ Não possui site
+ 142 avaliações no Google
+ Fundadora encontrada no LinkedIn
+ Atua na região-alvo
```

Isso é essencial para que o vendedor confie no sistema.

---

# 21. Pesquisa assistida pelo LinkedIn

Quando não existir uma API oficial que permita realizar determinada busca automaticamente, o sistema deve fornecer uma pesquisa assistida.

Exemplo:

```text
Empresa:
Clínica Exemplo

Pesquise no LinkedIn:

"Clínica Exemplo" Founder
"Clínica Exemplo" Sócia
"Clínica Exemplo" Diretora
"Clínica Exemplo" Psicóloga

[Copiar consulta]
[Abrir pesquisa]
[Adicionar perfil encontrado]
```

O usuário pode então colar a URL do perfil.

O sistema valida e associa o perfil ao lead.

Isso é preferível a construir scraping ou automação não autorizada.

---

# 22. Pesquisa externa

Quando apropriado, gerar consultas como:

```text
site:linkedin.com/in "Clínica Exemplo" "Founder"
site:linkedin.com/in "Clínica Exemplo" "Sócia"
site:linkedin.com/in "Clínica Exemplo" "Psicóloga"
```

Também permitir:

```text
"Nome da empresa" "Nome da pessoa" LinkedIn
```

O sistema deve sempre tratar resultados externos como candidatos, não como verdade absoluta.

---

# 23. Pipeline de enriquecimento

Para cada novo lead:

```text
1. Normalizar empresa
2. Verificar duplicidade
3. Identificar domínio
4. Identificar setor
5. Identificar localização
6. Avaliar tamanho
7. Procurar página da empresa no LinkedIn
8. Procurar decisores
9. Calcular match de cada pessoa
10. Selecionar candidatos
11. Calcular ICP score
12. Calcular lead score
13. Gerar justificativas
14. Salvar evidências
15. Solicitar revisão quando necessário
16. Disponibilizar para prospecção
```

---

# 24. Evidências

O sistema deve armazenar a origem de cada dado.

Exemplo:

```json
{
  "field": "company_size",
  "value": "11-50",
  "source": "linkedin",
  "collected_at": "2026-08-10"
}
```

Outro:

```json
{
  "field": "google_review_count",
  "value": 142,
  "source": "google",
  "collected_at": "2026-08-10"
}
```

Não permitir que a IA invente dados.

Se não houver evidência:

```text
unknown
```

e não:

```text
false
```

---

# 25. Regras contra alucinação

A IA nunca deve:

- inventar perfil de LinkedIn;
- inventar cargo;
- inventar empresa;
- inventar e-mail;
- inventar telefone;
- afirmar que alguém é dono de uma empresa sem evidência;
- afirmar que uma pessoa trabalha atualmente em uma empresa sem evidência atual;
- transformar um candidato de busca em match confirmado.

Quando houver incerteza:

```text
confidence < threshold
```

deve ser marcado para revisão humana.

---

# 26. Atualização de informações

Dados de pessoas mudam.

O sistema deve registrar:

```text
first_seen_at
last_verified_at
source
```

Se um perfil mudar de empresa, não apagar o histórico.

Registrar:

```text
employment_history
```

e atualizar:

```text
current_company
current_title
```

---

# 27. Interface recomendada

Na tela do lead:

```text
┌────────────────────────────────────────────┐
│ João Silva                                 │
│ Clínica Exemplo                            │
│                                            │
│ Lead Score: 92/100       PRIORIDADE ALTA   │
│                                            │
│ Cargo: Fundador                            │
│                                            │
│ LinkedIn                                   │
│ ✓ Perfil encontrado                        │
│ Match: 96%                                 │
│                                            │
│ [Abrir LinkedIn]                           │
│                                            │
│ Empresa                                    │
│ 11–50 funcionários                         │
│ Psicologia                                 │
│ Araraquara                                 │
│                                            │
│ Site: NÃO POSSUI                           │
│ Instagram: ATIVO                           │
│ Google: 4,9 ★ / 142 avaliações             │
│                                            │
│ Por que este lead é bom?                   │
│ • ICP ideal                                │
│ • Não possui site                          │
│ • Presença digital ativa                   │
│ • Decisor identificado                     │
│                                            │
│ [Adicionar à prospecção]                   │
└────────────────────────────────────────────┘
```

---

# 28. Lista de leads

A lista deve permitir ordenar por:

- Lead Score;
- ICP Score;
- Match do LinkedIn;
- prioridade;
- cidade;
- setor;
- tamanho;
- responsável;
- status;
- data da última interação;
- existência de site;
- existência de decisor;
- origem.

Filtros:

```text
[ ] Sem site
[ ] Site ruim
[ ] Instagram ativo
[ ] Decisor encontrado
[ ] LinkedIn confirmado
[ ] Score > 80
[ ] Ainda não contatado
[ ] Sem responsável
```

---

# 29. Distribuição entre membros

A planilha atual possui uma aba por membro.

O novo sistema deve preservar esse conceito através de:

```text
owner_user_id
```

Ao criar um lead:

```text
responsável = Zenon
```

ou:

```text
responsável = Maria
```

O sistema deve impedir que dois membros trabalhem acidentalmente o mesmo lead.

Se houver conflito:

```text
LEAD JÁ ESTÁ ATRIBUÍDO A:
Zenon Bergamo

Deseja solicitar transferência?
```

---

# 30. Regras de ownership

Uma empresa pode ter múltiplos contatos, mas cada oportunidade deve ter um responsável.

Exemplo:

```text
Empresa: Clínica X

Zenon
 └── Ana — Fundadora

Maria
 └── Carlos — Marketing
```

O sistema deve sinalizar que os dois contatos pertencem à mesma empresa.

---

# 31. Geração de pitch

A IA pode usar os dados enriquecidos para gerar um pitch contextual.

Não gerar mensagens genéricas.

Exemplo:

```text
Contexto encontrado:

- clínica possui Instagram ativo;
- não possui site;
- 8 profissionais;
- 4,8 estrelas;
- 120 avaliações;
- contato é a fundadora.

Mensagem:

"Olá, Ana! Tudo bem?

Encontrei a Clínica X enquanto pesquisava clínicas de
psicologia da região e vi que vocês possuem uma presença
bem ativa no Instagram.

Notei também que vocês ainda não possuem um site próprio,
e achei que poderia existir uma oportunidade interessante
para transformar parte desse tráfego em novos contatos..."
```

O sistema deve gerar a mensagem a partir de fatos comprovados.

---

# 32. Não automatizar envio sem autorização

A primeira versão deve focar em:

```text
encontrar
+
qualificar
+
enriquecer
+
organizar
+
recomendar
```

Não deve assumir:

```text
enviar mensagens automaticamente
```

Especialmente no LinkedIn.

O envio deve permanecer manual ou utilizar somente mecanismos oficiais/autorizados pela plataforma.

---

# 33. Segurança e credenciais

Nunca armazenar:

- senha do LinkedIn;
- cookies do navegador;
- sessão do usuário;
- tokens em texto puro;
- credenciais no frontend.

Se houver OAuth:

```text
Frontend
   ↓
Backend
   ↓
OAuth Provider
   ↓
Encrypted Token Storage
```

Tokens devem ser criptografados e possuir escopo mínimo.

---

# 34. Integração oficial com LinkedIn

A implementação deve verificar primeiro quais produtos/permissões estão realmente disponíveis para a aplicação.

A documentação oficial atual indica que:

- acesso a determinadas APIs depende de aprovação;
- funcionalidades de Sales Navigator dependem do programa SNAP;
- a documentação atual informa que o LinkedIn não está aceitando novos parceiros SNAP neste momento;
- APIs de organização têm permissões específicas;
- APIs de perfil não equivalem a uma API pública irrestrita de pesquisa de todos os membros.

Portanto:

```text
if official_api_available:
    use_official_api()
else:
    use_assisted_search()
```

Nunca construir o produto assumindo que endpoints internos do LinkedIn, scraping do site ou automação de navegador são APIs oficiais.

---

# 35. Estratégia de fallback

A integração deve possuir adapters:

```text
LinkedInProvider
GoogleProvider
WebsiteProvider
MapsProvider
ManualProvider
```

Interface conceitual:

```typescript
interface PersonDiscoveryProvider {
  searchPeople(input: PersonSearchInput): Promise<PersonCandidate[]>
}

interface CompanyDiscoveryProvider {
  searchCompanies(input: CompanySearchInput): Promise<CompanyCandidate[]>
}
```

Implementações:

```text
OfficialLinkedInProvider
SearchEngineProvider
ManualLinkedInProvider
```

Assim, o restante do sistema não depende de uma implementação específica.

---

# 36. Banco de dados sugerido

Entidades mínimas:

```text
User
Company
Person
Employment
Lead
Campaign
LeadScore
LinkedInProfile
CompanySocialProfile
ContactMethod
Evidence
Outreach
FollowUp
Deal
LeadAssignment
```

Relacionamentos:

```text
Company 1 ─── N Employment
Person  1 ─── N Employment

Company 1 ─── N Lead
Person  1 ─── N Lead

Campaign 1 ─── N Lead

Lead 1 ─── N Evidence
Lead 1 ─── N Outreach
Lead 1 ─── N FollowUp

User 1 ─── N LeadAssignment
```

---

# 37. Modelo simplificado de Lead

```typescript
type Lead = {
  id: string

  companyId: string
  personId?: string
  campaignId: string
  ownerUserId: string

  status: LeadStatus

  leadScore: number
  priority: "LOW" | "MEDIUM" | "HIGH"

  icpMatch: boolean
  icpReasons: string[]
  icpMismatchReasons: string[]

  linkedinMatchScore?: number
  linkedinMatchStatus:
    | "NOT_FOUND"
    | "CANDIDATE"
    | "NEEDS_REVIEW"
    | "VERIFIED"

  notes?: string

  createdAt: Date
  updatedAt: Date
  lastEnrichedAt?: Date
}
```

---

# 38. Modelo simplificado de Person

```typescript
type Person = {
  id: string

  fullName: string
  firstName?: string
  lastName?: string

  currentTitle?: string
  city?: string
  state?: string

  linkedinUrl?: string
  linkedinId?: string

  email?: string
  phone?: string

  confidence?: number

  createdAt: Date
  updatedAt: Date
}
```

---

# 39. Modelo simplificado de Company

```typescript
type Company = {
  id: string

  legalName?: string
  displayName: string

  domain?: string
  website?: string

  linkedinUrl?: string
  linkedinId?: string

  industry?: string
  employeeRange?: string

  city?: string
  state?: string
  country?: string

  instagramUrl?: string

  googleRating?: number
  googleReviewCount?: number

  createdAt: Date
  updatedAt: Date
}
```

---

# 40. API interna recomendada

Endpoints conceituais:

```http
POST /campaigns
GET  /campaigns

POST /companies/discover
GET  /companies/:id

POST /companies/:id/enrich
POST /companies/:id/find-decision-makers

GET /companies/:id/linkedin

POST /people/match-linkedin

GET /leads
POST /leads
PATCH /leads/:id

POST /leads/:id/enrich
POST /leads/:id/score
POST /leads/:id/generate-pitch

POST /leads/:id/assign

GET /search/linkedin
```

Os endpoints reais devem ser adaptados à arquitetura existente.

---

# 41. Exemplo de fluxo completo

Usuário cria campanha:

```text
Landing Pages — Psicologia
```

Define:

```text
Cidade:
Araraquara

Tamanho:
1–50

Setor:
Psicologia

Oferta:
Landing Page
```

O sistema encontra:

```text
Clínica Vida
```

Enriquecimento:

```text
Site: inexistente
Instagram: ativo
Google: 4,9 / 182 avaliações
Funcionários: 11–50
```

Pesquisa decisores:

```text
Ana Silva — Fundadora
Carlos Souza — Psicólogo
Mariana Costa — Coordenadora
```

Matching:

```text
Ana Silva → 96%
Carlos Souza → 73%
Mariana Costa → 89%
```

Recomendação:

```text
Ana Silva
```

Score:

```text
94/100
```

Resultado:

```text
PRIORIDADE ALTA
```

O usuário clica:

```text
[Adicionar à minha prospecção]
```

O sistema cria:

```text
Lead: Ana Silva
Empresa: Clínica Vida
Responsável: usuário atual
Campanha: Landing Pages — Psicologia
Status: NOVO
```

A partir daí, o fluxo tradicional da planilha continua:

```text
NOVO
↓
PITCH ENVIADO
↓
1º FOLLOW-UP
↓
2º FOLLOW-UP
↓
3º FOLLOW-UP
↓
RESPONDEU
↓
REUNIÃO
↓
PROPOSTA
↓
CONTRATO
```

---

# 42. Métricas

O sistema deve medir:

### Descoberta

- empresas encontradas;
- pessoas encontradas;
- matches de LinkedIn;
- taxa de match;
- leads duplicados;
- leads qualificados.

### Comercial

- pitch enviado;
- taxa de resposta;
- taxa de reunião;
- taxa de proposta;
- taxa de fechamento;
- ticket médio;
- conversão por campanha;
- conversão por responsável;
- conversão por nicho.

### Qualidade do algoritmo

- leads score alto que responderam;
- leads score baixo que responderam;
- precisão dos matches;
- falsos positivos;
- falsos negativos.

Isso permitirá recalibrar o algoritmo com dados reais da equipe.

---

# 43. Aprendizado baseado no histórico

O sistema deve aproveitar a própria planilha histórica.

Exemplo:

Se os dados mostrarem:

```text
Clínicas pequenas
+ sem site
+ fundador identificado
+ Instagram ativo
```

possuem taxa de resposta muito maior, o algoritmo deve aumentar o peso desses sinais.

Inicialmente utilizar regras determinísticas.

Posteriormente, implementar modelo estatístico/ML:

```text
features
   ↓
historical leads
   ↓
responses
   ↓
meetings
   ↓
contracts
   ↓
conversion model
```

O objetivo final é estimar:

```text
P(resposta)
P(reunião)
P(proposta)
P(fechar)
```

em vez de depender apenas de um score arbitrário.

---

# 44. Importante: não confundir qualidade do lead com match do LinkedIn

Devem existir dois scores independentes:

```text
LinkedIn Match Score
=
"Encontramos a pessoa correta?"

Lead Score
=
"Essa oportunidade vale a pena?"
```

Exemplo:

```text
Lead A
LinkedIn Match: 98
Lead Score: 35

Pessoa correta, mas empresa ruim.

Lead B
LinkedIn Match: 82
Lead Score: 94

Empresa excelente, mas precisamos confirmar o contato.
```

O Lead B pode ser mais importante comercialmente.

---

# 45. Prioridade final

A prioridade pode combinar:

```text
commercial_score
+
linkedin_confidence
+
recency
+
campaign_priority
```

Mas nunca esconder os componentes.

Exibir:

```text
Prioridade: ALTA

Lead Score: 94
LinkedIn Match: 96
ICP Match: 100
```

---

# 46. Requisitos de qualidade

O sistema deve ser:

- modular;
- auditável;
- explicável;
- tolerante a falhas;
- idempotente;
- preparado para múltiplas fontes;
- preparado para múltiplas campanhas;
- preparado para múltiplos usuários;
- preparado para múltiplos contatos por empresa;
- preparado para deduplicação;
- preparado para revisão humana.

---

# 47. Idempotência

Executar:

```text
POST /companies/:id/enrich
```

duas vezes não deve criar dois registros.

O enriquecimento deve atualizar os dados existentes e criar apenas informações novas.

---

# 48. Cache

Não pesquisar novamente o mesmo lead toda vez.

Registrar:

```text
last_searched_at
last_enriched_at
```

e utilizar TTL configurável.

Exemplo:

```text
LinkedIn candidate search:
TTL = 30 dias

Website:
TTL = 7 dias

Google reviews:
TTL = 24 horas
```

Os valores devem ser configuráveis.

---

# 49. Tratamento de erros

Possíveis estados:

```text
SOURCE_UNAVAILABLE
RATE_LIMITED
AUTH_REQUIRED
PERMISSION_DENIED
NO_RESULTS
AMBIGUOUS_MATCH
DUPLICATE
INVALID_INPUT
```

O erro não deve fazer o lead desaparecer.

Exemplo:

```text
LinkedIn:
PERMISSION_DENIED

Ação:
Pesquisa assistida disponível.
```

---

# 50. MVP

A primeira versão NÃO precisa tentar automatizar tudo.

Implementar primeiro:

## Fase 1

```text
Importar planilha
↓
Normalizar empresas/pessoas
↓
Deduplicar
↓
Criar campanhas
↓
Criar ICP
↓
Pesquisar empresas
↓
Encontrar candidatos a decisor
↓
Adicionar LinkedIn URL manualmente
↓
Calcular match
↓
Calcular lead score
↓
Distribuir para membro
```

## Fase 2

```text
Enriquecimento automático
Website
Google
Redes sociais
Pesquisa externa
```

## Fase 3

```text
Integrações oficiais disponíveis
LinkedIn/Sales Navigator
```

## Fase 4

```text
Machine Learning
Predição de resposta
Predição de fechamento
Otimização automática do ICP
```

---

# 51. Critério de sucesso do MVP

O MVP será considerado bem-sucedido se um membro da equipe conseguir:

```text
1. escolher uma campanha;
2. definir cidade/nicho/tamanho;
3. receber empresas candidatas;
4. ver quais não possuem site;
5. identificar decisores;
6. encontrar/confirmar LinkedIn;
7. visualizar score;
8. entender por que o lead é recomendado;
9. atribuir o lead a si mesmo;
10. iniciar o fluxo normal de prospecção.
```

O sistema deve reduzir drasticamente o trabalho manual de:

```text
"achar empresa"
+
"achar pessoa"
+
"descobrir se ela é decisora"
+
"descobrir LinkedIn"
+
"ver se vale a pena"
+
"organizar na planilha"
```

sem remover o controle humano da prospecção.

---

# 52. Regra principal do projeto

A integração deve ser construída para **melhorar a qualidade das decisões comerciais**, e não simplesmente para coletar o maior número possível de perfis.

O resultado desejado não é:

```text
10.000 contatos encontrados
```

O resultado desejado é:

```text
100 leads altamente qualificados
→
40 contatos abordados
→
15 respostas
→
8 reuniões
→
3 propostas
→
1–2 contratos
```

Portanto, toda funcionalidade deve ser avaliada pela capacidade de aumentar:

```text
qualidade do lead
+
precisão do decisor
+
taxa de resposta
+
taxa de reunião
+
taxa de fechamento
```

e não pelo volume bruto de dados coletados.

---

# 53. Referências oficiais

A implementação deve consultar a documentação atual do LinkedIn antes de desenvolver qualquer integração:

- LinkedIn API — Getting Access
- LinkedIn Sales Navigator Application Platform (SNAP)
- LinkedIn Organization Lookup API
- LinkedIn People APIs
- LinkedIn Sales Navigator Profile Associations API

A documentação oficial deve ser tratada como fonte de verdade para permissões, endpoints, limites e disponibilidade de recursos.

Nunca assumir que um endpoint encontrado em código de terceiros, extensão, fórum ou projeto de scraping é uma API oficial.

