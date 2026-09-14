"""Capability de Event Discovery por oferta efetiva (seam: offer_supports_event_discovery).

A UI da campanha só oferece prospecção por eventos quando o OfferProfile
efetivo do workspace declara o provider `event_search` na estratégia de
discovery — nunca por heurística de texto (nome da campanha/oferta).

Critérios:
- chave vazia/ausente, perfil inexistente ou sem `event_search` → False;
- `trophies` (único perfil base com `event_search`) → True;
- overlay publicado pelo workspace também vale (registry efetivo).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))


class TestOfferSupportsEventDiscovery:
    def test_trophies_suporta_eventos(self):
        from services.prospecting.effective_offer_registry import offer_supports_event_discovery
        assert offer_supports_event_discovery(None, None, "trophies") is True

    def test_landing_page_nao_suporta_eventos(self):
        from services.prospecting.effective_offer_registry import offer_supports_event_discovery
        assert offer_supports_event_discovery(None, None, "landing_page") is False

    def test_outros_perfis_base_nao_suportam_eventos(self):
        from services.prospecting.effective_offer_registry import offer_supports_event_discovery
        for key in ("mechanical_project", "technical_drawing", "machine_manual"):
            assert offer_supports_event_discovery(None, None, key) is False

    def test_chave_ausente_ou_desconhecida_nao_suporta(self):
        from services.prospecting.effective_offer_registry import offer_supports_event_discovery
        assert offer_supports_event_discovery(None, None, None) is False
        assert offer_supports_event_discovery(None, None, "") is False
        assert offer_supports_event_discovery(None, None, "oferta_inexistente") is False
