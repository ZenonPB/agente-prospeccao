from types import SimpleNamespace

from services.prospecting.commercial_analysis_contract import build_commercial_analysis_input


class Profile:
    key = "landing_pages"
    version = "1.0"
    def to_dict(self):
        return {"key": self.key, "version": self.version, "signals": {"positive": ["HAS_CNPJ"]}}


def test_contract_e_grounded_e_versionado_sem_inventar_conclusao():
    lead = SimpleNamespace(
        id="lead-1", company_id="company-1", company_name="Clínica X",
        cnpj="123", category="psicologia", city="Araraquara", state="SP",
        website=None, qualification_score=70, score_vector={"icp_fit": 80},
        evidence=[{"title": "CNPJ ativo", "source": "registry", "epistemic": "FACT",
                   "confidence": 1.0, "observed_at": "2026-09-18T00:00:00Z"}],
        discovery_provenance=None, evidence_score=None,
    )
    opp = SimpleNamespace(
        id="opp-1", score=82, signals_matched=["HAS_CNPJ"],
        signals_missing=["NO_OWN_WEBSITE"], score_breakdown={"confidence_band": "medium"},
    )
    out = build_commercial_analysis_input(
        organization_id="org-1", lead=lead, opportunity=opp, offer_profile=Profile(),
        provider="groq", model="model-x",
    )
    assert out["contract_version"] == "commercial-analysis-input-v1"
    assert out["offer"]["profile"]["signals"]["positive"] == ["HAS_CNPJ"]
    assert out["evidence_context"]["observations"][0]["epistemic"] == "FACT"
    assert out["analysis_metadata"]["provider"] == "groq"
    assert "recommendation" not in out
    assert "why_now" not in out
