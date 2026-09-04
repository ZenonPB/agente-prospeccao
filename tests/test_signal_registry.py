"""Testes do Signal Registry universal + status epistêmico (docs 20 e 29)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.signal_registry import (  # noqa: E402
    EpistemicStatus,
    SignalKey,
    make_signal,
    merge_signals,
    to_statement,
    validate_signal,
)
from services.candidate_pre_scoring_service import (  # noqa: E402
    CandidatePreScoringService,
)


# ---------- make_signal / regras epistêmicas ----------

class TestMakeSignal:
    def test_fact_valido_com_fonte_e_evidencia(self):
        sig = make_signal(SignalKey.HIRING, True, source="company_site",
                          evidence="vaga de torneiro publicada")
        assert sig["epistemic"] == "FACT"
        assert validate_signal(sig) == []

    def test_fact_sem_fonte_e_rebaixado_para_inference(self):
        sig = make_signal(SignalKey.EXPANDING, True, source=None,
                          evidence="obra no fundo")
        assert sig["epistemic"] == "INFERENCE"

    def test_fact_sem_evidencia_e_rebaixado_para_inference(self):
        sig = make_signal(SignalKey.COMPANY_SIZE, "EPP", source="receita")
        assert sig["epistemic"] == "INFERENCE"

    def test_confidence_fora_do_range_rejeitada(self):
        import pytest
        with pytest.raises(ValueError):
            make_signal(SignalKey.HAS_PHONE, True, source="places",
                        evidence="x", confidence=1.5)

    def test_unknown_nao_pode_carregar_valor(self):
        import pytest
        with pytest.raises(ValueError):
            make_signal(SignalKey.COMPANY_SIZE, "MEI", source="x",
                        epistemic=EpistemicStatus.UNKNOWN)

    def test_hypothesis_carrega_evidence_refs(self):
        sig = make_signal(
            SignalKey.HAS_CNC, True, epistemic=EpistemicStatus.HYPOTHESIS,
            evidence_refs=[SignalKey.HAS_CATEGORY, SignalKey.COMPANY_SIZE])
        assert sig["evidence_refs"] == [SignalKey.HAS_CATEGORY, SignalKey.COMPANY_SIZE]

    def test_value_obrigatorio_para_nao_unknown(self):
        import pytest
        with pytest.raises(ValueError):
            make_signal(SignalKey.HAS_PHONE, None, source="places")


# ---------- merge (critério de aceite doc 20) ----------

class TestMergeSignals:
    def _fact(self, key, source, evidence, conf=1.0, value=True):
        return make_signal(key, value, source=source, evidence=evidence,
                           confidence=conf)

    def test_dois_providers_mesmo_sinal_sem_duplicar_semanticamente(self):
        a = self._fact(SignalKey.HAS_PHONE, "google_places", "telefone (11) 99999-0000")
        b = self._fact(SignalKey.HAS_PHONE, "receita", "telefone (11) 99999-0000")
        merged = merge_signals(a, b)
        assert merged["key"] == SignalKey.HAS_PHONE
        assert merged["epistemic"] == "FACT"
        # evidência idêntica (normalizada) não é duplicada
        assert merged["evidence"].count("99999-0000") == 1
        assert merged["contributing_sources"] == ["google_places", "receita"]

    def test_evidencias_distintas_sao_concatenadas(self):
        a = self._fact(SignalKey.HAS_INSTAGRAM, "google_places", "perfil @loja")
        b = self._fact(SignalKey.HAS_INSTAGRAM, "company_site", "link no rodapé")
        merged = merge_signals(a, b)
        assert "perfil @loja" in merged["evidence"]
        assert "link no rodapé" in merged["evidence"]

    def test_confidence_e_o_maximo(self):
        a = self._fact(SignalKey.HIRING, "site", "vagas", conf=0.6)
        b = self._fact(SignalKey.HIRING, "linkedin", "vagas", conf=0.9)
        assert merge_signals(a, b)["confidence"] == 0.9

    def test_fact_com_inference_resulta_em_fact(self):
        a = self._fact(SignalKey.HAS_PHONE, "places", "tel: 111")
        b = make_signal(SignalKey.HAS_PHONE, True, evidence="dedução")
        merged = merge_signals(a, b)
        assert merged["epistemic"] == "FACT"

    def test_keys_diferentes_nao_fundem(self):
        import pytest
        a = self._fact(SignalKey.HAS_PHONE, "places", "x")
        b = self._fact(SignalKey.HAS_INSTAGRAM, "places", "x")
        with pytest.raises(ValueError):
            merge_signals(a, b)

    def test_valores_divergentes_ficam_com_o_de_maior_confianca(self):
        a = self._fact(SignalKey.GOOGLE_RATING, "places", "nota 4.5",
                       conf=0.9, value=4.5)
        b = self._fact(SignalKey.GOOGLE_RATING, "csv", "nota 4.0",
                       conf=0.5, value=4.0)
        merged = merge_signals(a, b)
        assert merged["value"] == 4.5
        assert "4.0" in merged["evidence"] and "4.5" in merged["evidence"]


# ---------- statement (doc 29) e pre-scoring ----------

class TestStatementAndPrescoring:
    def test_to_statement_contrato_do_doc_29(self):
        sig = make_signal(SignalKey.HAS_CNC, True, source="site",
                          evidence="oferece usinagem CNC", confidence=0.8,
                          evidence_refs=[SignalKey.HAS_CATEGORY])
        st = to_statement(sig)
        assert st == {
            "statement": "oferece usinagem CNC",
            "epistemic_status": "FACT",
            "confidence": 0.8,
            "evidence_refs": [SignalKey.HAS_CATEGORY],
        }

    def test_sinais_do_pre_scoring_sao_facts_validos_do_registry(self):
        item = {"name": "Acme", "website": None, "instagram_url": "@acme",
                "phone": "11 1", "rating": 4.5, "rating_count": 30,
                "category": "metalurgia"}
        signals = CandidatePreScoringService().collect_signals(item)
        assert signals, "deve coletar sinais"
        for sig in signals:
            assert validate_signal(sig) == []
            assert sig["epistemic"] == "FACT"
            assert sig["source"] == "google_places"
        keys = {s["key"] for s in signals}
        assert SignalKey.NO_OWN_WEBSITE in keys
        assert SignalKey.HAS_INSTAGRAM in keys
