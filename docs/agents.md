# Instruções para agentes — `docs/`

> **LIVE · atualizado em 2026-09-13.** Estas regras valem ao editar documentação.
> Para arquitetura atual, leia `README.md`, `00-status-mapa.md`,
> `architecture.md`, `context.md` e `roadmap.md`.

## Hierarquia documental

1. Código + migrations + testes são a evidência executável.
2. Documentos **LIVE** refletem estado corrente.
3. RUNBOOKS descrevem operação atual.
4. ADR/DECISÃO preserva decisões e mudanças.
5. SNAPSHOT HISTÓRICO registra uma fase passada e não deve ser tratado como
   fonte de verdade presente.

A classificação completa está em `README.md`.

## Ao implementar uma capability

Atualize no mesmo PR:
- `00-status-mapa.md` se o estado da capability mudou;
- `architecture.md` se boundary/modelo/runtime mudou;
- `context.md` se agentes futuros precisam conhecer nova invariante;
- `roadmap.md`/`pendencias-pos-consolidacao.md` se backlog foi fechado/aberto;
- documento de domínio específico (OfferProfile, CRM, learning, BI, UAT etc.).

Não marque algo ✅ só porque existe helper, interface, registry ou placeholder.
Exija fluxo real e teste proporcional ao risco.

## Não reescrever história

Arquivos de fase/auditoria classificados como snapshot histórico podem conter
estado antigo de propósito. Não os atualize para parecerem contemporâneos.
Quando um risco histórico continua válido, copie-o para um LIVE doc e indique a
situação atual.

## Terminologia canônica

- workspace = `Organization`;
- conta = `Company`;
- pessoa/decisor = `Person`;
- contexto comercial = `Lead`;
- oportunidade/oferta = `LeadOpportunity`;
- tarefa = `CommercialTask`;
- activity/timeline source = `LeadActivity` e demais eventos reais;
- configuração inteligente da oferta = `OfferProfile` / `OfferProfileVersion`.

## Regras críticas que documentação não pode contradizer

- isolamento multi-workspace é obrigatório;
- OfferProfile publicado é por workspace e learning é human-in-the-loop;
- UNKNOWN não é FALSE;
- uma empresa pode ter múltiplas oportunidades;
- outcome deve ser atribuído à oportunidade correta quando possível;
- CRM 360 é composição das fontes existentes;
- Proposal/Contract/Note não são entidades canônicas completas ainda;
- merge exige CI verde no mesmo HEAD.

## Estilo

- escrever estado observável, não intenção como se fosse entrega;
- separar “entregue”, “em validação” e “planejado”;
- citar PR/commit/teste quando isso melhora rastreabilidade;
- remover percentuais de conclusão sem métrica reprodutível;
- preferir tabelas pequenas e checklists verificáveis a texto repetido;
- manter links internos relativos.

## Atualização de snapshots

Só alterar snapshot histórico para corrigir erro factual do próprio snapshot ou
adicionar banner explícito de arquivamento. Novas entregas pertencem aos LIVE
docs.
