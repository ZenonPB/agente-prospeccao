"""Contrato OfferProfile → CampaignScoringTemplate (regressão do AttributeError).

Causa raiz: `pipeline_worker` sobrescrevia os critérios estruturados do
template (`[{label, description, weight_hint}]`) pelas chaves canônicas do
OfferProfile (`["NO_OWN_WEBSITE", ...]`) e o `icp` (dict) no lugar de
`context_signals` (lista) — `_format_signals` chamava `.get()` em str.

Seams: `merge_template_signals`, `adapt_offer_signals`,
`adapt_icp_to_context` (adapter) e `AIScoringService._format_signals`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

RICH_TEMPLATE = {
    "service_label": "Landing Pages",
    "positive_signals": [
        {"label": "Sem site próprio", "description": "Empresa sem website", "weight_hint": "high"},
    ],
    "negative_signals": [
        {"label": "Site robusto", "description": "Presença forte", "weight_hint": "medium"},
    ],
    "context_signals": [
        {"label": "Segmentos: clínicas", "description": "", "weight_hint": "medium"},
    ],
}

OFFER_SIGNALS = {
    "positive": ["NO_OWN_WEBSITE", "HAS_INSTAGRAM"],
    "negative": ["HAS_OWN_WEBSITE_INSTITUTIONAL"],
    "weights": {"NO_OWN_WEBSITE": 25, "HAS_INSTAGRAM": 12},
}

ICP = {
    "company_sizes": ["ME", "PE"],
    "segments": ["psicologia", "clínicas"],
    "cnaes": ["8630-5/04"],
    "exclusions": ["enterprise com site"],
    "geography": {"country": "BR", "states": ["SP"]},
}


class TestMergePreservesRichTemplate:
    def test_sinais_ricos_nao_sao_destruidos(self):
        from services.offer_signal_adapter import merge_template_signals
        merged = merge_template_signals(dict(RICH_TEMPLATE), OFFER_SIGNALS, ICP)
        assert merged["positive_signals"] == RICH_TEMPLATE["positive_signals"]
        assert merged["negative_signals"] == RICH_TEMPLATE["negative_signals"]
        assert merged["context_signals"] == RICH_TEMPLATE["context_signals"]

    def test_template_vazio_recebe_criterios_adaptados(self):
        from services.offer_signal_adapter import merge_template_signals
        merged = merge_template_signals({}, OFFER_SIGNALS, ICP)
        positives = merged["positive_signals"]
        assert all(isinstance(s, dict) for s in positives)
        assert positives[0]["label"] == "Não possui site próprio"
        assert positives[0]["weight_hint"] == "high"
        assert merged["negative_signals"][0]["label"] == "Site institucional robusto (presença forte)"
        contexts = merged["context_signals"]
        assert isinstance(contexts, list)
        assert any("psicologia" in (c.get("label") or "") for c in contexts)

    def test_chave_desconhecida_e_ignorada_sem_quebrar(self):
        from services.offer_signal_adapter import merge_template_signals
        merged = merge_template_signals({}, {"positive": ["SINAL_QUE_NAO_EXISTE"], "negative": []}, None)
        assert merged["positive_signals"] == []
        assert merged["negative_signals"] == []


class TestFormatSignalsDefensive:
    def test_strings_nao_derrubam_formatacao(self):
        from services.scoring_service import _format_signals
        out = _format_signals(["NO_OWN_WEBSITE", {"label": "Ok", "description": "d", "weight_hint": "high"}], "Positivos")
        assert "Ok" in out
        assert "NO_OWN_WEBSITE" not in out

    def test_entrada_nao_lista_nao_quebra(self):
        from services.scoring_service import _format_signals
        out = _format_signals({"a": 1}, "Positivos")  # type: ignore[arg-type]
        assert "(nenhum)" in out

    def test_dict_valido_formata_normalmente(self):
        from services.scoring_service import _format_signals
        out = _format_signals([{"label": "Sem site", "description": "Empresa sem website", "weight_hint": "high"}], "Positivos")
        assert "[high] Sem site: Empresa sem website" in out


class TestWeightMapping:
    def test_pesos_do_perfil_viram_hint(self):
        from services.offer_signal_adapter import weight_hint_for
        assert weight_hint_for(25) == "high"
        assert weight_hint_for(12) == "medium"
        assert weight_hint_for(5) == "low"
        assert weight_hint_for(None) == "medium"
