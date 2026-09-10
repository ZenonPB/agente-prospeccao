"""Golden patterns operacionais por oferta (P1.28).

Seams: `match_golden_patterns(profile_key, signals, archetype=None)` +
wiring no `OfferMatcher` (evidence `golden:<id>`).
Critério P1.28: patterns associados a OfferProfile e ligados ao pipeline —
não apenas dois genéricos órfãos.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))


class TestGoldenPorOferta:
    def test_landing_page_tem_padrao_proprio(self):
        from services.learning_service import match_golden_patterns
        matches = match_golden_patterns("landing_page", {
            "NO_OWN_WEBSITE": True, "HAS_INSTAGRAM": True,
        })
        ids = [m["pattern_id"] for m in matches]
        assert any("landing_page" in i for i in ids)

    def test_trophies_tem_padrao_proprio(self):
        from services.learning_service import match_golden_patterns
        matches = match_golden_patterns("trophies", {
            "HOSTS_EVENTS": True, "HAS_INSTAGRAM": True,
        })
        ids = [m["pattern_id"] for m in matches]
        assert any("trophies" in i for i in ids)

    def test_archetype_industrial_casa_ofertas_sem_padrao_explicito(self):
        from services.learning_service import match_golden_patterns
        # technical_drawing não tem padrão próprio para {CNPJ, PHONE}, mas o
        # arquétipo industrial casa via machine_manual_fabricante.
        matches = match_golden_patterns("technical_drawing", {
            "HAS_CNPJ": True, "HAS_PHONE": True,
        }, archetype="industrial")
        ids = [m["pattern_id"] for m in matches]
        assert "machine_manual_fabricante_contatavel" in ids

    def test_sem_sinais_sem_match(self):
        from services.learning_service import match_golden_patterns
        assert match_golden_patterns("landing_page", {}) == []

    def test_condicao_nao_booleana_usa_igualdade_semantica(self):
        from services.learning_service import match_golden_patterns
        matches = match_golden_patterns("web_presence", {
            "NO_OWN_WEBSITE": True,
            "GOOGLE_RATING_COUNT": "".join([">", "=5"]),
        })
        assert matches[0]["pattern_id"] == "web_presence_no_site"


class TestGoldenNoMatcher:
    def test_matcher_anexa_golden_na_evidencia(self):
        from services.prospecting.offer_matcher import OfferMatcher
        from services.prospecting.default_profiles import build_default_registry
        matcher = OfferMatcher(build_default_registry())
        lead = {"company_name": "Clínica X", "has_own_website": False,
                "has_instagram": True, "has_phone": True}
        opps = {o.offer_key: o for o in matcher.match(lead)}
        assert any(e.startswith("golden:") for e in opps["landing_page"].evidence)
