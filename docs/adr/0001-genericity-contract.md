# ADR 0001 — Contrato de genericidade do core de prospecção

- Status: aceito
- Data: 2026-09-11
- Escopo: Task 2 do roadmap (Genericity Test Harness)

## Contexto

A plataforma deve atender múltiplas ofertas e organizações com **um core
genérico**, onde a diferença entre verticais vive em configuração
(`OfferProfile`), providers plugáveis e outcomes — não em código do motor.

O risco concreto é a erosão silenciosa: cada nova vertical adiciona um `if` no
core "só desta vez", e em poucos ciclos o motor conhece cada domínio pelo nome.
O repositório já tem dois casos assim (ver Baseline).

Decidimos usar Troféus/Eventos e Sistemas Web/ERP como testes arquiteturais
opostos, com Engenharia Mecânica como prova de configurabilidade teórica. Um
contrato executável é o que impede a regressão entre as fases.

## Decisão

Toda capability genérica do core está sob **contrato de genericidade**:

1. é uma só implementação, usada por todas as verticais;
2. recebe diferença de comportamento por configuração (`OfferProfile`), nunca
   por branch de domínio no core;
3. produz saída com o mesmo formato para qualquer vertical;
4. é configurável para Engenharia Mecânica sem implementação dedicada.

O contrato é verificado por um harness em duas frentes.

### Frente estática — pureza do core

Varredura AST dos módulos sob contrato detecta:

- `identity_literal`: literal de string igual a uma chave de oferta/vertical
  conhecida (ex.: `"trophies"`);
- `identity_branch`: comparação entre expressão de identidade de perfil
  (`profile_key`, `offer_key`, `vertical`, `archetype`) e literal de string.

Escopo: `services/workers/src/services/prospecting/**` mais
`discovery_planner_service.py`. Fora do escopo por desenho:

- `default_profiles.py` — é a camada de configuração; declarar chaves é a sua
  função;
- **adapters de provider** — ser específico de um provider (Google Places,
  Hunter, CNAE) é legítimo; ser específico de uma **oferta** não é;
- serviços legados indexados por `AnalysisProfile` (`scoring_service`,
  `segment_suggestion_service`, etc.) — tabelas de configuração da geração
  anterior, com migração prevista nas fases seguintes.

Escolhas de precisão: casamento por **igualdade exata** (um branch por domínio
usa `== "trophies"`; substring geraria falso positivo em prosa como "presença
digital"); docstrings são ignoradas (documentar domínio é legítimo); literais
que são **nomes de campo** de identidade são descartados (em
`row["offer_key"] == offer_key` o literal é a coluna, não a vertical).

### Frente comportamental — mesma capability, três verticais

As capabilities são exercitadas de forma paramétrica com os três perfis:
validação de perfil, matching/scoring de oportunidade, intent com decay,
próxima melhor ação, discovery dirigido pelo perfil e inferência de buyer role.
As asserções verificam formato idêntico de saída e divergência de resultado
vinda **apenas** da configuração.

Troféus e Engenharia vêm do **registry de produção** (o harness exercita o core
real). `web_erp` é fixture do harness porque a vertical só é implementada na
Task 8 — promover um perfil incompleto para `default_profiles` agora criaria
configuração órfã.

### Ratchet de violações conhecidas

As violações que já existem estão registradas em `KNOWN_VIOLATIONS` com a Task
do roadmap que as remove. O harness falha se:

- aparecer violação nova (a contagem não pode subir); **ou**
- uma entrada ficar obsoleta após a correção (a lista não pode ficar
  desatualizada).

Assim a lista só encolhe, e não vira uma lista permanente de exceções.

## Baseline no momento desta decisão

| Módulo | Tipo | Qtd. | Task que remove |
|---|---|---|---|
| `services/discovery_planner_service.py` | `identity_branch` | 1 | Task 5 — planner genérico dirigido por `OfferProfile` |
| `services/prospecting/event_opportunity_service.py` | `identity_literal` | 4 | Task 6 — vertical de Troféus parametrizada por perfil |
| `services/prospecting/event_opportunity_service.py` | `identity_branch` | 1 | Task 6 — vertical de Troféus parametrizada por perfil |

## Consequências

Positivas:

- regressão de genericidade falha no CI, com o arquivo e a linha apontados;
- o débito arquitetural fica explícito e atribuído a uma Task, em vez de
  implícito;
- adicionar uma vertical passa a ser exercício de configuração, e o harness
  prova isso a cada execução.

Custos e limites aceitos:

- a varredura é estática: pega acoplamento por nome, não acoplamento semântico
  (um core poderia ramificar por um sinal que só uma vertical usa). A frente
  comportamental cobre parte disso, não tudo;
- ao adicionar uma vertical nova, suas chaves precisam entrar em
  `FORBIDDEN_IDENTITIES`;
- perfis de fixture podem divergir da configuração de produção; por isso duas
  das três verticais vêm do registry real.

## Alternativas descartadas

- **Só revisão de código**: não sobrevive à pressão de entrega nem a mudança de
  quem revisa.
- **Proibir qualquer string de domínio no repositório**: quebraria
  `default_profiles`, seeds e adapters, que legitimamente nomeiam domínios.
- **Falhar imediatamente nas violações existentes**: deixaria a suíte vermelha
  antes das Tasks 5 e 6, incentivando a desativação do guard. O ratchet
  preserva o sinal sem bloquear o roadmap.
