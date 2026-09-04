# Busca em cascata para decisores e contatos

> **Status: 🟡 Proposto**  
> **Prioridade: P0**  
> **Domínio: Contacts / Cost Control**

## Problema

Chamar todas as fontes para todos os leads é caro e desnecessário; parar cedo demais também reduz cobertura.

## Objetivo

Executar busca em cascata com early stopping baseado em confiança e acionabilidade.

## Mudança proposta

A cascata deve começar por fontes baratas/próprias e subir para providers pagos apenas quando necessário. A ordem pode variar por vertical e disponibilidade.

## Fluxo esperado

```text
1. Site/equipe da empresa
   ↓ se insuficiente
2. CNPJ/QSA
   ↓
3. People database
   ↓
4. Web/LinkedIn assistido
   ↓
5. Social
   ↓
6. Contato institucional roteável
   ↓
Email/contact verification
   ↓
Channel ranking
```

## Implementação sugerida

Definir threshold de `identity_confidence` e `actionable` para parar. Não parar só porque encontrou um email genérico se a vertical exige decisor técnico.

## Critérios de aceite

- Cada etapa registra motivo de execução/parada.
- Providers caros são chamados somente se necessário.
- Fallback institucional mantém lead acionável quando possível.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
