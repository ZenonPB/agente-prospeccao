# Inferência de padrão de email com verificação obrigatória

> **Status: 🟡 Proposto**  
> **Prioridade: P1**  
> **Domínio: Contacts / Email**

## Problema

Quando o nome do decisor é conhecido mas o email não, padrões corporativos podem ampliar cobertura; porém emails inferidos não podem ser tratados como fatos.

## Objetivo

Detectar padrão do domínio a partir de emails públicos/verificados, gerar candidatos e submetê-los a verificação antes de uso.

## Mudança proposta

Guardar origem, padrão aplicado, confiança e status de verificação. Nunca enviar automaticamente para um email apenas inferido sem passar pelas regras de verificação definidas.

## Contratos / modelo de dados

```json
{
  "email": "carlos.silva@empresa.com.br",
  "source": "pattern_inference",
  "confidence": 0.72,
  "verification_status": "verified"
}
```

## Critérios de aceite

- Email inferido carrega `source=pattern_inference`.
- Sem verificação positiva, não é marcado como contato confirmado.
- Padrão é associado ao domínio e possui confiança.

## Testes mínimos

- `firstname.lastname` inferido de exemplos conhecidos gera candidato correto.
- Email não verificável permanece unverified.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
