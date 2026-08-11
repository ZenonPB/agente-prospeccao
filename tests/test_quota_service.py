"""Testes do medidor de cotas por provedor/org (roadmap-vendas 4.14)."""
from datetime import datetime, timezone

from database.models import Organization, ProviderUsage
from services.quota_service import QuotaService


class _FakeOrg:
    id = "org-1"
    api_quota = None


class _FakeRow:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _FakeQuery:
    """Cadeia `.filter().first()` que roteia por entidade e por key_name."""

    def __init__(self, db, entity):
        self._db = db
        self._entity = entity
        self._key = None

    def filter(self, *args, **_k):
        for a in args:
            left = getattr(a, "left", None)
            if getattr(left, "name", None) == "key_name":
                right = getattr(a, "right", None)
                self._key = right.value if hasattr(right, "value") else str(right)
        return self

    def first(self):
        if self._entity is Organization:
            return self._db.org
        if self._key is not None:
            return self._db.rows.get(self._key)
        return next(iter(self._db.rows.values()), None)


class _FakeDb:
    """`rows` é um dict key_name → _FakeRow (medidor por provedor)."""

    def __init__(self, org=None, rows=None):
        self.org = org or _FakeOrg()
        self.rows = dict(rows or {})
        self.added = []

    def query(self, entity):
        return _FakeQuery(self, entity)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        for obj in self.added:
            if isinstance(obj, ProviderUsage):
                self.rows[obj.key_name] = obj
        self.added = []


def _today():
    return datetime.now(timezone.utc)


def test_limit_for_usando_default_do_pool():
    db = _FakeDb(_FakeOrg())
    # Sem override na org → default do settings (GOOGLE_API_KEY=100).
    assert QuotaService.limit_for(db, "org-1", "GOOGLE_API_KEY") >= 100
    assert QuotaService.limit_for(db, "org-1", "GROQ_API_KEY") >= 2000


def test_limit_for_respeita_override_da_org():
    org = _FakeOrg()
    org.api_quota = {"GOOGLE_API_KEY": 250}
    db = _FakeDb(org)
    assert QuotaService.limit_for(db, "org-1", "GOOGLE_API_KEY") == 250
    assert QuotaService.limit_for(db, "org-1", "GROQ_API_KEY") != 250


def test_remaining_subtrai_uso_do_dia():
    db = _FakeDb(_FakeOrg(), rows={"GOOGLE_API_KEY": _FakeRow(count=30)})
    assert QuotaService.used_today(db, "org-1", "GOOGLE_API_KEY", _today()) == 30
    remaining = QuotaService.remaining(db, "org-1", "GOOGLE_API_KEY", _today())
    assert remaining == QuotaService.limit_for(db, "org-1", "GOOGLE_API_KEY") - 30


def test_remaining_zero_quando_estoura():
    org = _FakeOrg()
    org.api_quota = {"GOOGLE_API_KEY": 10}
    db = _FakeDb(org, rows={"GOOGLE_API_KEY": _FakeRow(count=10)})
    assert QuotaService.remaining(db, "org-1", "GOOGLE_API_KEY", _today()) == 0
    assert QuotaService.can_consume(db, "org-1", "GOOGLE_API_KEY", when=_today()) is False


def test_consume_cria_contador_na_primeira_chamada():
    db = _FakeDb(_FakeOrg(), rows={})
    QuotaService.consume(db, "org-1", "GROQ_API_KEY", when=_today())
    row = db.rows["GROQ_API_KEY"]
    assert isinstance(row, ProviderUsage)
    assert row.count == 1
    assert row.usage_date == _today().date()


def test_consume_incrementa_contador_existente():
    row = _FakeRow(count=5)
    db = _FakeDb(_FakeOrg(), rows={"GOOGLE_API_KEY": row})
    QuotaService.consume(db, "org-1", "GOOGLE_API_KEY", when=_today())
    assert row.count == 6
    assert db.added == []


def test_consume_sem_org_nao_conta():
    db = _FakeDb(_FakeOrg())
    QuotaService.consume(db, None, "GOOGLE_API_KEY", when=_today())
    assert db.added == []


def test_usage_for_org_monta_painel_com_pct():
    org = _FakeOrg()
    org.api_quota = {"GOOGLE_API_KEY": 100, "GROQ_API_KEY": 100}
    db = _FakeDb(org, rows={"GOOGLE_API_KEY": _FakeRow(count=90)})
    usage = {u["key_name"]: u for u in QuotaService.usage_for_org(db, "org-1", _today())}
    assert usage["GOOGLE_API_KEY"]["used"] == 90
    assert usage["GOOGLE_API_KEY"]["remaining"] == 10
    assert usage["GOOGLE_API_KEY"]["pct"] == 90.0
    assert usage["GROQ_API_KEY"]["pct"] == 0.0
