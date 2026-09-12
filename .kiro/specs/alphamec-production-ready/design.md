# Design Document

## Overview

Esta spec não adiciona capacidade nova ao produto. Ela fecha seis invariantes
quebradas, corrige quatro defeitos de contrato entre `apps/web` e `services/api`,
executa um UAT real e completa o BI mínimo de operação reaproveitando o
`AnalyticsService` existente.

O design segue quatro princípios, nesta ordem de precedência:

1. **Falha fechada.** Onde hoje um valor nulo ou ausente permite a operação, a
   operação passa a ser recusada. Isso vale para `Job.organization_id`, para a
   resolução de organização no inbound e para `Lead.lost_reason` em `PERDIDO`.
2. **Garantia em duas camadas.** Toda invariante de dado recebe validação na
   aplicação *e* garantia no banco. Quando a garantia de banco depende de dado
   legado, ela é introduzida em forma não-validante e a promoção fica gateada por
   contagem real de violações.
3. **Aditividade.** Nenhuma coluna é removida, nenhuma migration existente é
   editada. Toda mudança de schema é uma revisão nova.
4. **Reúso antes de criação.** Nenhum endpoint de BI paralelo, nenhum mecanismo
   de dry-run novo, nenhuma abstração de provider nova. O que já existe é
   estendido.

O trabalho é executado na branch `feat/alphamec-production-ready`, originada de
`main @ 27d2925`.

### Mapa das mudanças

```
Bloco 1 — invariantes                        Bloco 2 — Golden Path
─────────────────────────────                ─────────────────────────
webhooks.py        → token por org           campanhas/nova   → ?start=true
inbound_email_service → organization_id      campanhas/[id]   → guard de disparo único
pipeline.py (WS)   → fail-closed             lead-list.tsx    → assigned='me'
cadence_service    → estado terminal         lead-list.tsx    → mark-lost em lote
leads.py           → transição única         lib/safe-redirect.ts (novo)
models.py + 4 migrations                     estados de provider na UI

Bloco 3 — UAT real                           Bloco 4 — BI mínimo
─────────────────────────────                ─────────────────────────
docs/uat-runbook.md (execução)               analytics_service.funnel → 8 etapas
Outreach_Assistido (dry-run existente)       + offer_key, + canal, + amostra
ficha de 9 itens × ≥10 oportunidades         /relatorios → aba Funil de operação
decisão do provider de eventos               export da visão filtrada
```

---

## Architecture

### Bloco 1 — Segurança e invariantes

#### 1.1 Tenant determinístico no inbound (Requisitos 1, 2)

##### Problema

`webhooks.py` valida apenas `X-Webhook-Secret == settings.EMAIL_WEBHOOK_SECRET`,
um segredo global. Nenhuma organização entra no payload nem no header.
`process_inbound_email` então procura o lead com
`or_(Lead.email == sender, Contact.email == sender)` mais
`Lead.organization_id.isnot(None)` e `.first()` — isto é, em qualquer
organização, pegando o primeiro resultado que o planner devolver. Um lead de
outro cliente pode receber a resposta.

##### Solução: token de inbound por organização no path

Nova rota:

```
POST /api/webhooks/email/inbound/{token}
POST /api/webhooks/import/{token}
```

`Organization` recebe a coluna aditiva `inbound_token_hash` (String, nullable,
unique index) que guarda `sha256(token)`. O token em claro nunca é persistido: é
exibido uma vez na geração e o operador o cola na configuração do provedor.

O path foi escolhido em vez de header extra porque os provedores de inbound
(Postmark, SendGrid inbound parse) configuram somente a URL de destino — não
permitem header customizado por hook. Reapontar a URL do provedor é mudança de
configuração operacional, não mudança destrutiva.

```python
# services/api/src/services/inbound_token_service.py (novo)
import hashlib
import secrets

def hash_inbound_token(token: str) -> str:
    """Hash determinístico do token — permite lookup indexado por igualdade."""
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()

def generate_inbound_token() -> tuple[str, str]:
    """Retorna (token em claro, hash). O claro só é exibido na geração."""
    token = secrets.token_urlsafe(32)
    return token, hash_inbound_token(token)

def resolve_organization_by_token(db: Session, token: str) -> Organization | None:
    """Resolve exatamente uma org antes de qualquer consulta de domínio."""
    if not token or len(token) > 128:
        return None
    return (
        db.query(Organization)
        .filter(Organization.inbound_token_hash == hash_inbound_token(token))
        .first()
    )
```

O lookup é por igualdade sobre índice único: determinístico e resolve no máximo
uma organização. A comparação do hash é feita no banco sobre valor derivado, não
sobre o segredo, o que dispensa comparação em tempo constante na aplicação.

##### Rota legada

`POST /api/webhooks/email/inbound` (sem token) é **mantida** e passa a exigir
`X-Webhook-Secret` (segredo global) **e** `X-Organization-Id`. Fica marcada como
depreciada na docstring e no OpenAPI. Sem organização resolvível: `401` e zero
persistência. Mesmo tratamento para `/webhooks/import`.

```python
@router.post("/email/inbound/{token}")
def email_inbound_by_token(token: str, payload: InboundEmailPayload,
                           db: Session = Depends(get_db)):
    org = resolve_organization_by_token(db, token)
    if org is None:
        # Recusa idêntica para token inexistente e token malformado.
        raise HTTPException(status_code=401, detail="Credencial de inbound inválida")
    result = process_inbound_email(
        db,
        organization_id=org.id,
        from_email=payload.from_email,
        subject=payload.subject or "",
        body=payload.body or "",
    )
    return {"ok": True, **result}
```

Nota sobre o `404` atual: hoje a rota responde `404` quando
`EMAIL_WEBHOOK_SECRET` não está configurado. A rota nova não depende do segredo
global — depende do token da organização — e responde `401` em qualquer falha de
credencial, sem revelar se o token existe.

##### Escrita confinada (Requisito 2)

`process_inbound_email` ganha parâmetro **obrigatório** `organization_id` e o
aplica no filtro do lead:

```python
def process_inbound_email(
    db: Session,
    organization_id: uuid.UUID,   # obrigatório — sem default
    from_email: str,
    subject: str,
    body: str,
) -> Dict[str, bool]:
    sender = (from_email or "").strip().lower()
    if not sender:
        return {"matched": False, "stop_requested": False}

    lead = (
        db.query(Lead)
        .outerjoin(Contact, Contact.lead_id == Lead.id)
        .filter(
            or_(Lead.email == sender, Contact.email == sender),
            Lead.organization_id == organization_id,   # antes: .isnot(None)
        )
        .first()
    )
    if lead is None:
        logger.info("Inbound sem lead correspondente na org %s", organization_id)
        return {"matched": False, "stop_requested": False}

    # Guarda defensiva: nenhuma escrita se a org divergir do lead resolvido.
    if str(lead.organization_id) != str(organization_id):
        logger.error("Divergência de org no inbound — operação rejeitada")
        db.rollback()
        return {"matched": False, "stop_requested": False}
    ...
```

Todas as escritas do serviço (`opt_out`, `FollowUp` SKIPPED/CANCELLED, `Message`
espelho com `is_response=True` herdando `variant`, `LeadActivity`, notificação
via `create_lead_responded_notification`) já derivam de `lead`. Com o lead
confinado, elas ficam confinadas por construção. A guarda defensiva existe para
que uma refatoração futura que perca o filtro falhe fechada em vez de vazar.

Ausência de correspondência mantém o comportamento atual: retorno
`matched=False` **antes** de qualquer `db.add`, sem `commit`. Zero registros.

##### Contrato de resposta

