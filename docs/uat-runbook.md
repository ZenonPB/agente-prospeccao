# UAT — AlphaMec Release Candidate

> **RUNBOOK · atualizado em 2026-09-13.** Executar somente em ambiente
> autorizado, com workspaces e credenciais de teste/produção explicitamente
> identificados. Nunca declarar campanha real concluída sem evidência.

## Objetivo

Provar que a plataforma pode substituir a planilha e operar com segurança em
multi-workspace antes do RC.

## Pré-condições

- migrations em `head` e verifier verde;
- CI do commit testado completamente verde;
- ao menos dois workspaces A/B;
- usuários MANAGER e CONSULTOR em ambos;
- OfferProfiles publicados distintos em A/B para uma mesma key de teste;
- providers externos somente se houver credencial/consentimento;
- dados sintéticos para testes destrutivos.

## Bloco 1 — isolamento

1. obter UUID de Company/Person/Lead/Opportunity de A;
2. autenticar em B e tentar acessar pelas APIs/telas;
3. esperado: 404/403 conforme contrato, nenhum dado parcial;
4. repetir para tasks, outcomes, analytics e importação;
5. CONSULTOR deve enxergar apenas carteira/pool permitido;
6. MANAGER/owner deve enxergar toda a própria organização.

## Bloco 2 — OfferProfile por workspace

1. publicar overlay A e overlay B com diferenças observáveis;
2. disparar jobs concorrentes;
3. verificar snapshots/score/plano de discovery usados por cada job;
4. confirmar que A nunca usa versão/configuração de B;
5. rollback em A e repetir sem afetar B.

## Bloco 3 — CRM

Fluxo mínimo:

1. abrir Company 360;
2. navegar para Person 360;
3. navegar para Opportunity 360;
4. atribuir owner/estágio/valor/próxima ação quando a edição 360 estiver pronta;
5. criar/concluir tarefa;
6. registrar contato/reunião/proposta/perda/conversão;
7. confirmar timeline e outcome correto;
8. confirmar que refresh/navegação preserva estado.

## Bloco 4 — importador histórico

Após implementação:

- upload de planilha real sanitizada;
- preview sem escrita;
- mapping explícito;
- linhas inválidas destacadas;
- dedupe de Company/Person/Lead;
- confirmação;
- relatório final;
- reimportação do mesmo arquivo sem duplicação indevida;
- auditoria/provenance da importação.

## Bloco 5 — Filter Context/BI

Usar o mesmo conjunto de filtros em dashboards diferentes e conferir:
- período;
- owner;
- campanha;
- oferta/versão;
- estágio;
- segmento/região;
- provider.

Números devem reconciliar com queries/linhas conhecidas da base.

## Bloco 6 — Golden Path troféus/eventos/MEJ

Cenário prioritário:

`evento/organizador → Company → Person/decisor → trophies → score/evidência → Next Best Action → tarefa/contato → outcome → BI`.

Verificar que a especificidade está em OfferProfile/providers, não em hardcode
do pipeline.

## Bloco 7 — campanha real autorizada

Somente após os blocos anteriores:
- campanha pequena e controlada;
- registrar correlation IDs;
- medir candidatos → qualificados → acionáveis → contatos → respostas → reuniões;
- medir custo/latência/coverage/precision/routability/bounce;
- revisar manualmente falsos positivos/negativos.

## Registro de achados

Classificar cada achado:
- `BLOCKS_ALPHAMEC`;
- `IMPORTANT_ALPHAMEC`;
- `DEFER_TO_V2`.

Registrar: passos, esperado, observado, workspace, usuário, entidade, timestamp,
commit e correlation ID quando houver.

## Critério de aprovação

RC só é aprovado se não houver `BLOCKS_ALPHAMEC`, isolamento for comprovado,
fluxo CRM não depender da planilha para estado corrente e o Golden Path puder
ser repetido com resultados auditáveis.
