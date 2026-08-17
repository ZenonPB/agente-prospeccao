"""Testes da integração do outreach com o `provider_client` (rate-limit/cotas).

O `generate_sequence` agora passa por `groq_json_chat` (pacing + retry 429/5xx
+ gate/consumo de cota). Aqui o stub é a função do provider — a mesma costura
usada no scoring — e o teste não depende de rede.
"""
import asyncio

from services.outreach_service import OutreachService

_CANNED = {
    "subject": "O site sem CTA de matrícula",
    "body_opening": (
        "João,\nO site da sua academia não tem formulário de matrícula, "
        "então o tráfego que o Google manda não vira aluno.\n-\n"
        "Responda STOP para não receber mais mensagens."
    ),
    "followup_1": "Follow-up com novo ângulo.",
    "followup_2": "Insight + caso genérico do segmento.",
    "closing": "Encerramento respeitoso.",
    "whatsapp_short": "Posso te mostrar como converter visitantes?",
    "rationale": "Gancho na ausência de CTA de matrícula.",
}

_LEAD = {
    "company_name": "Habitus Academia Baldan",
    "category": "Academia",
    "city": "Matão",
    "state": "SP",
    "website": "https://habitusbaldan.com.br",
    "primary_need": "Captar mais alunos via site",
    "pitch_angle": "Site sem CTA de matrícula impede captação digital de alunos",
    "qualification_reason": "Academia bem avaliada no Maps mas site sem fluxo de conversão.",
    "evidence": [
        {"title": "Sem CTA de matrícula", "description": "Homepage sem botão 'Matricule-se'."},
    ],
    "contacts": [{"name": "João Baldan", "role_label": "Sócio-Proprietário", "email": "joao@habitusbaldan.com.br"}],
}


def _patch_provider(monkeypatch, result, collect=None, pace=0.0, retries=2):
    from services import provider_client

    async def fake_groq_json_chat(*args, **kwargs):
        if collect is not None:
            collect(kwargs)
        return result

    monkeypatch.setattr(provider_client, "groq_json_chat", fake_groq_json_chat)
    monkeypatch.setattr(provider_client.settings, "GROQ_MIN_INTERVAL_SECONDS", pace)
    monkeypatch.setattr(provider_client.settings, "GROQ_MAX_RETRIES", retries)
    monkeypatch.setattr(provider_client, "_last_groq_sent", 0.0)


def test_generate_sequence_usa_provider_e_normaliza(monkeypatch):
    _patch_provider(monkeypatch, _CANNED)
    out = asyncio.run(OutreachService(api_key="test").generate_sequence(_LEAD, "Criação de Sites", "academias"))
    assert out is not None
    assert out["subject"] == _CANNED["subject"]
    assert "Responda STOP" in out["body_opening"]
    assert out["followup_1"] == _CANNED["followup_1"]


def test_generate_sequence_repassa_cota_db_e_org(monkeypatch):
    captured = {}

    def collect(kwargs):
        captured.update(kwargs)

    _patch_provider(monkeypatch, _CANNED, collect=collect)
    asyncio.run(
        OutreachService(api_key="test").generate_sequence(
            _LEAD, "X", "", db=object(), organization_id="org-1",
        )
    )
    assert captured.get("organization_id") == "org-1"
    assert captured.get("db") is not None
    assert captured.get("max_tokens") == 6000


def test_generate_sequence_falha_do_provider_retorna_none(monkeypatch):
    _patch_provider(monkeypatch, None)
    out = asyncio.run(OutreachService(api_key="test").generate_sequence(_LEAD))
    assert out is None