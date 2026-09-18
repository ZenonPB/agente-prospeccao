"""Prova o mecanismo de segurança de rodapé de opt-out da cadência.

Contrato (docs/lead-to-conversation-contract.md, invariante 10): TODA
mensagem de e-mail da cadência contém mecanismo de opt-out, inclusive
follow-ups e closing, mesmo se o modelo omitir. A normalização é a
última barreira antes da persistência/envio.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.outreach_service import _normalize_response  # noqa: E402


def test_opt_out_footer_present_in_all_cadence_emails():
    out = _normalize_response({
        "subject": "S",
        "body_opening": "abertura sem rodape",
        "followup_1": "f1 sem rodape",
        "followup_2": "f2 sem rodape",
        "closing": "fim sem rodape",
    })
    for key in ("body_opening", "followup_1", "followup_2", "closing"):
        assert "STOP" in out[key], key