| Situação | Status | Corpo | Persistência |
|---|---|---|---|
| Token válido, lead encontrado | 200 | `{ok: true, matched: true, stop_requested: bool}` | trilha + mensagens do lead |
| Token válido, sem lead na org | 200 | `{ok: true, matched: false, stop_requested: false}` | zero |
| Token inválido / ausente | 401 | `{detail: "Credencial de inbound inválida"}` | zero |
| Rota legada sem `X-Organization-Id` | 401 | idem | zero |

#### 1.2 Falha fechada em job e WebSocket (Requisito 3)

##### Problema

`pipeline.py` autoriza a conexão quando
`job is None or (job.organization_id and str(job.organization_id) != str(org.id))`
é falso. A conjunção com `job.organization_id` faz job órfão (`organization_id`
nulo) passar pela guarda.

##### Solução

```python
job = db.query(Job).filter(Job.id == job_id).first()
if (
    job is None
    or job.organization_id is None
    or str(job.organization_id) != str(org.id)
):
    # Recusa idêntica para inexistente, órfão e de outra org — não revela
    # existência do job.
    await websocket.close(code=403, reason="Acesso negado a este job")
    return
```

O código e a razão de recusa são literalmente os mesmos nos três casos, o que
sustenta a indistinguibilidade exigida pelo Requisito 3.3.

##### Auditoria dos pontos de criação de Job

Levantamento feito no código:

| Arquivo | Linha aprox. | `organization_id` preenchido |
|---|---|---|
| `routes/pipeline.py` | 95 | sim (`_org.id`) |
| `routes/campaigns.py` (reanálise) | 515 | sim (`_org.id`) |
| `routes/campaigns.py` (coleta CNAE) | 801 | sim (`_org.id`) |
| `routes/campaigns.py` (coleta PNCP) | 848 | sim (`_org.id`) |

Nenhum caminho de criação em produção deixa o campo nulo. A garantia de
aplicação para o Requisito 3.4 é, portanto, um teste por rota que assevera
`organization_id is not None`, mais a guarda fail-closed que torna qualquer
regressão inofensiva.

##### Rotas HTTP de estado de job (Requisito 3.5)

`GET /api/pipeline/jobs` já filtra `Job.organization_id == _org.id`. Com a
coluna nula recusada pelo mesmo predicado de igualdade, job órfão também
desaparece da listagem. Nenhuma mudança necessária; o comportamento entra na
suíte como teste de regressão.

##### `Job.organization_id` NOT NULL — proposto e gateado

A migration que torna a coluna `NOT NULL` é **proposta, não incondicional**.
Antes de aplicá-la:

```sql
SELECT count(*) FROM jobs WHERE organization_id IS NULL;
```

- resultado `0` → aplicar a migration `m4`;
- resultado `> 0` → registrar **Ponto_De_Parada** com a contagem e aguardar
  decisão humana. Não há backfill adivinhado: derivar a organização a partir de
  `campaign_id` seria uma inferência sobre dado de produção.

A garantia obrigatória desta branch é a de aplicação. A de banco é condicional.

#### 1.3 Estados terminais fora da cadência (Requisito 4)

##### Problema

`send_step` checa, nesta ordem: `status == SENT`, `lead.opt_out`, conteúdo,
destinatário, `EmailSuppression`. Nenhuma checagem de `Lead.status`. `run_due`
filtra `PENDING & scheduled_at <= now & Lead.opt_out.is_(False) &
Organization.auto_send_email.is_(True)` — também sem estado terminal. E nem
`mark-lost` nem `mark-disqualified` cancelam `FollowUp` pendente (só
`mark-responded` e o inbound fazem isso).

##### Solução em três pontos

**(a) Guarda em `send_step`**, imediatamente após o early-return de `SENT` e
antes de qualquer resolução de destinatário ou envio:

```python
TERMINAL_STATUSES = (LeadStatus.PERDIDO, LeadStatus.DESQUALIFICADO)

def send_step(db, follow_up, user_id=None) -> bool:
    if follow_up.status == FollowUpStatus.SENT:
        return True

    lead = follow_up.lead or db.query(Lead).filter(Lead.id == follow_up.lead_id).first()
    if lead and lead.status in TERMINAL_STATUSES:
        follow_up.status = FollowUpStatus.SKIPPED
        log_event(
            "cadence_skipped",
            lead_id=str(follow_up.lead_id),
            organization_id=str(lead.organization_id) if lead.organization_id else None,
            reason="terminal_status",
            status=lead.status.value,
            step=follow_up.step.value,
        )
        db.commit()
        return False

    if lead and lead.opt_out:
        ...
```

A posição importa: antes da guarda, nenhuma `Message` é criada e nenhum
`send_email` é chamado. `SKIPPED` (não `CANCELLED`) porque o bloqueio é de
elegibilidade do lead, alinhado ao tratamento de `opt_out`.

**(b) Filtro em `run_due`**, com operadores SQLAlchemy:

```python
due = (
    db.query(FollowUp)
    .join(Lead, FollowUp.lead_id == Lead.id)
    .join(Organization, Lead.organization_id == Organization.id)
    .filter(
        (FollowUp.status == FollowUpStatus.PENDING)
        & (FollowUp.scheduled_at <= now_utc)
        & (Lead.opt_out.is_(False))
        & (~Lead.status.in_(TERMINAL_STATUSES))
        & (Organization.auto_send_email.is_(True))
    )
    .order_by(FollowUp.scheduled_at.asc())
    .all()
)
```

`&` e `~`, nunca `and`/`not` do Python.

**(c) Função única de cancelamento na transição terminal**, em
`cadence_service`, ao lado de `mark_opt_out` (que já implementa o mesmo padrão
para opt-out):

```python
def cancel_pending_for_terminal(db: Session, lead: Lead, reason: str) -> int:
    """Encerra as etapas pendentes de um lead que entrou em estado terminal.

    Ponto único: qualquer caminho que grave PERDIDO/DESQUALIFICADO chama isto,
    sem commit próprio — a transação é do chamador.
    """
    pendentes = db.query(FollowUp).filter(
        FollowUp.lead_id == lead.id,
        FollowUp.status == FollowUpStatus.PENDING,
    ).all()
    for fu in pendentes:
        fu.status = FollowUpStatus.CANCELLED
    if pendentes:
        logger.info("Cadência encerrada para lead %s (%s): %d etapa(s)",
                    lead.id, reason, len(pendentes))
    return len(pendentes)
```

Chamadores: a função de transição de status descrita em 1.4 (que atende
`PATCH /status`, `mark-lost` e `mark-disqualified`). Nenhum caminho duplica a
lógica.

#### 1.4 Motivo obrigatório em PERDIDO (Requisito 5) e lote sem bypass (Requisito 6)

##### Problema

`UpdateLeadStatusRequest.lost_reason` é `Optional[LostReason] = None`, e
`PATCH /{lead_id}/status` grava `lead.status = body.status` sempre, gravando o
motivo apenas `if body.lost_reason is not None`. `MarkLostRequest.lost_reason` é
obrigatório, mas o frontend usa `updateStatus` (o PATCH genérico) na ação em
lote `PERDIDO` — o caminho fraco.

##### Camada (a) — validação de schema

```python
class UpdateLeadStatusRequest(BaseModel):
    status: LeadStatus
    lost_reason: Optional[LostReason] = None

    @model_validator(mode="after")
    def _exigir_motivo_em_perdido(self):
        if self.status == LeadStatus.PERDIDO and self.lost_reason is None:
            raise ValueError("lost_reason é obrigatório quando status é PERDIDO")
        return self
```

O `ValueError` em `model_validator` produz `422` pelo handler de validação do
FastAPI, e a requisição é rejeitada antes de qualquer acesso ao banco — o
`Lead.status` anterior permanece intacto sem esforço adicional.

##### Camada (b) — fonte de verdade de domínio

Nova função em `services/api/src/services/lead_status_service.py`:

