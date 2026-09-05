"""Testes de auditoria profunda do OfferMatcher (achados na revisão).

Bug encontrado: o matcher não normaliza has_X=False ↔ no_X=True.
CASO 1: lead com has_own_website=False deveria bater no signal NO_OWN_WEBSITE
        e score ~80+ (4 sinais matched + icp hit).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))


class TestOfferMatcherAudit:
    def test_has_own_website_false_normaliza_para_no_own_website(self):
        """Bug: has_own_website=False NÃO conta como NO_OWN_WEBSITE no match atual."""
        from services.prospecting import OfferMatcher
        from services.prospecting.default_profiles import build_default_registry
        m = OfferMatcher(build_default_registry())
        lead = {
            "company_name": "Clínica X",
            "segment": "psicologia",
            "has_own_website": False,  # ← deveria contar como NO_OWN_WEBSITE
            "has_instagram": True,
            "has_phone": True,
            "google_rating": 4.5,
        }
        opps = m.match(lead)
        lp = next((o for o in opps if o.offer_key == "landing_page"), None)
        assert lp is not None
        # Esperado: 4 sinais matched (NO_OWN_WEBSITE + HAS_INSTAGRAM + HAS_PHONE + GOOGLE_RATING)
        # + 1 icp hit (segment) = 70 + 10 = 80
        # Atualmente só pega HAS_INSTAGRAM (1/4) + icp (10) = 27.5 → 27
        # Após fix: deve ser >= 70
        assert lp.score >= 70, f"score={lp.score}, evidence={lp.evidence}"

    def test_disqualifier_enterprise_zera_score(self):
        from services.prospecting import OfferMatcher
        from services.prospecting.default_profiles import build_default_registry
        m = OfferMatcher(build_default_registry())
        lead = {
            "company_name": "BigCo",
            "segment": "psicologia",
            "has_own_website": False,
            "has_instagram": True,
            "has_phone": True,
            "enterprise": True,  # disqualifier explícito
        }
        opps = m.match(lead)
        lp = next((o for o in opps if o.offer_key == "landing_page"), None)
        if lp:
            assert lp.score == 0
            assert "DISQUALIFIED" in str(lp.evidence)
