"""Narrativa comercial da oportunidade (P1.10 — "Why this offer?").

Seam: `build_opportunity_narrative(opportunity, profile)`.
Critério P1.10: separar explicitamente FATOS (sinais presentes), HIPÓTESE
(o que os sinais sugerem) e VALIDAÇÃO (perguntas para confirmar) — copiloto
de vendas, não apenas ranking.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))


def _opp(**kw):
    from services.prospecting.offer_matcher import LeadOpportunity
    base = dict(offer_key="technical_drawing", profile_key="industrial",
                score=70, signals_matched=["HAS_CNPJ"],
                signals_missing=["HAS_BUSINESS_EMAIL"])
    base.update(kw)
    return LeadOpportunity(**base)


def _profile():
    from services.prospecting.default_profiles import build_default_registry
    return build_default_registry().get("technical_drawing")


class TestNarrative:
    def test_separa_fatos_hipotese_validacao(self):
        from services.prospecting.opportunity_narrative import build_opportunity_narrative
        n = build_opportunity_narrative(_opp(), _profile())
        assert n["facts"] and all("HAS_CNPJ" in f for f in n["facts"])
        assert n["hypotheses"]
        assert n["validation_questions"]
        assert set(n) >= {"facts", "hypotheses", "validation_questions", "headline"}

    def test_headline_traz_oferta_e_score(self):
        from services.prospecting.opportunity_narrative import build_opportunity_narrative
        n = build_opportunity_narrative(_opp(score=70), _profile())
        assert "70" in n["headline"]

    def test_pergunta_validacao_cita_sinal_ausente(self):
        from services.prospecting.opportunity_narrative import build_opportunity_narrative
        n = build_opportunity_narrative(_opp(), _profile())
        blob = " ".join(n["validation_questions"])
        assert "HAS_BUSINESS_EMAIL" in blob

    def test_sem_perfil_usa_generico_sem_quebrar(self):
        from services.prospecting.opportunity_narrative import build_opportunity_narrative
        n = build_opportunity_narrative(_opp(), None)
        assert n["facts"] and n["validation_questions"]