```python
def transition_lead_status(
    db: Session,
    lead: Lead,
    new_status: LeadStatus,
    *,
    user_id: str | None,
    lost_reason: LostReason | None = None,
    disqualification_reason: str | None = None,
) -> LeadActivity:
    """Único ponto de gravação de Lead.status.

    Garante, na mesma transação: motivo obrigatório em PERDIDO, trilha
    correspondente ao outcome e encerramento da cadência em estado terminal.
    PERDIDO e DESQUALIFICADO seguem trilhas e outcomes distintos.
    """
    if new_status == LeadStatus.PERDIDO and lost_reason is None:
        raise ValueError("PERDIDO exige lost_reason")

    previous = lead.status
    lead.status = new_status

    if new_status == LeadStatus.PERDIDO:
        lead.lost_reason = lost_reason
        activity = log_activity(
            db, lead, action=LeadActivityAction.LOST, user_id=user_id,
            status_from=previous, status_to=new_status,
            detail=f"Lead perdido — motivo: {lost_reason.value}",
        )
    elif new_status == LeadStatus.DESQUALIFICADO:
        detail = "Lead desqualificado"
        if disqualification_reason:
            detail += f" — motivo: {disqualification_reason.strip()}"
        activity = log_activity(
            db, lead, action=LeadActivityAction.STATUS_CHANGED, user_id=user_id,
            status_from=previous, status_to=new_status, detail=detail,
        )
    else:
        activity = log_status_change(
            db, lead, user_id=user_id, status_to=new_status, status_from=previous,
            detail=f"{previous.value if previous else '?'} → {new_status.value}",
        )

    if new_status in TERMINAL_STATUSES:
        cancel_pending_for_terminal(db, lead, reason=new_status.value)

    db.flush()
    return activity
```

Consumidores: `PATCH /{lead_id}/status`, `POST /{lead_id}/mark-lost`,
`POST /{lead_id}/mark-disqualified` e qualquer caminho futuro. O registro de
outcome comercial (`_record_commercial_outcome`) continua no chamador, com a
mesma chave de evento derivada da atividade (`activity:{id}` no PATCH,
`mark-lost:{lead_id}` no mark-lost) — o que preserva a idempotência já existente
de outcome.

`PERDIDO` e `DESQUALIFICADO` continuam separados: ações de trilha diferentes
(`LOST` vs `STATUS_CHANGED`), outcome comercial só em `PERDIDO`, e
`lost_reason` gravado só em `PERDIDO`. Nenhum caminho converte um no outro.

##### Camada (c) — garantia de banco

```sql
ALTER TABLE leads
  ADD CONSTRAINT ck_leads_lost_reason_required
  CHECK (status <> 'PERDIDO' OR lost_reason IS NOT NULL)
  NOT VALID;
```

`NOT VALID` porque linhas legadas podem violar. A promoção
(`ALTER TABLE leads VALIDATE CONSTRAINT ...`) fica condicionada a:

```sql
SELECT count(*) FROM leads WHERE status = 'PERDIDO' AND lost_reason IS NULL;
```

Zero → validar. Maior que zero → **Ponto_De_Parada** com a contagem. `NOT VALID`
já bloqueia toda escrita nova, que é o que a invariante exige daqui para frente.

##### Ação em lote no Painel_Oportunidades (Requisito 6)

`lead-list.tsx` hoje faz `bulkStatus('PERDIDO')` → `updateStatus.mutate`. Passa
a:

```tsx
// PERDIDO em lote exige motivo — usa o caminho que o valida (mark-lost),
// nunca o PATCH genérico de status.
const bulkStatus = (status: string) => {
  if (status === 'PERDIDO') {
    setLostReasonDialogOpen(true);   // resolve antes de qualquer requisição
    return;
  }
  runBulk((id) => updateStatus.mutate({ id, status }, { ... }));
};

const confirmBulkLost = (reason: LostReasonOption) => {
  runBulk((id) => markLost.mutate({ id, lostReason: reason }, { ... }));
};
```

`useMarkLost` e `LOST_REASON_OPTIONS` já existem em `hooks/use-api.ts`; a API
`markLost` já existe em `lib/api.ts`. O diálogo reaproveita o seletor de motivo
do `OutcomeDialog`. Cancelar fecha sem emitir requisição. `runBulk` já agrega
sucessos e falhas — o resumo passa a ser exibido com as duas contagens, e o
toast de sucesso só sai depois da resposta da API.

#### 1.5 Conversão única sob concorrência (Requisito 7)

##### Problema

`register_conversion` faz check-then-insert: `find_duplicate_conversion` consulta
e, se não achar, `db.add(Conversion(...)); db.flush()`. Sob duplo clique, as duas
transações leem "não existe" e ambas inserem. `Conversion.__table_args__` só tem
`Index("ix_conversions_lead_id", "lead_id")` — nenhuma constraint única.

Agrava: o filtro por `lead_opportunity_id` em `find_duplicate_conversion` é
condicional (`if lead_opportunity_id:`), o que torna o check **mais estreito** que
a invariante do Requisito 7 (unicidade por `lead_id` + `offer_key`).

##### Solução: índice único de expressão

```sql
CREATE UNIQUE INDEX uq_conversions_lead_offer
  ON conversions (lead_id, coalesce(offer_key, 'unknown'));
```

Expressão, não índice único simples, porque `offer_key` é `String(64) nullable` e
NULLs são distintos entre si em unique comum — duas conversões com `offer_key`
nulo passariam. O sentinel `'unknown'` é o mesmo que a rota já usa
(`if body.offer_key != "unknown":`), então app e banco concordam sobre o
significado de "sem oferta".

No modelo:

```python
class Conversion(Base):
    __tablename__ = "conversions"
    __table_args__ = (
        Index("ix_conversions_lead_id", "lead_id"),
        Index(
            "uq_conversions_lead_offer",
            "lead_id",
            func.coalesce(text("offer_key"), text("'unknown'")),
            unique=True,
        ),
    )
```

##### Alinhamento do check com a constraint

```python
def find_duplicate_conversion(db, lead_id, offer_key, lead_opportunity_id=None):
    """Localiza conversão já registrada para o mesmo lead+oferta.

    O escopo é lead+oferta, igual ao índice único: a oportunidade não estreita
    a busca, senão o check aceitaria o que o banco rejeita.
    """
    return (
        db.query(Conversion)
        .filter(
            Conversion.lead_id == lead_id,
            func.coalesce(Conversion.offer_key, "unknown") == (offer_key or "unknown"),
        )
        .order_by(Conversion.converted_at.desc())
        .first()
    )
```

O parâmetro `lead_opportunity_id` é mantido na assinatura para não quebrar os
chamadores existentes, mas deixa de participar do filtro.

##### Tratamento da violação

```python
try:
    db.add(conversion)
    db.flush()
except IntegrityError:
    db.rollback()
    logger.info("Conversão duplicada para lead %s / oferta %s", lead.id, body.offer_key)
    # Mensagem de domínio: nenhum nome de constraint, de tabela ou texto do banco.
    raise HTTPException(
        status_code=409,
        detail="Esta venda já foi registrada para este lead e esta oferta",
    )
```

O `except` captura `IntegrityError` genérico (não inspeciona a mensagem do
driver) e a resposta é uma frase de domínio fixa. O detalhe técnico vai para o
log da aplicação, não para o corpo HTTP.

Duplicatas preexistentes bloqueiam a criação do índice. Contagem prévia:

```sql
SELECT lead_id, coalesce(offer_key,'unknown') AS ofr, count(*)
FROM conversions GROUP BY 1,2 HAVING count(*) > 1;
```

Resultado vazio → criar o índice. Resultado não vazio → **Ponto_De_Parada** com
as linhas em conflito. Nenhuma linha é apagada sem aprovação humana: uma
conversão duplicada pode ser um segundo contrato registrado errado, e a decisão é
comercial.

#### 1.6 Migrations (Requisito 8)

Quatro revisões novas em `services/workers/alembic/versions/`, encadeadas, nenhuma
edição de migration existente:

