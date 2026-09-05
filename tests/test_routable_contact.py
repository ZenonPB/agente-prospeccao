"""Testes do Routable Contact (Fase 3 — docs 42 e 47).

Seam: `classify_routability(phone, pabx_extension, target_person)`,
       `actionable_contact_rate(contacts)`.
Capacidade: classificar telefone como DIRECT_CONTACT/ROUTABLE_CONTACT/INSTITUTIONAL
e calcular taxa consolidada de contatos acionáveis.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.routable_contact_service import (  # noqa: E402
    classify_routability,
    actionable_contact_rate,
)


class TestClassifyRoutability:
    def test_sem_phone_e_unknown(self):
        r = classify_routability(None)
        assert r["type"] == "UNKNOWN"
        assert r["routable"] is False

    def test_telefone_longo_e_direct(self):
        r = classify_routability("16999998888")
        assert r["type"] == "DIRECT_CONTACT"
        assert r["routable"] is True

    def test_pabx_com_target_person_e_routable(self):
        r = classify_routability(
            "1633334000",
            pabx_extension="123",
            target_person="João",
        )
        assert r["type"] == "ROUTABLE_CONTACT"
        assert r["routable"] is True
        assert r["pabx_extension"] == "123"
        assert r["target_person"] == "João"

    def test_telefone_curto_generico_e_institutional(self):
        # Telefones muito curtos são institucionais
        r = classify_routability("11400")
        assert r["type"] == "INSTITUTIONAL"
        assert r["routable"] is False


class TestActionableContactRate:
    def test_sem_contatos_rate_zero(self):
        r = actionable_contact_rate([])
        assert r["actionable_rate"] == 0.0
        assert r["total"] == 0

    def test_todos_direct_rate_100(self):
        r = actionable_contact_rate([
            {"phone": "16999998888", "full_name": "A"},
            {"phone": "16988887777", "full_name": "B"},
        ])
        assert r["actionable_rate"] == 1.0
        assert r["direct"] == 2
        assert r["routable"] == 0
        assert r["institutional"] == 0

    def test_misto_calcula_proporcao(self):
        r = actionable_contact_rate([
            {"phone": "16999998888", "full_name": "A"},  # direct
            {"phone": "1633334000", "pabx_extension": "1", "full_name": "B"},  # routable
            {"phone": "1140000000"},  # direct (10 dígitos)
        ])
        # 3 direct/routable em 3 total = 1.0
        assert r["total"] == 3
        assert r["actionable_rate"] > 0.5

    def test_institucional_e_inactionable(self):
        r = actionable_contact_rate([
            {"phone": "16999998888", "full_name": "A"},
            {"phone": "11400"},  # institutional
        ])
        assert r["actionable_rate"] < 1.0
        assert r["institutional"] == 1
