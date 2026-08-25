"""Unit — roteamento multi-decisor da cadência e insights de vertente.

Funções puras (sem banco): `_planned_recipient` / `_candidate_emails`
(cadence_service) e `compute_signal_insights` (analytics_service).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))

from src.services.cadence_service import (  # noqa: E402
    _candidate_emails,
    _planned_recipient,
)
from src.db.models import ContactRole, FollowUpStep  # noqa: E402

# analytics_service é da API — conftest já injeta env dummy para os Settings.
from src.services.analytics_service import compute_signal_insights  # noqa: E402


class FakeContact:
    def __init__(self, email, role=None, is_primary=False, email_verified=True):
        self.email = email
        self.role = role
        self.is_primary = is_primary
        self.email_verified = email_verified


class FakeLead:
    def __init__(self, email=None, contacts=None):
        self.email = email
        self.contacts = contacts or []


def test_abertura_vai_para_o_email_principal_do_lead():
    lead = FakeLead(email="geral@empresa.com", contacts=[FakeContact("socio@empresa.com")])
    assert _planned_recipient(lead, step=FollowUpStep.OPENING) == "geral@empresa.com"


def test_followup_1_mantem_o_destinatario_da_abertura():
    lead = FakeLead(email="geral@empresa.com", contacts=[FakeContact("socio@empresa.com")])
    sent_to = ["geral@empresa.com"]
    assert (
        _planned_recipient(lead, step=FollowUpStep.FOLLOWUP_1, sent_to=sent_to)
        == "geral@empresa.com"
    )


def test_followup_2_escala_para_outro_decisor():
    lead = FakeLead(
        email="compras@industria.com",
        contacts=[
            FakeContact("engenharia@industria.com", role=ContactRole.DIRETOR),
            FakeContact("socio@industria.com", role=ContactRole.SOCIO),
        ],
    )
    recipient = _planned_recipient(
        lead,
        step=FollowUpStep.FOLLOWUP_2,
        sent_to=["compras@industria.com"],
    )
    # Sócio é o mais sênior entre os alternativos.
    assert recipient == "socio@industria.com"


def test_closing_tambem_escala_e_nao_repete_quem_ja_recebeu():
    lead = FakeLead(
        email="a@x.com",
        contacts=[FakeContact("b@x.com", role=ContactRole.CEO), FakeContact("c@x.com")],
    )
    sent_to = ["a@x.com", "b@x.com"]
    assert (
        _planned_recipient(lead, step=FollowUpStep.CLOSING, sent_to=sent_to)
        == "c@x.com"
    )


def test_sem_alternativo_mantem_o_principal():
    lead = FakeLead(email="unico@x.com")
    assert (
        _planned_recipient(
            lead, step=FollowUpStep.FOLLOWUP_2, sent_to=["unico@x.com"]
        )
        == "unico@x.com"
    )


def test_gate_de_verificado_filtra_contatos_nao_verificados():
    lead = FakeLead(
        contacts=[FakeContact("chute@x.com", email_verified=False)]
    )
    assert _candidate_emails(lead, require_verified=True) == []
    # Envio manual (require_verified=False) pode usar.
    assert _candidate_emails(lead, require_verified=False) == ["chute@x.com"]


def test_prioridade_de_papel_ordena_socio_antes_de_administrador():
    lead = FakeLead(
        contacts=[
            FakeContact("admin@x.com", role=ContactRole.ADMINISTRADOR),
            FakeContact("socio@x.com", role=ContactRole.SOCIO),
        ]
    )
    assert _candidate_emails(lead)[0] == "socio@x.com"


def test_primario_do_mesmo_nivel_vem_primeiro():
    lead = FakeLead(
        contacts=[
            FakeContact("segundo@x.com", role=ContactRole.OUTRO),
            FakeContact("primeiro@x.com", role=ContactRole.OUTRO, is_primary=True),
        ]
    )
    assert _candidate_emails(lead)[0] == "primeiro@x.com"


# ---------------------------------------------------------------------------
# compute_signal_insights — loop de aprendizado por frequência relativa.
# ---------------------------------------------------------------------------


def sf(*labels):
    return [{"label": l} for l in labels]


def test_insight_reforca_caracteristica_dos_convertidos():
    converted = [sf("tem site lento"), sf("tem site lento"), sf("tem site lento"), sf("outro")]
    lost = [sf("outro"), sf("outro"), sf("outro"), sf("outro")]
    result = compute_signal_insights(converted, lost)
    by_label = {i["label"]: i for i in result["insights"]}
    assert by_label["tem site lento"]["suggestion"] == "reforcar"
    assert result["converted_total"] == 4
    assert result["lost_total"] == 4


def test_insight_reduz_caracteristica_dos_perdidos():
    converted = [sf("z"), sf("z"), sf("z"), sf("z")]
    lost = [sf("site wordpress"), sf("site wordpress"), sf("site wordpress"), sf("z")]
    result = compute_signal_insights(converted, lost)
    by_label = {i["label"]: i for i in result["insights"]}
    assert by_label["site wordpress"]["suggestion"] == "reduzir"


def test_base_pequena_de_um_lado_nao_gera_sugestao():
    # 1 conversão só: 100% de taxa é ruído, não sinal.
    converted = [sf("site wordpress")]
    lost = [sf("site wordpress"), sf("site wordpress"), sf("x")]
    result = compute_signal_insights(converted, lost)
    assert result["insights"] == []


def test_amostra_pequena_fica_de_fora():
    converted = [sf("raro"), sf("a"), sf("b"), sf("c")]
    lost = [sf("raro"), sf("a"), sf("b"), sf("c")]
    result = compute_signal_insights(converted, lost, min_occurrences=3)
    assert all(i["label"] != "raro" for i in result["insights"])


def test_gap_pequeno_e_neutro():
    converted = [sf("a"), sf("b"), sf("a"), sf("d")]
    lost = [sf("a"), sf("c"), sf("a"), sf("f")]
    result = compute_signal_insights(converted, lost)
    by_label = {i["label"]: i for i in result["insights"]}
    assert by_label["a"]["suggestion"] == "neutro"


def test_rotulos_normalizados_sem_duplicar_por_lead():
    # Mesma característica com caixa diferente no MESMO lead conta uma vez
    # (sem dedup, o 1º lead contribuiria 2 e o total seria 4).
    converted = [
        [{"label": "Site Lento"}, {"label": "site lento"}],
        sf("site lento"),
        sf("site lento"),
        sf("z"),
    ]
    lost = [sf("x"), sf("y"), sf("z"), sf("w")]
    result = compute_signal_insights(converted, lost)
    by_label = {i["label"]: i for i in result["insights"]}
    assert by_label["site lento"]["converted"] == 3
