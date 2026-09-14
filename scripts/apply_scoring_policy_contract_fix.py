"""Patch temporário usado pelo CI da branch de correção.

O arquivo se remove antes do commit final. Mantemos a transformação aqui para
que o runner aplique as mudanças sobre um checkout completo e rode a suíte real.
"""
from pathlib import Path
import re


SCORING = Path("services/workers/src/services/scoring_service.py")
PIPELINE = Path("services/api/src/pipeline_worker.py")
TESTS = Path("tests/test_scoring_policy_runtime.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: esperado 1 match, encontrados {count}")
    return text.replace(old, new, 1)


def patch_scoring() -> None:
    text = SCORING.read_text()

    replacement = '''# Política semântica de scoring vinda do OfferProfile efetivo. Labels comerciais
# são apresentação e nunca devem alterar comportamento do motor.
def _runtime_scoring_policy(template: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    if not isinstance(template, dict):
        return None
    raw = template.get("scoring_policy")
    if not isinstance(raw, dict):
        return None
    mode = str(raw.get("mode") or "").strip()
    website_absence = str(raw.get("website_absence") or "").strip()
    if mode not in {"generic", "web_presence", "erp"}:
        logger.warning("scoring_policy.mode inválido: %r", mode)
        return None
    if website_absence not in {"neutral", "opportunity"}:
        logger.warning("scoring_policy.website_absence inválido: %r", website_absence)
        return None
    return {
        "mode": mode,
        "website_absence": website_absence,
        "offer_key": str(raw.get("offer_key") or ""),
        "archetype": str(raw.get("archetype") or ""),
    }


# Fallback legado: campanhas sem OfferProfile efetivo ainda usam o contrato
# anterior até serem migradas/publicadas. O pipeline principal injeta
# scoring_policy e, portanto, não depende destes labels.
_WEB_PRESENCE_LABELS = frozenset({
    "desenvolvimento de sites",
    "seo / marketing digital",
})
_SELLS_WEB_PRESENCE = re.compile(
    r"site|website|p[áa]gina|loja virtual|presen[çc]a digital|landing|"
    r"marketing digital|seo|e-?commerce|web\\s?(design|sites?|presen)",
    re.IGNORECASE,
)


def _campaign_sells_web_presence(template: Optional[Dict[str, Any]], target_service: str) -> bool:
    policy = _runtime_scoring_policy(template)
    if policy is not None:
        return policy["website_absence"] == "opportunity"

    if template:
        label = (template.get("service_label") or "").strip().lower()
        if label not in _WEB_PRESENCE_LABELS and label != "genérico":
            return False
    return bool(_SELLS_WEB_PRESENCE.search(target_service or ""))


'''
    pattern = r"# Campanhas cujo serviço é presença digital/desenvolvimento de site.*?(?=# Labels de template cuja venda é sistema web completo / ERP)"
    text, count = re.subn(pattern, lambda _match: replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"bloco web_presence: esperado 1 match, encontrados {count}")

    replacement = '''# Fallback legado de ERP. No fluxo principal, `mode=erp` vem do archetype
# técnico `digital_systems`, não do texto exibido no template.
_ERP_WEBAPP_LABELS = frozenset({
    "aplicações web / erp",
    "sistemas web / erp",
    "aplicações web completas",
    "erp personalizado",
    "sistema web sob medida",
})


def _campaign_sells_erp_webapps(template: Optional[Dict[str, Any]], target_service: str) -> bool:
    policy = _runtime_scoring_policy(template)
    if policy is not None:
        return policy["mode"] == "erp"

    if template:
        label = (template.get("service_label") or "").strip().lower()
        if label in _ERP_WEBAPP_LABELS:
            return True
        if label and label != "genérico":
            return False
    if not target_service:
        return False
    svc = target_service.lower()
    return bool(re.search(
        r"erp|sistema(s)?\\s+web|aplica[çc][ãa]o\\s+web|gest[ãa]o\\s+integrada|"
        r"plataforma\\s+(web|sob\\s+medida)|software\\s+sob\\s+medida",
        svc,
    ))


'''
    pattern = r"# Labels de template cuja venda é sistema web completo / ERP.*?(?=def _contradicts_site_state)"
    text, count = re.subn(pattern, lambda _match: replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"bloco ERP: esperado 1 match, encontrados {count}")

    SCORING.write_text(text)


