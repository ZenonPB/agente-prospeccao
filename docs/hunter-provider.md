# Hunter — configuração opt-in

O Hunter é uma fonte complementar de descoberta de pessoas. Ele não substitui
Receita/CNPJ nem o site oficial e permanece desligado por padrão.

## Plano gratuito

O plano Free do Hunter informa 50 créditos por mês e oferece acesso à API. O
Domain Search consome crédito por endereço encontrado; consulte os limites
atuais em [hunter.io/pricing](https://hunter.io/pricing).

## Ativar para uma organização

1. Crie uma chave em <https://hunter.io>.
2. No Prospect.ai, abra **Configurações → Chaves de Inteligência e Buscas**.
3. Salve a chave em **Contatos de decisores (Hunter)**.
4. Em **Uso Diário de Buscas e Inteligência Artificial**, defina uma quota
   positiva para **Busca de decisores (Hunter)**. Para o plano gratuito, use
   no máximo 50 como limite operacional inicial.
5. Execute o enriquecimento de um lead qualificado ou inicie uma campanha.

A chave sozinha não habilita o provider. A execução só registra Hunter quando:

```text
organization_secrets.HUNTER_API_KEY existe
e
organizations.api_quota.HUNTER_API_KEY > 0
```

Sem isso, o resultado é `disabled` e nenhum request externo é feito.

## Segurança e comportamento

- A chave fica criptografada em `organization_secrets` e nunca é devolvida.
- O request usa o header `X-API-KEY`, não a URL.
- HTTP 429 vira `quota_exceeded`; timeout e HTTP 5xx são retentáveis.
- Resposta válida sem pessoas vira `empty`.
- E-mails encontrados pelo Hunter não são automaticamente considerados
  verificados: o sistema ainda aplica verificação passiva de sintaxe, domínio
  descartável e MX pelo `EmailVerificationService`.
- O provider não dispara outreach e o LinkedIn continua sendo uma tarefa humana.

## Recomendação de uso do crédito

Use Hunter apenas depois de filtros baratos:

```text
pre-score alto
→ oportunidade relevante
→ Receita/site sem contato acionável
→ Domain Search Hunter
→ revisão de cargo e identidade
```

Não coloque a chave em `.env` versionado, logs, payloads de WebSocket ou
`raw_data`.