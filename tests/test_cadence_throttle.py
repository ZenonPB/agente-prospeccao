"""Testes do warmup/throttling e remetente dedicado.

Cobrem as funções puras que conduzem o throttle do `run_due`:
- `_org_daily_limit` — teto diário por org (fallback global);
- `_parse_hhmm` / `_window_state` — janela de espalhamento + teto por hora;
- `_resolve_from_email` — remetente dedicado por consultor → org → global.

O `run_due` em si depende de banco/ORM e SMTP (fora do escopo unitário).
"""
from types import SimpleNamespace

from src.services.cadence_service import (
    _org_daily_limit,
    _parse_hhmm,
    _resolve_from_email,
    _window_state,
)


def _org(**kw):
    defaults = dict(daily_email_limit=40, send_window_start="09:00", send_window_end="17:00")
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _window(org, hour, minute):
    now = SimpleNamespace(hour=hour, minute=minute)
    return _window_state(org, now)


# ---------------------------------------------------------------------------
# _org_daily_limit
# ---------------------------------------------------------------------------

def test_limite_usa_orgao_quando_definido():
    assert _org_daily_limit(_org(daily_email_limit=5)) == 5


def test_limite_fallback_global_quando_org_invalido():
    assert _org_daily_limit(_org(daily_email_limit=0)) > 0


def test_limite_sem_org_usa_default_global():
    assert isinstance(_org_daily_limit(None), int)


# ---------------------------------------------------------------------------
# _parse_hhmm / _window_state
# ---------------------------------------------------------------------------

def test_parse_hhmm_valido():
    assert _parse_hhmm("09:30", 0) == 9 * 60 + 30


def test_parse_hhmm_invalido_usa_default():
    assert _parse_hhmm("sem-separador", 12 * 60) == 12 * 60
    assert _parse_hhmm(None, 12 * 60) == 12 * 60


def test_window_dentro_retorna_true_e_teto_horario():
    # Janela 09:00–17:00 (480 min), limite 40 → teto por hora = ceil(40*60/480)=5.
    within, hourly_cap = _window(_org(), 12, 0)
    assert within is True
    assert hourly_cap == 5


def test_window_fora_retorna_false():
    within, _ = _window(_org(), 18, 0)
    assert within is False


def test_window_invertida_vira_dia_inteiro():
    # end < start → sem restrição de horário (só o teto diário).
    org = _org(send_window_start="17:00", send_window_end="09:00")
    within, hourly_cap = _window(org, 3, 0)
    assert within is True
    assert hourly_cap >= 1


def test_window_limite_teto_horario_proporcional():
    # Janela 08:00–10:00 (120 min), limite 40 → teto por hora = ceil(40*60/120)=20.
    org = _org(send_window_start="08:00", send_window_end="10:00")
    within, hourly_cap = _window(org, 9, 0)
    assert within is True
    assert hourly_cap == 20


# ---------------------------------------------------------------------------
# _resolve_from_email (remetente dedicado)
# ---------------------------------------------------------------------------

class _Member:
    def __init__(self, email_from):
        self.email_from = email_from


class _FakeDb:
    """db.query(col).filter(...).first() → devolve um member configurado."""

    def __init__(self, member):
        self._member = member

    def query(self, *_a):
        return self

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self._member


def _lead(assigned_to_id, org_id):
    return SimpleNamespace(assigned_to_id=assigned_to_id, organization_id=org_id)


def test_remetente_consultor_dedicado_tem_precedencia():
    org = _org(email=None)  # email_from é tratado abaixo via attribute
    org.email_from = "vendas@empresa.com.br"
    db = _FakeDb(_Member("rapha@empresa.com.br"))
    lead = _lead(assigned_to_id="user-rapha", org_id="org-1")
    assert _resolve_from_email(db, lead, org) == "rapha@empresa.com.br"


def test_remetente_org_quando_consultor_sem_email_dedicado():
    db = _FakeDb(_Member(email_from=None))
    org = _org(email_from="vendas@empresa.com.br")
    lead = _lead(assigned_to_id="user-rapha", org_id="org-1")
    assert _resolve_from_email(db, lead, org) == "vendas@empresa.com.br"


def test_remetente_sem_org_retorna_none_para_global():
    db = _FakeDb(_Member(email_from=None))
    org = _org(email_from=None)
    lead = _lead(assigned_to_id="user-1", org_id="org-1")
    assert _resolve_from_email(db, lead, org) is None