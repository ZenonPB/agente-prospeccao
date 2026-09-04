# Contato direto vs contato roteável

> **Status: 🟡 Proposto**  
> **Prioridade: P1**  
> **Domínio: Contacts / Telephony**

## Problema

Em indústria, encontrar celular pessoal do gerente pode ser raro, mas conhecer nome/cargo + telefone geral da empresa ainda permite chegar ao decisor.

## Objetivo

Modelar `DIRECT_CONTACT` e `ROUTABLE_CONTACT`. Um telefone institucional pode ser acionável quando existe `target_person` ou `target_department`.

## Mudança proposta

Não exibir PABX como telefone pessoal. O sistema deve orientar o vendedor a pedir transferência para a pessoa/departamento correto.

## Contratos / modelo de dados

```json
{
  "type": "company_switchboard",
  "target_person": "João Silva",
  "target_department": "Engenharia",
  "routable": true
}
```

## Critérios de aceite

- Contato roteável conta para actionable_contact_rate.
- Não é exibido como contato direto.
- Script de ligação pode usar nome/departamento quando conhecido.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