| ID | Conteúdo | Tipo | Gate |
|---|---|---|---|
| `m1` | `organizations.inbound_token_hash` (String nullable) + unique index | aditiva | nenhum |
| `m2` | `CHECK ck_leads_lost_reason_required` como `NOT VALID` | aditiva | `VALIDATE` só com zero violações |
| `m3` | `CREATE UNIQUE INDEX uq_conversions_lead_offer` sobre expressão | aditiva | zero duplicatas preexistentes |
| `m4` | `jobs.organization_id SET NOT NULL` | restritiva | **só se** `count(NULL) = 0` |

`alembic heads` deve reportar exatamente uma cabeça após o encadeamento; isso
entra nos gates. Nenhuma coluna é removida; nenhuma tabela é dropada. Se qualquer
correção passar a exigir remoção, o trabalho para com **Ponto_De_Parada**.

---

### Bloco 2 — Golden Path AlphaMec

#### 2.1 "Criar e iniciar coleta" (Requisito 9)

`campanhas/nova/page.tsx` navega para `/campanhas/${campaign.id}` quando
`startCollection` é verdadeiro. `campanhas/[id]/page.tsx` lê
`searchParams.get('start') === 'true'` e só então passa `autoStart`. O parâmetro
nunca é enviado, então a coleta nunca inicia.

```tsx
if (startCollection) {
  router.push(`/campanhas/${campaign.id}?start=true`);
} else {
  router.push('/campanhas');
}
```

Sem inventar contrato novo: `?start=true` é exatamente o que a página consome.

O disparo único (Requisito 9.2) é garantido por guarda de ref no componente que
recebe `autoStart`, porque React 19 em StrictMode monta o efeito duas vezes em
desenvolvimento e um re-render por mudança de dados não deve redisparar:

```tsx
const disparado = useRef(false);
useEffect(() => {
  if (!autoStart || disparado.current) return;
  disparado.current = true;
  iniciarColeta();
}, [autoStart, iniciarColeta]);
```

O progresso já é exibido pelo componente de pipeline via WebSocket; falha já tem
caminho de erro. Ambos entram na verificação de navegador, não em código novo.

#### 2.2 Contrato do filtro Meus Leads (Requisito 10)

`GET /api/leads` valida `assigned` com `pattern="^(me|none|any)$"`.
`lead-list.tsx` envia `assigned: myLeadsOnly && currentUserId ? currentUserId : undefined`
— um UUID, que a rota rejeita.

**A correção é no frontend**, não na API:

```tsx
// A API resolve 'me' no servidor, dentro da organização ativa.
assigned: myLeadsOnly ? 'me' : undefined,
```

Justificativa: `me` já é resolvido no servidor a partir do usuário autenticado e
da organização ativa. Aceitar UUID arbitrário exigiria uma regra de permissão
nova (quem pode ver a carteira de terceiros), criando superfície de autorização
que esta spec não precisa e não quer abrir. `consultant_id` já existe para o caso
de gestão, com as regras dele.

O teste de contrato compara o valor emitido pelo componente com o `pattern`
declarado na rota — um lado não pode mudar sem quebrar o teste.

#### 2.3 Redirecionamento pós-login seguro (Requisito 11)

`login/page.tsx` sempre faz `router.push('/dashboard')`.
`aceitar-convite/page.tsx` monta
`callbackUrl = encodeURIComponent('/aceitar-convite?token=' + token)` e passa em
`/login?callbackUrl=...`, que é descartado.

Helper único, novo, em `apps/web/src/lib/safe-redirect.ts`:

```ts
const FALLBACK = '/dashboard';

/**
 * Resolve um callbackUrl para um caminho interno seguro.
 * Qualquer valor que não seja caminho relativo da própria aplicação
 * degrada para o fallback — nunca redireciona para fora.
 */
export function resolveSafeCallbackUrl(raw: string | null | undefined,
                                       fallback: string = FALLBACK): string {
  if (!raw) return fallback;

  let valor = raw;
  // Decodifica até estabilizar: bloqueia %2F%2Fhost, %5C, %09, etc.
  for (let i = 0; i < 3; i++) {
    let proximo: string;
    try {
      proximo = decodeURIComponent(valor);
    } catch {
      return fallback;      // percent-encoding malformado
    }
    if (proximo === valor) break;
    valor = proximo;
  }

  // eslint-disable-next-line no-control-regex
  if (/[\u0000-\u001F\u007F]/.test(valor)) return fallback;  // caracteres de controle
  if (valor.includes('\\')) return fallback;                 // /\host, \\host
  if (!valor.startsWith('/')) return fallback;               // relativo ou absoluto externo
  if (valor.startsWith('//')) return fallback;               // protocol-relative
  if (/^\/+[\\]/.test(valor)) return fallback;               // /\host

  return valor;
}
```

Rejeita, por construção: URL absoluta com qualquer esquema (`http:`, `https:`,
`javascript:`, `data:` — nenhuma começa com `/`), `//host`, `/\host`, qualquer
backslash, ausência de `/` inicial, caracteres de controle e as variantes
percent-encoded de tudo isso.

Consumidores:

```tsx
// login/page.tsx
const destino = resolveSafeCallbackUrl(searchParams.get('callbackUrl'));
router.push(destino);
```

O mesmo helper é usado no aceite de convite ao construir e ao consumir o
`callbackUrl`. A divergência de e-mail entre sessão e convite (Requisito 11.5) já
tem tela e ação "Trocar de conta" em `aceitar-convite/page.tsx`; entra na
verificação de navegador.

#### 2.4 Vazio distinto de falha de provider (Requisito 12)

Os cinco estados (`FOUND`, `EMPTY`, `FAILED`, `DISABLED`, `QUOTA_EXCEEDED`) já
existem no backend e devem permanecer distintos (Requisito 22.4). O problema é de
apresentação. O design centraliza o mapeamento em uma função pura, o que também a
torna testável por propriedade:

```ts
export type ProviderState = 'FOUND' | 'EMPTY' | 'FAILED' | 'DISABLED' | 'QUOTA_EXCEEDED';

export type Apresentacao =
  | { tipo: 'resultados' }
  | { tipo: 'sem-correspondencia' }                                  // todos EMPTY
  | { tipo: 'parcial'; providersComFalha: string[] }                 // misto
  | { tipo: 'falha'; providersComFalha: string[]; estados: ProviderState[] };

/**
 * Ausência de correspondência só é anunciada quando TODOS os providers
 * consultados retornaram EMPTY. Falha, desabilitado e quota nunca são
 * apresentados como "nada encontrado".
 */
export function apresentarResultado(
  providers: { nome: string; estado: ProviderState }[],
): Apresentacao { /* ... */ }
```

Regras de UI derivadas:

- **loading / error / retry por região**, não por página: cada bloco de dados
  (lista, evidência, decisor, contato) tem seu próprio estado.
- **`EMPTY`** → "nenhuma correspondência para estes critérios".
- **`FAILED` / `DISABLED` / `QUOTA_EXCEEDED`** → estado específico do provider,
  nomeando-o, com ação de nova tentativa quando aplicável. Nunca a mensagem de
  ausência.
- **resultado parcial** → banner declarando incompletude e qual provider falhou.
- **inferência** → todo valor derivado de heurística ou LLM recebe marcação de
  inferência (badge + tooltip com a origem), distinta de dado com fonte
  verificada. Isso alimenta diretamente o item de evidência da ficha de UAT
  (Requisito 14.4).

Componentes: shadcn/ui sobre `@base-ui/react`, usando a prop `render` — nunca
`asChild`, conforme `apps/web/AGENTS.md`.

---

### Bloco 3 — UAT real

#### 3.1 Ambiente e Outreach_Assistido (Requisito 13)