def patch_pipeline() -> None:
    text = PIPELINE.read_text()
    old = "from services.enrichment_orchestrator import process_single_lead, resolve_enrichment_steps\n"
    text = replace_once(
        text,
        old,
        old + "from services.lead_processing_guard import run_guarded_lead_operation\n",
        "import lead guard",
    )

    old = '''            scoring_template = merge_template_signals(
                {**(scoring_template or {}), **offer_template},
                offer_signals=offer_resolution.signals,
                icp=offer_resolution.icp,
            )'''
    new = '''            scoring_template = merge_template_signals(
                {**(scoring_template or {}), **offer_template},
                offer_signals=offer_resolution.signals,
                icp=offer_resolution.icp,
                offer_key=offer_resolution.key,
                offer_archetype=offer_resolution.archetype,
            )'''
    text = replace_once(text, old, new, "injeção scoring_policy")

    old = '''                scoring_result = None
                try:
                    _, scoring_result = await process_single_lead(
                        lead, enrichment_service, scoring_service, db,
                        analysis_profile=analysis_profile,
                        campaign_target_service=campaign.target_service if campaign else "",
                        campaign_target_segment=campaign.target_segment if campaign else "",
                        scoring_template=scoring_template,
                        allow_business_fallback=reanalyze_only,
                        learned_instructions=learned_instructions,
                        explicit_reanalyze=reanalyze_only,
                    )
                except Exception:  # noqa: BLE001 — falha isolada por lead: registra com traceback e segue o lote
                    logger.exception("Falha ao processar lead %s (será reprocessado)", lead.company_name)

                if scoring_result is None:'''
    new = '''                async def _score_current_lead():
                    return await process_single_lead(
                        lead, enrichment_service, scoring_service, db,
                        analysis_profile=analysis_profile,
                        campaign_target_service=campaign.target_service if campaign else "",
                        campaign_target_segment=campaign.target_segment if campaign else "",
                        scoring_template=scoring_template,
                        allow_business_fallback=reanalyze_only,
                        learned_instructions=learned_instructions,
                        explicit_reanalyze=reanalyze_only,
                    )

                guarded = await run_guarded_lead_operation(
                    db,
                    _score_current_lead,
                    lead_name=lead.company_name,
                    correlation_id=correlation_id,
                )
                scoring_result = None
                processing_failure = guarded.failure
                if guarded.ok and guarded.value is not None:
                    _, scoring_result = guarded.value

                if scoring_result is None:'''
    text = replace_once(text, old, new, "isolamento por lead")

    old = '''                    yield {
                        "type": "log",
                        "message": (
                            f"{lead.company_name} NÃO foi pontuado agora (falha temporária) — "
                            "será reprocessado no próximo lote."
                        ),
                        "timestamp": _ts(),
                    }'''
    new = '''                    failure_message = (
                        f"Não foi possível analisar {lead.company_name} agora. "
                        "O restante da busca continua e este lead ficará pendente para nova tentativa."
                        if processing_failure
                        else (
                            f"{lead.company_name} NÃO foi pontuado agora (serviço de análise indisponível) — "
                            "será reprocessado no próximo lote."
                        )
                    )
                    yield {
                        "type": "log",
                        "message": failure_message,
                        "timestamp": _ts(),
                    }'''
    text = replace_once(text, old, new, "mensagem de falha")
    PIPELINE.write_text(text)


def write_tests() -> None:
    TESTS.write_text('''"""Contrato semântico de scoring e isolamento por lead."""
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
''')


if __name__ == "__main__":
    patch_scoring()
    patch_pipeline()
    write_tests()
