"""Contrato dos estados de resolução de decisor (Onda 1, PR04).

Cobre a máquina de estados exigida pelo roadmap: resolved/partial indicam
pessoa encontrada, needs_review exige humano, not_found indica ausência e
failed indica exceção de provider (retryable), nunca confundidos.
"""
from database.models import Person


def _columns(model):
    return {column.key for column in model.__table__.columns}


class TestPersonCanonicalFields:
    def test_person_tem_campos_canonicos_de_confianca(self):
        """Person carrega identidade/contato/verificação/acionabilidade."""
        columns = _columns(Person)
        for field in (
            "identity_confidence",
            "contact_confidence",
            "source_reliability",
            "verification_status",
            "last_verified_at",
            "routability_type",
            "routable",
            "routability_reason",
        ):
            assert field in columns, f"Person sem campo canônico: {field}"