O UAT executa `docs/uat-runbook.md` contra Postgres real, API real (`uvicorn` em
`services/api`), web real (`apps/web`), Google Places API e Groq. Leitura de
código não conta como UAT.

**Outreach_Assistido usa o dry-run que já existe.** `email_service.send_email`,
quando `_is_smtp_configured()` é falso e `ENVIRONMENT != "production"`, retorna
`EmailSendResult(sent=True, error="dry-run")` e apenas loga destinatário e
assunto. Nada sai para a rede. A configuração da sessão é:

| Controle | Valor | Efeito |
|---|---|---|
| `ENVIRONMENT` | diferente de `production` | habilita o dry-run existente |
| SMTP | não configurado | `send_email` só loga destinatário/assunto |
| `Organization.auto_send_email` | `False` | `run_due` não seleciona nada da org |

Nenhum mecanismo novo é criado. A dupla proteção (dry-run + flag) é intencional:
o dry-run impede a saída da mensagem, a flag impede o disparo sem ação humana.

Antes de abrir a sessão, os três controles são conferidos e registrados. Cada
item do roteiro recebe resultado observado e evidência; item não executável é
registrado como **não executado com a causa**, jamais como aprovado.

#### 3.2 Ficha de avaliação por oportunidade (Requisito 14)

Ficha com os nove itens do Requisito 14, aplicada a **no mínimo dez**
oportunidades da Oferta_TROFEUS:

| # | Item | Registro |
|---|---|---|
| 1 | Existência real do evento ou empresa | sim / não / indeterminado |
| 2 | Evidência real e rastreável | URL ou fonte + resultado da verificação |
| 3 | Plausibilidade do score | plausível / implausível + comentário |
| 4 | Utilidade do timing | útil / tardio / prematuro |
| 5 | Organizador correto | correto / incorreto |
| 6 | Decisor útil | útil / genérico / ausente |
| 7 | Contato disponível | verificado / inferido / ausente |
| 8 | Próxima ação definida | sim / não |
| 9 | Abordagem sugerida | usável / genérica / inadequada |
| — | **Veredito** | comercialmente útil: sim / não |

Regras de fechamento:

- evidência não localizável na fonte declarada → oportunidade registrada como
  **não útil** (item 2 reprova o veredito);
- valor inferido apresentado como fato verificado → **Finding
  `BLOCKS_ALPHAMEC`** (é exatamente a falha que 2.4 corrige);
- ao final, registrar a **proporção de oportunidades comercialmente úteis** e
  manter a rastreabilidade da evidência de cada ficha.

#### 3.3 Decisão sobre o provider de eventos (Requisito 15)

A decisão é tomada **depois** do UAT, com critério objetivo definido **antes**
dele, para não ser racionalizada a posteriori. Dois limiares:

| Critério | Limiar |
|---|---|
| Proporção de oportunidades comercialmente úteis (das ≥10 fichas) | **≥ 60%** |
| Proporção de fichas com evidência localizável na fonte declarada (item 2) | **≥ 80%** |

- **Ambos atingidos** → provider especializado MEJ/eventos permanece
  `DEFER_TO_V2`, com justificativa registrada e os números que a sustentam.
- **Qualquer um abaixo** → provider vira `BLOCKS_ALPHAMEC` e é implementado
  nesta branch, registrando provenance, confiança e os cinco estados `FOUND`,
  `EMPTY`, `FAILED`, `DISABLED`, `QUOTA_EXCEEDED`, reaproveitando o contrato de
  provider já existente (sem abstração paralela).

A decisão e os dados observados são registrados **antes** de qualquer
implementação decorrente.

#### 3.4 Classificação de findings (Requisito 16)

Todo Finding recebe exatamente uma classificação. `BLOCKS_ALPHAMEC` é corrigido
nesta branch. `IMPORTANT_ALPHAMEC` entra só com impacto alto e custo baixo ou
médio. `DEFER_TO_V2` é registrado em documentação e **não altera código desta
branch**. Os quatro blocos são o escopo total.

---

### Bloco 4 — BI mínimo de operação

#### 4.1 Estratégia: estender, não paralelizar

Endpoints já existentes em `analytics.py`: `overview`, `executive-metrics`,
`funnel`, `consultants`, `consultants/{id}`, `consultants/{id}/activity`,
`forecast`, `leads-ranking`, `geo`, `campaigns`, `outcomes-breakdown`,
`timeline`, `threshold-suggestion`, `deliverability`, `provider-usage`,
`provider-trace/{correlation_id}`, `message-variants`, `template-insights`,
`export/pdf`.

O BI dos Requisitos 17–19 é entregue reutilizando `funnel`,
`executive-metrics`, `campaigns` e `outcomes-breakdown`. Nenhum endpoint
paralelo.

#### 4.2 Lacunas reais a fechar

**(a) Oito contagens no funil.** `AnalyticsService.funnel` hoje devolve cinco
etapas: `achados`, `prospectados`, `responderam`, `reuniao_diagnostica`,
`fecharam`. O Requisito 17.1 pede oito quantidades. O funil passa a ter sete
etapas monotônicas mais um bloco de outcomes não monotônico:

```python
# cadeia monotônica — cada etapa é subconjunto da anterior
stages = {
    "encontrados":  base.count(),
    "qualificados": base.filter(Lead.status.in_(QUALIFIED_AND_BEYOND)).count(),
    "abordados":    ...,   # status contatado OU followup/message enviados
    "respostas":    ...,   # status respondido OU Message.is_response
    "reunioes":     ...,   # status de reunião OU atividade MEETING_*
    "propostas":    ...,   # status PROPOSTA_ENVIADA ou além
    "ganhos":       base.filter(Lead.id.in_(converted_ids)).count(),
}
# categorias de saída — fora da cadeia, contadas separadamente
outcomes = {
    "perdas":          base.filter(Lead.status == LeadStatus.PERDIDO).count(),
    "desqualificados": base.filter(Lead.status == LeadStatus.DESQUALIFICADO).count(),
}
```

`perdas` e `desqualificados` ficam **fora** da cadeia monotônica de propósito:
são saídas do funil, não etapas dele, e somá-las à cadeia quebraria a
monotonicidade sem ganho de leitura. Isso também mantém `PERDIDO` e
`DESQUALIFICADO` como categorias distintas (Requisito 17.6) — nunca agregadas em
"perdidos".

**(b) Taxa de conversão.** Derivada das contagens em `build_funnel_stages`, que
já é função pura. Domínio `[0, 1]`; denominador zero devolve `null` com
marcador de indisponibilidade, nunca `0.0`.

**(c) Filtro por `offer_key` no funil.** `funnel` hoje aceita `from`, `to`,
`campaign_id`, `consultant_id`. Ganha `offer_key`, alinhado ao que
`executive-metrics` já aceita. O corte é feito por `LeadOpportunity.offer_key` /
`Conversion.offer_key`, com parcela explícita "sem oferta" para fechar a partição.

**(d) Corte por canal onde o dado existe.** Derivado de `MessageChannel`
(abordagem e resposta) e `PostSaleChannel` (pós-venda). Onde o registro de origem
não tem canal, a parcela vai para "sem canal" — nunca é redistribuída nem
descartada.

**(e) Ausência de dado ≠ zero.** Toda agregação por dimensão devolve, por
categoria, `{ valor, amostra, disponivel }`. Dimensão sem dado persistido no
período responde `disponivel: false` em vez de `valor: 0`. A UI apresenta "sem
dado no período", não o número zero.

**(f) Tamanho de amostra exposto.** Cada agregação carrega `amostra` (n de
registros que a compõem) e, abaixo de um limiar explícito, um sinal de
insuficiência junto ao valor.

