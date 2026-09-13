# Feedback humano e loop de aprendizado

> **LIVE · atualizado em 2026-09-13.** Feedback melhora análise e priorização,
> mas nunca altera produção sem o fluxo de Controlled Learning.

## Dois tipos de feedback

### Utilidade do lead

`LeadUsefulnessFeedback` responde à pergunta operacional: **este lead serve para
o time?**

- 👍 útil;
- 👎 não útil;
- motivo negativo fechado (empresa errada, sem necessidade, contato errado,
  fora do porte/região, já tem fornecedor, dados incorretos, outro);
- detalhe opcional;
- org-scoped;
- idempotente por lead + usuário;
- evento auditável na trilha.

### Correção de score

`ScoringFeedback` responde: **a pontuação da IA ficou alta ou baixa demais?**

- score original;
- score sugerido;
- direção da correção;
- justificativa humana;
- estado do feedback;
- aplicação explícita quando permitida;
- trilha auditável.

Os dois conceitos não devem ser fundidos: um lead pode ter score razoável e ser
inútil por um motivo operacional, ou ser útil apesar de um score mal calibrado.

## Outcome real

`CommercialOutcomeRow` é a evidência mais forte do ciclo comercial quando está
atribuído à `LeadOpportunity` correta. Comparações devem agrupar por:

- workspace;
- oferta;
- versão da oferta;
- segmento/coorte quando aplicável;
- período;
- provider/origem quando a pergunta for qualidade de aquisição.

## Fluxo de uso

```text
feedback útil/não útil
score feedback
outcomes reais
      ↓
analytics / diagnóstico / coaching
      ↓
hipótese de alteração do OfferProfile
      ↓
comparação + tamanho de amostra
      ↓
proposta versionada
      ↓
aprovação humana
      ↓
publicação explícita / rollback
```

## Coaching

O produto de coaching ainda é parcial. A próxima camada deve transformar dados
existentes em orientação explicável ao vendedor, por exemplo:

- leads bons sem próxima ação;
- oportunidades quentes paradas;
- taxa de feedback negativo por motivo;
- gargalos por estágio;
- follow-ups vencidos;
- diferenças entre previsão e outcome;
- segmentos/providers com baixa utilidade.

Não usar linguagem prescritiva baseada em amostra insuficiente; sempre mostrar
por que a recomendação foi gerada.

## Isolamento e privacidade

Nenhum feedback de A pode calibrar B. Toda agregação deve começar por
`organization_id`. Feedback, outcomes e publicação de OfferProfile são privados
ao workspace salvo decisão futura explícita para padrões globais anonimizados.

## Gate antes da calibração final

A calibração final depende do PR #172: o pipeline precisa consumir o
OfferProfile publicado no workspace inteiro. Depois disso, Filter Context/BI e
UAT devem provar que feedback/outcomes usados na análise pertencem à mesma
oferta, versão e organização.
