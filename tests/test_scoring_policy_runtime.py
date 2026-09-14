"""Contrato semântico de scoring e isolamento por lead."""
import asyncio

from database.models import AnalysisProfile, Lead, LeadStatus
from services.enrichment_orchestrator import process_single_lead
from services.lead_processing_guard import run_guarded_lead_operation
from services.offer_signal_adapter import merge_template_signals
from services.scoring_service import (
    _campaign_sells_erp_webapps,
    _campaign_sells_web_presence,
    build_prompt,
)


OFFER_SIGNALS = {
    "positive": ["NO_OWN_WEBSITE", "HAS_INSTAGRAM"],
    "negative": ["HAS_OWN_WEBSITE_INSTITUTIONAL"],
    "weights": {"NO_OWN_WEBSITE": 25, "HAS_INSTAGRAM": 12},
}


def _runtime_template(archetype="web_presence", key="landing_page", label="Nome comercial mutável"):
    return merge_template_signals(
        {
            "service_label": label,
            "positive_signals": [
                {"label": "Sem site próprio", "description": "Empresa sem website", "weight_hint": "high"},
            ],
            "negative_signals": [],
            "context_signals": [],
            "enrichment_steps": ["cnpj_receita", "technical_site"],
        },
        OFFER_SIGNALS,
        {"segments": ["psicologia"]},
        offer_key=key,
        offer_archetype=archetype,
    )


def test_web_presence_nao_depende_do_service_label():
    template = _runtime_template(label="Qualquer nome traduzido no futuro")
    assert _campaign_sells_web_presence(template, "texto irrelevante") is True
    prompt = build_prompt(
        "Landing pages e páginas de conversão",
        "clínicas de psicologia",
        template,
        [],
        ["Empresa: Clínica X", "Tem website: não"],
    )
    assert "é PÚBLICO-ALVO" in prompt
    assert "ausência de site próprio é NEUTRA" not in prompt


def test_digital_systems_usa_politica_erp_sem_label():
    template = _runtime_template(
        archetype="digital_systems",
        key="web_systems_erp",
        label="Solução XPTO",
    )
    assert _campaign_sells_web_presence(template, "landing page") is False
    assert _campaign_sells_erp_webapps(template, "texto sem ERP") is True
    prompt = build_prompt("Sistema sob medida", "serviços", template, [], ["Tem website: não"])
    assert "ausência de site próprio é NEUTRA" in prompt
    assert "Venda de SISTEMA WEB COMPLETO / ERP" in prompt


def test_archetype_desconhecido_falha_de_forma_conservadora():
    template = _runtime_template(archetype="novo_archetype", key="nova_oferta")
    policy = template["scoring_policy"]
    assert policy["mode"] == "generic"
    assert policy["website_absence"] == "neutral"
    assert _campaign_sells_web_presence(template, "landing page") is False


class _Savepoint:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        self.db.entered += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.db.rolled_back += 1
        return False


class _GuardDB:
    def __init__(self):
        self.entered = 0
        self.rolled_back = 0
        self.flushed = 0

    def begin_nested(self):
        return _Savepoint(self)

    def flush(self):
        self.flushed += 1


def test_guard_savepoint_isola_excecao_e_mantem_lote_utilizavel():
    db = _GuardDB()

    async def explode():
        raise AttributeError("contrato inválido")

    result = asyncio.run(
        run_guarded_lead_operation(db, explode, lead_name="Lead X", correlation_id="corr-1")
    )
    assert result.ok is False
    assert result.failure is not None
    assert result.failure.error_type == "AttributeError"
    assert db.entered == 1
    assert db.rolled_back == 1
    assert db.flushed == 0

    async def succeed():
        return "ok"

    result2 = asyncio.run(run_guarded_lead_operation(db, succeed, lead_name="Lead Y"))
    assert result2.ok is True
    assert result2.value == "ok"
    assert db.flushed == 1


class _FakeQuery:
    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return None


class _OrchestratorDB:
    def query(self, *_args, **_kwargs):
        return _FakeQuery()

    def add(self, *_args, **_kwargs):
        return None


class _FakeScoring:
    def __init__(self):
        self.kwargs = None

    async def score_business_lead(self, **kwargs):
        self.kwargs = kwargs
        return {
            "qualification_score": 85,
            "primary_need": "Presença digital",
            "qualification_reason": "Sem site próprio.",
            "priority": "HOT",
            "priority_reasoning": "Boa aderência.",
            "executive_summary": "Oportunidade clara.",
            "pitch_angle": "",
            "suggested_subject": "",
            "score_factors": [],
            "evidence": [],
        }


class _UnusedEnrichment:
    async def enrich_website(self, _url):
        raise AssertionError("lead sem site não deve executar auditoria técnica")


def test_landing_page_sem_site_sem_cnpj_conclui_scoring_business():
    lead = Lead(
        company_name="Psicologia Clínica",
        category="psychologist",
        city="Araraquara",
        state="SP",
        website=None,
        cnpj=None,
        status=LeadStatus.NOVO,
    )
    scoring = _FakeScoring()
    template = _runtime_template()
    _, result = asyncio.run(
        process_single_lead(
            lead,
            _UnusedEnrichment(),
            scoring,
            _OrchestratorDB(),
            analysis_profile=AnalysisProfile.WEB_PRESENCE,
            campaign_target_service="Landing pages e páginas de conversão",
            campaign_target_segment="clínicas de psicologia",
            scoring_template=template,
        )
    )
    assert result is not None
    assert result["qualification_score"] == 85
    assert lead.status == LeadStatus.QUALIFICADO
    assert scoring.kwargs is not None
    assert scoring.kwargs["website"] is None
    assert scoring.kwargs["template"]["scoring_policy"]["website_absence"] == "opportunity"
