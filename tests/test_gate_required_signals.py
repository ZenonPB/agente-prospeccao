"""Fase 2.x — gate distingue 'candidato fraco' de 'dados insuficientes'.

O gate v0 só sabia de score >= threshold. Isso descartava silenciosamente
dois tipos muito diferentes de candidato:

  (a) 'observado, mas baixo' — descartado por limite
  (b) 'sinal decisivo não foi coletado' — não temos base para decidir

(b) é o caso típico de verticais cujo fit real vem do pós-gate (Engenharia
precisa de CNAE industrial; ERP precisa saber se a empresa tem sistema).
Não dá pra o gate declarar 'descartado' sem os dados que ele não tem.

Contrato novo: `discovery_status` ∈ {QUALIFIES, INSUFFICIENT_DATA, DISQUALIFIES}.
Templates declaram `prescoring_config.required_signals` (opcional). Se algum
deles não foi observado, o gate marca INSUFFICIENT_DATA e o comportamento
fica opt-in via `prescoring_config.on_insufficient_data` ∈ {discard, promote}.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from seeds.scoring_templates import DEFAULT_TEMPLATES  # noqa: E402
from services.candidate_pre_scoring_service import CandidatePreScoringService  # noqa: E402
from services.prospecting_profile_service import (  # noqa: E402
    resolve_prospecting_profile,
)
from services.signal_registry import SignalKey  # noqa: E402

SVC = CandidatePreScoringService()


def _seed_template(label):
    matches = [t for t in DEFAULT_TEMPLATES if t["service_label"].startswith(label)]
    assert len(matches) == 1
    return matches[0]


def _score(label, item, prescoring_overrides=None):
    tmpl = dict(_seed_template(label))
    if prescoring_overrides:
        cfg = dict(tmpl.get("prescoring_config") or {})
        cfg.update(prescoring_overrides)
        tmpl["prescoring_config"] = cfg
    profile = resolve_prospecting_profile(tmpl)
    return SVC.score_candidate(item, profile), profile


class TestGateV1Fronteira:
    def test_score_candidate_retorna_discovery_status(self):
        item = {"name": "x", "phone": "16 1", "rating": 4.5}
        scored, _ = _score("Engenharia Mecânica", item)
        assert "discovery_status" in scored
        assert scored["discovery_status"] in (
            "QUALIFIES", "INSUFFICIENT_DATA", "DISQUALIFIES")

    def test_score_com_default_mantem_qualifies_ou_disqualifies(self):
        item = {"name": "x", "phone": "16 1", "rating": 4.5, "rating_count": 30}
        scored, _ = _score("Landing Pages", item)
        assert scored["discovery_status"] in ("QUALIFIES", "DISQUALIFIES")

    def test_eligible_for_enrichment_continua_sendo_derivado(self):
        item = {"name": "x", "phone": "16 1", "rating": 4.5, "rating_count": 30}
        scored, _ = _score("Landing Pages", item)
        assert scored["eligible_for_enrichment"] is (
            scored["discovery_status"] == "QUALIFIES")

    def test_required_signals_nao_observado_vira_insufficient(self):
        item = {"name": "x", "phone": "16 1", "rating": 4.5, "rating_count": 30}
        scored, _ = _score(
            "Engenharia Mecânica",
            item,
            prescoring_overrides={
                "required_signals": [SignalKey.CNAE],
                "on_insufficient_data": "discard",
            },
        )
        assert scored["discovery_status"] == "INSUFFICIENT_DATA", scored
        assert scored["eligible_for_enrichment"] is False

    def test_required_signals_atendido_e_score_alto_qualifies(self):
        item = {"name": "x", "phone": "16 1", "rating": 4.8, "rating_count": 100,
                "cnae": "25.31-2"}
        scored, _ = _score(
            "Engenharia Mecânica",
            item,
            prescoring_overrides={"required_signals": [SignalKey.CNAE]},
        )
        assert scored["discovery_status"] == "QUALIFIES", scored

    def test_insufficient_data_mas_score_alto_pode_promote(self):
        item = {"name": "x", "phone": "16 1", "rating": 4.8, "rating_count": 100}
        scored, _ = _score(
            "Engenharia Mecânica",
            item,
            prescoring_overrides={
                "required_signals": [SignalKey.CNAE],
                "on_insufficient_data": "promote",
            },
        )
        assert scored["discovery_status"] == "INSUFFICIENT_DATA"
        assert scored["eligible_for_promotion_on_insufficient"] is True


class TestSelectCandidatesComInsuficiencia:
    def test_default_discard_separa_insufficient(self):
        svc = CandidatePreScoringService()
        tmpl = dict(_seed_template("Engenharia Mecânica"))
        cfg = dict(tmpl.get("prescoring_config") or {})
        cfg["required_signals"] = [SignalKey.CNAE]
        cfg["on_insufficient_data"] = "discard"
        tmpl["prescoring_config"] = cfg
        profile = resolve_prospecting_profile(tmpl)

        items = [
            {"name": "fraco", "phone": None, "rating": None,
             "rating_count": None, "cnae": "25.31-2"},
            {"name": "forte_sem_cnae", "phone": "16 1", "rating": 4.8,
             "rating_count": 100},
            {"name": "forte_com_cnae", "phone": "16 1", "rating": 4.8,
             "rating_count": 100, "cnae": "25.31-2"},
        ]
        selected, stats = svc.select_candidates(items, profile)
        assert stats["discarded"] == 2, stats
        assert stats["below_threshold"] == 1, stats
        assert stats["insufficient_data"] == 1, stats
        assert len(selected) == 1
        assert selected[0]["name"] == "forte_com_cnae"

    def test_promote_mantem_insuficientes_no_fluxo(self):
        svc = CandidatePreScoringService()
        tmpl = dict(_seed_template("Engenharia Mecânica"))
        cfg = dict(tmpl.get("prescoring_config") or {})
        cfg["required_signals"] = [SignalKey.CNAE]
        cfg["on_insufficient_data"] = "promote"
        tmpl["prescoring_config"] = cfg
        profile = resolve_prospecting_profile(tmpl)

        items = [
            {"name": "fraco", "phone": None, "rating": None,
             "rating_count": None, "cnae": "25.31-2"},
            {"name": "forte_sem_cnae", "phone": "16 1", "rating": 4.8,
             "rating_count": 100},
        ]
        selected, stats = svc.select_candidates(items, profile)
        assert stats["insufficient_data_promoted"] == 1, stats
        assert stats["discarded"] == 1, stats
        names = {it["name"] for it in selected}
        assert "forte_sem_cnae" in names
        promoted = [s for s in selected
                    if s.get("discovery_status") == "INSUFFICIENT_DATA"]
        assert len(promoted) == 1

    def test_required_signals_vazio_ou_ausente_comportamento_atual(self):
        svc = CandidatePreScoringService()
        profile = resolve_prospecting_profile(_seed_template("Landing Pages"))
        _, stats = svc.select_candidates([{"name": "fraco"}], profile)
        assert stats["insufficient_data"] == 0
        assert stats["below_threshold"] == 1
