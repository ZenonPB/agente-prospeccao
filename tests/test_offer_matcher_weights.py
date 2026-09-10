"""Matcher ponderado por oferta (P1.7).

Seam: `OfferMatcher.match` / `_score_profile` + `LeadOpportunity.score_breakdown`.
Critério P1.7: `mechanical_project`, `technical_drawing` e `machine_manual`
atribuem pesos diferentes aos mesmos sinais — o mesmo lead ordena as três
ofertas de forma distinta, em vez de empatar no peso igualitário legado.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))


def _profile(key, positive, weights):
    from services.prospecting.offer_profile import OfferProfile
    return OfferProfile(
        key=key,
        archetype="industrial",
        vertical="mechanical_engineering",
        version="1.0",
        signals={"positive": positive, "weights": weights},
    )


class TestMatcherPonderado:
    def test_mesmos_sinais_pesos_diferentes_ordenam_diferente(self):
        from services.prospecting.offer_matcher import OfferMatcher
        from services.prospecting.offer_profile import OfferProfileRegistry
        registry = OfferProfileRegistry()
        registry.register(_profile("oferta_a", ["HAS_CNPJ", "HAS_PHONE"],
                                   {"HAS_CNPJ": 10, "HAS_PHONE": 1}))
        registry.register(_profile("oferta_b", ["HAS_CNPJ", "HAS_PHONE"],
                                   {"HAS_CNPJ": 1, "HAS_PHONE": 10}))
        matcher = OfferMatcher(registry)
        # Só HAS_CNPJ presente: oferta_a deve pontuar muito mais que oferta_b.
        lead = {"company_name": "X", "has_cnpj": True}
        opps = {o.offer_key: o for o in matcher.match(lead)}
        assert opps["oferta_a"].score > opps["oferta_b"].score
        # Valores independentes: 10/11*70=63 vs 1/11*70=6 (sem ICP → só sinal)
        assert opps["oferta_a"].score == 63
        assert opps["oferta_b"].score == 6

    def test_sem_weights_mantem_peso_igualitario_legado(self):
        from services.prospecting.offer_matcher import OfferMatcher
        from services.prospecting.offer_profile import OfferProfileRegistry
        registry = OfferProfileRegistry()
        registry.register(_profile("oferta_legada", ["HAS_CNPJ", "HAS_PHONE"], {}))
        matcher = OfferMatcher(registry)
        lead = {"company_name": "X", "has_cnpj": True}
        opps = matcher.match(lead)
        assert opps[0].score == 35  # 1/2*70 legado

    def test_breakdown_expoe_contas(self):
        from services.prospecting.offer_matcher import OfferMatcher
        from services.prospecting.offer_profile import OfferProfileRegistry
        registry = OfferProfileRegistry()
        registry.register(_profile("oferta_a", ["HAS_CNPJ", "HAS_PHONE"],
                                   {"HAS_CNPJ": 10, "HAS_PHONE": 1}))
        matcher = OfferMatcher(registry)
        opps = matcher.match({"company_name": "X", "has_cnpj": True})
        bd = opps[0].score_breakdown
        assert bd["signal_score"] == 63
        assert bd["icp_score"] == 0
        assert bd["matched_weight"] == 10
        assert bd["total_weight"] == 11

    def test_ofertas_industriais_reais_pesam_diferente(self):
        from services.prospecting.offer_matcher import OfferMatcher
        from services.prospecting.default_profiles import build_default_registry
        matcher = OfferMatcher(build_default_registry())
        lead = {"company_name": "Metalúrgica X", "cnae": "25",
                "has_cnpj": True, "has_phone": True}
        opps = {o.offer_key: o for o in matcher.match(lead)}
        scores = {k: opps[k].score for k in
                  ("mechanical_project", "technical_drawing", "machine_manual")
                  if k in opps}
        assert len(scores) == 3
        assert len(set(scores.values())) > 1
