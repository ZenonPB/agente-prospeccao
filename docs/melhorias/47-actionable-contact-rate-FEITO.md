# Actionable Contact Rate como métrica principal de contato

> **Status: 🟡 Proposto**  
> **Prioridade: P1**  
> **Domínio: BI / Contacts**

## Problema

Medir apenas `email_found_rate` penaliza canais válidos e não representa a capacidade real de chegar ao comprador.

## Objetivo

Adicionar `actionable_contact_rate`: percentual de leads para os quais existe um caminho plausível e permitido até o decisor correto.

## Mudança proposta

Um lead pode ser actionable por email direto verificado, perfil profissional do decisor, WhatsApp direto, telefone roteável com nome/departamento ou outro canal público/configurado. Contato institucional sem rota conhecida pode ter peso menor.

## Critérios de aceite

- Métrica distingue direct, routable e institutional.
- É calculável por vertical/campanha/provider.
- Não conta contatos inválidos/não verificados como direct.

## Testes mínimos

- Lead com nome do gerente + PABX roteável é actionable.
- Email inválido não conta como contato direto.

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
