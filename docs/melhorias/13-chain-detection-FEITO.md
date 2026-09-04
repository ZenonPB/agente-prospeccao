# Detecção de franquias, redes e empresas independentes

> **Status: 🟡 Proposto**  
> **Prioridade: P1**  
> **Domínio: Discovery / Exclusion**

## Problema

Leads de rede, franquia ou enterprise podem aparecer fortes em Maps, mas ter baixa viabilidade para vendas locais de pequeno/médio ticket.

## Objetivo

Detectar cedo tipo de negócio e permitir que a vertical use isso como sinal de exclusão ou redução de score.

## Mudança proposta

Criar `ChainDetectionService`/signal provider usando nome semelhante entre unidades, domínio, telefone, CNPJ matriz/filial, seletor de lojas e outras evidências. Classificar `INDEPENDENT`, `SMALL_CHAIN`, `FRANCHISE`, `ENTERPRISE`, `UNKNOWN`.

## Critérios de aceite

- Classificação inclui evidência e confiança.
- UNKNOWN não é automaticamente penalizado.
- Landing Pages pode penalizar franquias sem afetar Engenharia se o perfil não quiser.

## Testes mínimos

- Mesmo domínio em muitas localidades eleva probabilidade de rede.
- Uma única unidade sem evidência suficiente permanece UNKNOWN/INDEPENDENT com confiança adequada.

## Riscos / considerações

- Não inferir franquia somente pelo nome.
- Evitar listas hardcoded como única fonte de verdade.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
