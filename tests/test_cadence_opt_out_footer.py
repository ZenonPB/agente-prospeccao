"""A persistência da cadência garante opt-out em toda etapa de e-mail.

Contrato (docs/lead-to-conversation-contract.md, invariante 10): TODA
mensagem de e-mail da cadência contém mecanismo de opt-out, inclusive
quando o conteúdo agendado não veio do OutreachService normalizado.
`schedule_cadence` é a última barreira antes da persistência.
"""
from src.services.cadence_service import schedule_cadence


class _FakeQuery:
    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return []

    def first(self):
        return None


class _FakeDb:
    def __init__(self):
        self.added = []
        self.commits = 0

    def query(self, *_args, **_kwargs):
        return _FakeQuery()

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1

    def refresh(self, _row):
        return None


def _lead():
    from types import SimpleNamespace

    return SimpleNamespace(id="lead-1")


def _contents(follow_ups):
    from database.models import FollowUp

    return [fu.content for fu in follow_ups if isinstance(fu, FollowUp)]


def test_schedule_cadence_garante_rodape_stop_em_todas_as_etapas():
    db = _FakeDb()
    follow_ups = schedule_cadence(db, _lead(), {
        "subject": "S",
        "body_opening": "abertura sem rodape",
        "followup_1": "f1 sem rodape",
        "followup_2": "f2 sem rodape",
        "closing": "fim sem rodape",
    })
    assert len(follow_ups) == 4
    for content in _contents(follow_ups):
        assert "STOP" in (content or "")


def test_schedule_cadence_nao_duplica_rodape_existente():
    db = _FakeDb()
    body = "abertura\n-\nResponda STOP para não receber mais mensagens."
    follow_ups = schedule_cadence(db, _lead(), {
        "subject": "S",
        "body_opening": body,
        "followup_1": body,
        "followup_2": body,
        "closing": body,
    })
    for content in _contents(follow_ups):
        assert (content or "").count("Responda STOP") == 1
