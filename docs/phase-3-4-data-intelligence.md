# Fases 3 + 4 — Freshness, Data Health, Intent e Technographics

## Objetivo

Adicionar uma camada confiável de qualidade e inteligência de dados sem quebrar o pipeline atual e sem criar dependência obrigatória de providers pagos. O sistema passa a separar explicitamente dado **fresco**, **vencido** e **desconhecido**, além de derivar technographics, sinais de intent e um vetor comercial explicável a partir de evidências já coletadas.

## Freshness e TTL

A política central fica em `services/prospecting/freshness_policy.py`. Ausência de data nunca vira automaticamente `stale`: permanece `unknown`.

TTLs iniciais:

| Capability | TTL |
|---|---:|
| company registry | 60 dias |
| website | 30 dias |
| technographics | 30 dias |
| employment | 30 dias |
| email | 30 dias |
| phone | 60 dias |
| jobs | 14 dias |
| news/social/intent | 14 dias |
| events | até a data do evento |

Recomputar score/inteligência **não renova** freshness. A idade só muda quando collector/enricher observa informação nova.

## Data Health

Endpoints:

- `GET /api/data-intelligence/health` — visão gerencial tenant-aware;
- `POST /api/data-intelligence/refresh-plan` — gera plano e, com `enqueue=true`, usa a fila existente de `LEAD_ENRICHMENT`;
- `GET /api/data-intelligence/leads/{id}` — inteligência derivada sem persistir;
- `POST /api/data-intelligence/leads/{id}/recompute` — recomputa e persiste somente derivados, sem falsificar timestamps de observação.

A visão global e o enqueue de refresh exigem `ANALYST`/`MANAGER` ou owner/admin, seguindo a mesma política dos relatórios. Todos os acessos continuam limitados à organização ativa.

O painel `/data-health` mostra:

- dados vencidos e cobertura desconhecida;
- e-mail ausente/suprimido;
- telefone ausente e classificação passiva;
- decisor ausente;
- risco de identidade insuficiente;
- prioridade de refresh;
- saúde de providers nos últimos sete dias, mantendo `failed`, `timeout`, `quota_exceeded`, `disabled` e sucesso semanticamente distintos.

A priorização favorece oportunidades abertas, ações vencidas e lacunas de dados relevantes. O request HTTP nunca chama provider externo diretamente; quando solicitado pelo usuário, apenas agenda jobs na fila já observável.

## Verificação passiva de telefone

`PhoneVerificationService` usa quatro estados:

- `VERIFIED`: somente quando uma fonte confiável declarou verificação;
- `LIKELY_VALID`: formato plausível;
- `UNKNOWN`: não há evidência suficiente;
- `INVALID`: formato impossível/degenerado.

Formato plausível nunca é promovido a `VERIFIED`.

## Technographics

`TechnologyStackProvider` é um provider passivo de custo zero que examina HTML, headers e metadados já coletados. A primeira versão reconhece, quando há evidência explícita:

WordPress, WooCommerce, Shopify, RD Station, HubSpot, Salesforce, TOTVS/Protheus, Omie, Bling, Google Analytics, Meta Pixel, Cloudflare e Next.js.

O contrato permite substituir/complementar esse provider por serviços pagos futuramente sem alterar o domínio nem a API.

## Intent v2

A contribuição de cada sinal segue:

```text
signal_weight × confidence × source_reliability × recency_decay
```

O score final usa saturação suave para evitar que dezenas de sinais fracos façam o score crescer linearmente sem limite.

Famílias iniciais:

- vagas: engenharia mecânica, projetista, manutenção, automação, CNC, TI, operações e dados;
- notícias: nova unidade, expansão, nova fábrica, novo produto, funding e mudança de gestão;
- procurement: licitação, software, industrial e eventos/premiação;
- eventos e social quando já existem evidências com provenance compatível.

`IntentProviderRegistry` fornece adapters passivos para Job Posting, Company News, Procurement, Social e Event. Nesta fase eles **classificam evidências já existentes**; não fazem scraping oculto nem chamadas pagas. Isso preserva a estratégia free-first e cria o seam para futuros providers externos.

## Opportunity Vector v2

Dimensões:

- `icp_fit`;
- `need`;
- `intent`;
- `buying_power`;
- `reachability`;
- `timing`;
- `commercial_fit`;
- `overall`;
- `coverage`.

Dimensão desconhecida continua `null` e é removida do denominador. Portanto `UNKNOWN` não equivale a zero.

Os derivados são gravados em `lead.score_vector` e `lead.evidence_score.phase4`, preservando os contratos e snapshots comerciais existentes.

## Performance

- consultas do Data Health são tenant-scoped desde a raiz;
- Enrichment, Person, Company e Opportunity são lidos em lotes para evitar N+1;
- telemetria de providers é agregada no PostgreSQL com `GROUP BY` em vez de carregar execuções individuais;
- a UI usa cache curto do React Query e invalidação explícita após criação do plano de refresh;
- nenhuma detecção de intent/technographics faz I/O durante o cálculo.

## Segurança e custo

- visão gerencial de Data Health exige papel analítico/gerencial;
- endpoints individuais continuam verificando `organization_id` junto ao ID do lead;
- providers passivos têm custo zero e não recebem secrets;
- nenhum provider pago é chamado implicitamente;
- refresh reaproveita jobs, quotas, observabilidade, retries e políticas existentes;
- estados `empty`, `failed`, `disabled`, `quota_exceeded` e `unknown` não são colapsados em sucesso.

## Limites intencionais desta entrega

- Job change automático exige histórico canônico de Employment; sem histórico confiável não é inventado como capability concluída.
- Email Verification v2 reaproveita verificação/supressão existentes; catch-all e histórico avançado de bounce/engagement continuam evolução posterior.
- Job/News/Social intent externos ainda dependem de evidências coletadas por fontes existentes ou providers futuros. PNCP e Event Discovery já podem alimentar o registry com dados reais.
- O refresh desta fase é priorizado e enfileirado sob demanda. Monitoramento contínuo/schedules automáticos pertencem à Fase 6 para evitar gasto involuntário de quota gratuita.
- UAT de providers externos só pode ser declarado quando houver ambiente e credenciais reais.

Esses limites são deliberados: helpers ou placeholders não são marcados como capabilities completas sem consumidor, evidência, observabilidade e teste real.