**(g) Tela única na navegação principal.** `/relatorios` já está na navegação
principal (`sidebar.tsx`, `mobile-bottom-nav.tsx`, `command-menu.tsx`), com o
gate de papel existente (`analystOnly`). Recebe a aba **"Funil de operação"**
com as sete etapas, as duas categorias de saída, a taxa de conversão e os
filtros de período, campanha, oferta e canal. Nenhuma rota nova, nenhuma mudança
na regra de papel. A exportação da visão filtrada reutiliza o caminho de export
existente, carregando os filtros aplicados no cabeçalho.

#### 4.3 Consistência (Requisito 19)

- **Partição fechada:** soma das partes de qualquer corte, mais a parcela sem
  valor na dimensão, é igual ao total do mesmo período e filtro.
- **Conjunção e comutatividade:** filtros são aplicados por interseção; o
  resultado não depende da ordem de aplicação.
- **Mesma métrica, mesmo número:** `funnel`, `executive-metrics` e `campaigns`
  devolvem o mesmo valor para a mesma métrica sob período e filtro iguais. Isso é
  garantido derivando todos da mesma base org-scoped (`self._leads(...)`) e dos
  mesmos conjuntos de eventos persistidos (`FollowUp`, `Message`, `LeadActivity`,
  `Conversion`, outcome comercial).
- **Escopo:** todo resultado restrito a `organization_id` da organização ativa.

#### 4.4 Contenção (Requisito 20)

Sem ferramenta externa de BI, sem dependência nova. Análise por variante de
mensagem **já existe** (`message-variants`) e é exposta como está. Atribuição
avançada de resultado permanece `DEFER_TO_V2` salvo necessidade comprovada no
UAT — a decisão, em qualquer direção, é registrada com os dados observados.

---

## Data Models

### Deltas de modelo

Toda mudança em `services/workers/src/database/models.py`, que segue como única
definição dos modelos; a API apenas reexporta via `services/api/src/db/models.py`.

| Modelo | Campo / constraint | Mudança | Nulável | Migration |
|---|---|---|---|---|
| `Organization` | `inbound_token_hash` | nova coluna `String(64)` + unique index | sim | `m1` |
| `Lead` | `ck_leads_lost_reason_required` | novo CHECK `NOT VALID` | — | `m2` |
| `Conversion` | `uq_conversions_lead_offer` | novo unique index de expressão | — | `m3` |
| `Job` | `organization_id` | `NOT NULL` (gateado) | passa a não | `m4` |

Nada é removido. `Conversion.offer_key`, `Conversion.lead_opportunity_id`,
`Conversion.offer_version` e `Lead.lost_reason` permanecem como estão.

---

## Components and Interfaces

### Contratos de API — deltas

| Endpoint | Mudança | Compatibilidade |
|---|---|---|
| `POST /api/webhooks/email/inbound/{token}` | **novo** | — |
| `POST /api/webhooks/import/{token}` | **novo** | — |
| `POST /api/webhooks/email/inbound` | passa a exigir `X-Organization-Id` + segredo global; depreciado | quebra configuração do provedor (reapontar URL) |
| `POST /api/webhooks/import` | idem | idem |
| `WS /api/pipeline/ws/{job_id}` | recusa job com `organization_id` nulo | mais restritivo |
| `PATCH /api/leads/{id}/status` | `422` quando `PERDIDO` sem `lost_reason` | mais restritivo |
| `POST /api/leads/{id}/conversion` | `409` em duplicata (antes podia duplicar) | mais restritivo |
| `GET /api/analytics/funnel` | novos parâmetros `offer_key` e `channel`; resposta com 7 etapas + 2 outcomes + `amostra` + `disponivel` | aditivo na entrada, ampliado na saída |

A única mudança que exige ação operacional é a URL de inbound no provedor. Está
registrada como risco em "Riscos e Pontos_De_Parada".

---

### Rastreabilidade: requisito → componente → teste

