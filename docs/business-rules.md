# Regras de Negócio

## Funil de Status dos Leads
NOVO
→ ANALISADO      (após enriquecimento técnico)
→ QUALIFICADO    (score >= 60)
→ DESQUALIFICADO (score < 60 ou sem site)
→ CONTATADO      (1ª mensagem enviada)
→ RESPONDIDO     (lead respondeu)
→ REUNIAO_MARCADA
→ PERDIDO

## Critérios de Scoring (0-100)

| Faixa | Significado |
|---|---|
| 80-100 | Crítico: .env exposto, .git exposto, sem HTTPS |
| 60-79 | Grave: múltiplos problemas de segurança ou performance |
| 40-59 | Moderado: headers ausentes, WordPress detectado |
| 20-39 | Leve: site funcional com melhorias possíveis |
| 0-19 | Site bem configurado, baixa oportunidade |

**Score >= 60 → QUALIFICADO → entra na fila de outreach**
**Score < 60 → ANALISADO → não entra no outreach automaticamente**

## Confiança de Contato (contact_confidence)

| Faixa | Significado |
|---|---|
| 90-100 | Dono/CEO confirmado via Hunter ou CNPJ |
| 70-89 | Cargo relevante encontrado (diretor, sócio) |
| 50-69 | E-mail genérico de empresa (contato@, comercial@) |
| 0-49 | Fonte incerta ou inferida |

## Regras do Pipeline

- Lead sem website entra como NOVO mas não passa pelo enriquecimento técnico
- Lead sem contato com confidence >= 50 não entra no outreach automático
- Leads PERDIDO voltam para a fila após 90 dias
- Scoring é recalculado quando novos dados de enriquecimento chegam
- Mensagem de outreach nunca é genérica — deve referenciar dados reais do lead

## Limites Legais (Lei 12.737/2012)

A plataforma jamais:
- Tenta explorar vulnerabilidades
- Executa injeções de qualquer tipo
- Testa autenticação
- Realiza qualquer ação não-passiva

Toda análise se restringe a informações publicamente acessíveis.

## Limites de Uso (API Keys)

As chaves de API compartilham um pool de créditos limitados.

- Google Search: 100 consultas/mês por chave
- Hunter.io: 1.000 créditos/mês por chave
- WHOIS: 50 consultas/mês por chave
- CNPJ: 20 consultas/mês por chave

Se uma chave exceder seu limite, todas as operações usarão fallback (cache local ou skipping) até o próximo ciclo.

## Sequência de Follow-up

| Mensagem | Quando | Objetivo |
|---|---|---|
| 1ª mensagem | Dia 0 | Apresentação + problema + CTA reunião |
| Follow-up 1 | Dia 3 sem resposta | Reforço leve |
| Follow-up 2 | Dia 7 sem resposta | Última tentativa |
| Encerramento | Dia 14 sem resposta | Ciclo encerrado, lead volta em 90 dias |