| Req | Componente alterado | Teste |
|---|---|---|
| 1 | `routes/webhooks.py`, `services/inbound_token_service.py` (novo), `services/inbound_email_service.py`, `models.py` + `m1` | integração cross-tenant de inbound; property de resolução de token; property de zero persistência |
| 2 | `services/inbound_email_service.py` | integração: `Message`/`LeadActivity`/`FollowUp`/`Notification` confinados; negativo de lead homônimo |
| 3 | `routes/pipeline.py`, `models.py` + `m4` (gateado) | unit de fail-closed (nulo, outra org, inexistente); property de indistinguibilidade; regressão de `GET /jobs` |
| 4 | `services/cadence_service.py` (`send_step`, `run_due`, `cancel_pending_for_terminal`) | unit de zero envio em `PERDIDO`/`DESQUALIFICADO`; property de disjunção em `run_due`; integração de `PENDING` = 0 |
| 5 | `routes/leads.py`, `services/lead_status_service.py` (novo), `models.py` + `m2` | unit de 422; property de invariante global; property de trilha `LOST`; property de não-colapso |
| 6 | `components/oportunidades/lead-list.tsx` | componente: motivo antes da requisição, cancelar = zero chamadas, contagem de sucesso/falha; property de equivalência lote↔individual |
| 7 | `routes/leads.py` (`register_conversion`, `find_duplicate_conversion`), `models.py` + `m3` | concorrência real (contagem 1); property de exatamente um sucesso; property de corpo sem detalhe de banco |
| 8 | `services/workers/alembic/versions/` (`m1`–`m4`) | gate `alembic heads`; `alembic upgrade head`; diff vazio nas migrations preexistentes |
| 9 | `campanhas/nova/page.tsx`, `campanhas/[id]/page.tsx` | property de intenção→parâmetro; componente de disparo único em StrictMode; browser QA |
| 10 | `components/oportunidades/lead-list.tsx` | contrato valor↔`pattern`; property de escopo duplo (org + usuário); property de 422 fora do contrato |
| 11 | `lib/safe-redirect.ts` (novo), `login/page.tsx`, `aceitar-convite/page.tsx` | property sobre strings arbitrárias; casos de borda (`//`, `/\`, esquemas, encodados); browser QA do convite |
| 12 | mapeamento de estados de provider + componentes de estado | property de mapeamento total; property de incompletude declarada; property de marcação de inferência |
| 13 | `docs/uat-runbook.md` (execução), configuração de Outreach_Assistido | smoke de configuração (`ENVIRONMENT`, SMTP, `auto_send_email`); registro por item |
| 14 | ficha de avaliação (≥10 oportunidades) | fichas preenchidas com evidência rastreável; proporção registrada |
| 15 | decisão registrada; provider especializado se abaixo do limiar | se implementado: testes de provenance, confiança e cinco estados |
| 16 | registro de findings | revisão de escopo por bloco |
| 17 | `services/analytics_service.py` (`funnel`, `build_funnel_stages`), `/relatorios` | property das 8 contagens; property de período; property de escopo por org; property de categorias distintas; browser QA da navegação |
| 18 | `routes/analytics.py` (`offer_key`, canal), `analytics_service.py` | property de partição fechada por campanha/oferta/canal; property de comutatividade; property de ausência ≠ zero; export com filtros |
| 19 | `analytics_service.py` (amostra, disponibilidade) | property de partição; property de amostra presente; property de sinal de insuficiência; property de igualdade entre telas |
| 20 | nenhuma dependência nova; `message-variants` como está | smoke de ausência de dependência de BI; decisão registrada |
| 21 | — | execução dos nove gates com evidência |
| 22 | núcleo preservado | Genericity Harness; property de snapshots somente-inserção; property dos cinco estados; smoke de modelo único |
| 23 | — | declaração final, demonstração em sessão única, revisão de implementação e de código |

---

## Error Handling

| Situação | Código | Corpo | Log |
|---|---|---|---|
| Token de inbound inválido / ausente | 401 | frase fixa de credencial inválida | tentativa registrada sem o token |
| Job inexistente, órfão ou de outra org | 403 (close WS) | razão idêntica nos três casos | id do job e org do usuário |
| `PERDIDO` sem motivo | 422 | erro de validação do campo `lost_reason` | — |
| Conversão duplicada | 409 | frase de domínio, sem nome de constraint/tabela/exceção | `IntegrityError` completo no log |
| Etapa bloqueada por estado terminal | — (não é erro HTTP) | `send_step` devolve `False`, etapa `SKIPPED` | `cadence_skipped` com `reason="terminal_status"` |
| Provider `FAILED`/`DISABLED`/`QUOTA_EXCEEDED` | 200 com estado | estado específico do provider | correlation id preservado |

Princípio: mensagem de erro para o cliente descreve o domínio; detalhe técnico
vai para o log. Recusa de autorização é indistinguível de recusa por
inexistência.

---

## Testing Strategy

### Tipos e onde rodam

| Tipo | Onde | Execução |
|---|---|---|
| Unit puro | `tests/` | `python -m pytest tests -q -W error` (raiz) |
| Property-based (Hypothesis) | `tests/` | idem |
| Contrato frontend/API | `tests/` (lado API) + testes de componente em `apps/web` | pytest + suíte web |
| Integração com Postgres real | `tests/` com `E2E_DATABASE_URL` | pulado automaticamente sem banco, como o `e2e_outreach_cycle.py` atual |
| Concorrência real | `tests/` com `E2E_DATABASE_URL` | transações paralelas de verdade |
| Browser QA | fluxos do Bloco 2 | manual/automatizado, evidência anexada |
| Genericity Harness | `tests/test_genericity_harness.py`, `tests/test_genericity_core_purity.py` | já no pytest da raiz |

### Ordem de escrita no Bloco 1

Todo teste de invariante do Bloco 1 é escrito **primeiro** e deve **falhar**
antes da correção. A evidência red→green é registrada por invariante. Sem isso, a
correção não é considerada verificada (Requisito 21.1).

### Cobertura por invariante

| Invariante | Teste que falha antes | Nível |
|---|---|---|
| Inbound cross-tenant | duas orgs, mesmo remetente; asserção de que o lead afetado é o da org do token | integração (Postgres) |
| Escrita cross-tenant | zero `Message` no lead da outra org após inbound | integração |
| Job órfão no WS | `organization_id=None` → close 403 | unit com stub de WS |
| Recusa indistinguível | tupla (código, razão) igual entre inexistente e de outra org | unit |
| Cadência em terminal | `send_step` e `run_due` com lead `PERDIDO` e `DESQUALIFICADO` | unit com SMTP stub |
| Pendências após terminal | `PENDING` = 0 após transição por qualquer rota | integração |
| `PERDIDO` sem motivo | `PATCH /status` → 422 e status preservado | unit (TestClient) |
| Conversão concorrente | n transações paralelas → contagem 1 | concorrência (Postgres) |
| Filtro `assigned` | valor emitido pelo componente ∈ `^(me\|none\|any)$` | contrato |
| `callbackUrl` hostil | absolutos, esquema alternativo, `//`, `/\`, encodados | property-based |
| Intenção do botão | uma coleta com intenção, zero sem | componente + browser QA |

### Configuração dos testes de propriedade

- mínimo de 100 iterações por propriedade;
- cada teste referencia a propriedade do design com a tag
  `Feature: alphamec-production-ready, Property {n}: {texto}`;
- geradores de I/O (SMTP, Groq, Google) sempre stubados nas propriedades; o custo
  real fica nos testes de integração, com 1–3 exemplos.

### Rastreabilidade: propriedade → tipo de teste

| Prop | Enunciado (resumo) | Tipo | Onde |
|---|---|---|---|
| P1 | Inbound confinado à organização | property-based + integração | `tests/` com `E2E_DATABASE_URL` |
| P2 | Escrita confinada à organização | integração | Postgres real |
| P3 | Ausência de efeito sem correspondência | property-based | contagem invariante, banco real |
| P4 | Falha fechada de job (bicondicional) | unit puro | matriz de jobs × usuários |
| P5 | Indistinguibilidade da recusa | unit puro | comparação de tuplas (código, razão) |
| P6 | Leitura confinada (BI e listagem) | integração | duas orgs povoadas |
| P7 | Estado terminal absorve a cadência | unit puro | SMTP stub |
| P8 | `run_due` exclui terminais | unit puro | população em memória/banco |
| P9 | Sem `PENDING` após terminal | integração | transição por todas as rotas |
| P10 | Perda implica motivo | **property-based (Hypothesis)** | sequências de requisições geradas |
| P11 | Rejeição preserva estado | unit puro | TestClient |
| P12 | Lote equivale a individual | contrato de componente | chamadas emitidas comparadas |
| P13 | Perda e desqualificação não colapsam | unit puro | trilha e outcome |
| P14 | Conversão única | **property-based + concorrência real** | n transações paralelas |
| P15 | Exatamente um sucesso | **concorrência real** | distribuição de status HTTP |
| P16 | Sem vazamento de erro de banco | **concorrência real** | inspeção do corpo da resposta |
| P17 | Idempotência de outcome | unit puro | repetição da mesma chave de evento |
| P18 | Snapshots somente-inserção | unit puro | sequência de operações |
| P19 | Valores de filtro pertencem ao contrato | contrato frontend/API | valor emitido × `pattern` |
| P20 | Redirecionamento interno | **property-based (fast-check/Hypothesis)** | strings arbitrárias |
| P21 | Intenção do botão preservada | contrato de componente + browser QA | StrictMode |
| P22 | Vazio distinto de falha | property-based | função pura de mapeamento |
| P23 | Inferência rotulada | property-based | valores com provenance gerada |
| P24 | Partição fechada | **property-based (Hypothesis)** | populações geradas |
| P25 | Monotonicidade do funil | **property-based (Hypothesis)** | `build_funnel_stages` (função pura) |
| P26 | Comutatividade de filtros | property-based | permutações de filtros |
| P27 | Taxa em domínio válido | **property-based (Hypothesis)** | dicionários de contagem gerados |
| P28 | Ausência de dado não é zero | **property-based (Hypothesis)** | dimensões vazias geradas |

---

## Gates de qualidade (Requisito 21)

Ordem de execução:

1. `python -m pytest tests -q -W error` (da raiz)
2. `python -m compileall -q services/api services/workers`
3. Genericity Harness (`test_genericity_harness.py`, `test_genericity_core_purity.py`)
4. `alembic heads` → exatamente uma cabeça; `alembic upgrade head` sem erros
   (CWD `services/workers`)
5. `npm run lint` em `apps/web`
6. `npx tsc --noEmit`
7. `npm run build`
8. Browser QA dos fluxos do Bloco 2, com evidências anexadas
9. `graphify update .` — **só se comprovadamente executável** no ambiente

Falha em qualquer gate de 1 a 8 bloqueia a conclusão da spec.

---

## Riscos e Pontos_De_Parada

| Risco | Detecção | Ação |
|---|---|---|
| Linhas legadas violando o CHECK de `lost_reason` | contagem antes de `VALIDATE` | **Ponto_De_Parada** com a contagem; CHECK fica `NOT VALID` |
| Duplicatas preexistentes em `conversions` | `GROUP BY ... HAVING count(*) > 1` | **Ponto_De_Parada** com as linhas; índice não é criado |
| `jobs.organization_id` nulo | `count(*) WHERE organization_id IS NULL` | **Ponto_De_Parada** com a contagem; `m4` não é aplicada; sem backfill adivinhado |
| Reconfiguração da URL de inbound no provedor | rota legada passa a exigir `X-Organization-Id` | rota legada mantida e depreciada; janela para reapontar a URL |
| Provider de eventos abaixo do limiar | fichas do UAT | vira `BLOCKS_ALPHAMEC` e entra nesta branch com os cinco estados e provenance |

### Fora de escopo (não implementado nesta branch)

CRM bidirecional; saved searches e watchers; intent avançado; atribuição causal
multitoque; CRUD e rollback dinâmico de `OfferProfile`; autoaplicação de
controlled learning.

---

## Correctness Properties

*Uma propriedade é uma característica ou comportamento que deve valer em todas as
execuções válidas do sistema — uma afirmação formal sobre o que o software deve
fazer. As propriedades são a ponte entre a especificação legível por humanos e a
garantia de correção verificável por máquina.*

### Property 1: Inbound confinado à organização

Para qualquer conjunto de organizações, leads e contatos, e qualquer endereço de
remetente, o lead afetado por um inbound autenticado para a organização `O` tem
`organization_id == O`, ou nenhum lead é afetado.

**Validates: Requirements 1.1, 1.3, 1.4**

### Property 2: Escrita confinada à organização

Para qualquer sequência de operações de inbound, toda `Message`, `LeadActivity`,
`FollowUp` e `Notification` criada pertence a um lead da organização resolvida na
operação que a criou.

**Validates: Requirements 2.1, 2.2**

### Property 3: Ausência de efeito sem correspondência

Para qualquer inbound sem lead correspondente na organização resolvida, e para
qualquer inbound com credencial inválida, a contagem de registros de todas as
tabelas envolvidas permanece igual à contagem anterior à requisição.

**Validates: Requirements 1.2, 1.5, 2.3**

### Property 4: Falha fechada de job

Para qualquer job `J` e qualquer usuário `U`, o acesso é autorizado se e somente
se `J.organization_id` é não nulo e igual à organização ativa de `U`. Job com
`organization_id` nulo nunca é autorizado.

**Validates: Requirements 3.1, 3.2, 3.4, 3.5**

### Property 5: Indistinguibilidade da recusa

Para qualquer job inexistente e qualquer job de outra organização, a resposta de
recusa é idêntica em código e razão, sem revelar existência.

**Validates: Requirements 3.3**

### Property 6: Leitura confinada

Para qualquer consulta de BI ou de listagem executada no contexto da organização
`O`, todo registro retornado tem `organization_id == O`.

**Validates: Requirements 10.2, 17.5**

### Property 7: Estado terminal absorve a cadência

Para qualquer lead que entre em `PERDIDO` ou `DESQUALIFICADO` no instante `t`, o
número de `Message` de outreach com `sent_at > t` para esse lead é zero.

**Validates: Requirements 4.1, 4.4**

### Property 8: Seleção de vencidos exclui terminais

Para qualquer população de `FollowUp` pendentes, o conjunto selecionado por
`run_due` é disjunto do conjunto de follow-ups de leads em estado terminal.

**Validates: Requirements 4.2**

### Property 9: Sem pendências após terminal

Para qualquer lead em estado terminal, e para qualquer caminho de transição que o
tenha levado até lá, a contagem de `FollowUp` com status `PENDING` é zero após a
transição.

**Validates: Requirements 4.3**

### Property 10: Perda implica motivo

Para qualquer sequência de requisições aceitas, todo lead com
`status == PERDIDO` tem `lost_reason` não nulo e pertencente ao enum
`LostReason`, e existe uma `LeadActivity` com ação `LOST` contendo o motivo.

**Validates: Requirements 5.2, 5.3, 5.5, 6.2**

### Property 11: Rejeição preserva estado

Para qualquer requisição de status rejeitada, o `status` e o `lost_reason` do
lead permanecem iguais aos valores anteriores à requisição.

**Validates: Requirements 5.1**

### Property 12: Lote equivale a individual

Para qualquer conjunto de leads, o efeito da ação em lote de perda é igual ao
efeito da mesma marcação executada individualmente lead por lead, e o número de
requisições emitidas antes da confirmação do motivo é zero.

**Validates: Requirements 6.1, 6.2, 6.3, 6.4**

### Property 13: Perda e desqualificação não colapsam

Para qualquer lead, `PERDIDO` e `DESQUALIFICADO` produzem trilhas e outcomes
distintos, e nenhum caminho converte um no outro.

**Validates: Requirements 5.4, 17.6**

### Property 14: Conversão única

Para qualquer `n >= 1` de requisições de conversão concorrentes ou sequenciais
com o mesmo `lead_id` e `offer_key`, incluindo `offer_key` nulo, a contagem final
de `Conversion` para o par é exatamente 1.

**Validates: Requirements 7.1, 7.3**

### Property 15: Exatamente um sucesso

Para qualquer `n >= 2` de requisições concorrentes do mesmo par, exatamente uma
resposta é de sucesso e as demais são HTTP 409.

**Validates: Requirements 7.2**

### Property 16: Sem vazamento de erro de banco

Para qualquer violação de constraint provocada por concorrência, o corpo da
resposta não contém nome de constraint, nome de tabela nem texto de exceção do
banco.

**Validates: Requirements 7.4**

### Property 17: Idempotência de outcome

Para qualquer repetição da mesma transição de status com a mesma chave de evento,
a quantidade de outcomes comerciais persistidos não aumenta.

**Validates: Requirements 5.2, 19.4**

### Property 18: Snapshots somente-inserção

Para qualquer sequência de operações, nenhum registro de snapshot de oportunidade
existente é alterado ou removido.

**Validates: Requirements 22.2**

### Property 19: Valores de filtro pertencem ao contrato

Para qualquer estado da interface do Painel_Oportunidades, o valor enviado no
parâmetro de atribuição pertence ao conjunto aceito pela API; qualquer valor fora
do conjunto resulta em HTTP 422.

**Validates: Requirements 10.1, 10.3, 10.5**

### Property 20: Redirecionamento interno

Para qualquer string fornecida como `callbackUrl`, incluindo variantes
percent-encoded, o destino final do redirecionamento é um caminho relativo da
própria aplicação; qualquer outro valor resulta em `/dashboard`.

**Validates: Requirements 11.1, 11.2, 11.3, 11.6**

### Property 21: Intenção do botão preservada

Para qualquer confirmação de brief com a intenção de iniciar coleta, exatamente
uma coleta é iniciada por carregamento da página; sem essa intenção, nenhuma
coleta é iniciada.

**Validates: Requirements 9.1, 9.2, 9.3**

### Property 22: Vazio distinto de falha

Para qualquer combinação de estados de provider, a interface apresenta ausência
de resultados apenas quando todos os providers consultados retornaram `EMPTY`; e
qualquer combinação com falha parcial declara a incompletude nomeando o provider
que falhou.

**Validates: Requirements 12.3, 12.4, 12.5, 22.4**

### Property 23: Inferência rotulada

Para qualquer valor exibido, se a origem do valor é heurística ou modelo de
linguagem, o valor é apresentado com marcação de inferência, distinta da
apresentação de dado com fonte verificada.

**Validates: Requirements 12.6, 14.4, 22.3**

### Property 24: Partição fechada

Para qualquer período, filtro e dimensão, a soma das partes do corte mais a
parcela sem valor na dimensão é igual ao total da métrica.

**Validates: Requirements 18.1, 18.2, 18.3, 19.1**

### Property 25: Monotonicidade do funil

Para qualquer período e filtro, cada etapa da cadeia do funil tem quantidade
menor ou igual à etapa imediatamente anterior.

**Validates: Requirements 17.1, 17.3, 19.5**

### Property 26: Comutatividade de filtros

Para qualquer conjunto de filtros compatíveis, o resultado é independente da
ordem de aplicação e igual à conjunção dos filtros.

**Validates: Requirements 18.5**

### Property 27: Taxa em domínio válido

Para qualquer período e filtro, a taxa de conversão está no intervalo de 0 a 1, e
é declarada indisponível quando o denominador é zero.

**Validates: Requirements 17.2, 19.2, 19.3**

### Property 28: Ausência de dado não é zero

Para qualquer dimensão sem dado persistido no período, a resposta declara
ausência de dado em vez de valor medido igual a zero.

**Validates: Requirements 18.4**
