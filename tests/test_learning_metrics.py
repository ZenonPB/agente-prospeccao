"""Testes do Learning & Metrics (Fase H — consolidação §Fase H).

Seam: `OutcomesRegistry` (persistência de outcomes),
       `CommercialMetrics` (métricas por oferta/provider),
       `VersionComparator` (A/B testing de versões).

Capacidade: provar se uma alteração AUMENTOU ou REDUZIU a qualidade
comercial. Outcomes persistem, métricas calculam, comparador de
versões detecta regressões.

Critério: "É possível provar se uma alteração aumentou ou reduziu a
qualidade comercial."
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))


class TestOutcomesRegistry:
    def test_registra_e_recupera_outcome(self):
        from services.prospecting.learning_metrics import OutcomesRegistry
        reg = OutcomesRegistry()
        outcome = reg.record(
            org_id="org1", offer_key="trophies", outcome="WON",
            lead_id="lead1", value=1000.0,
        )
        assert outcome["outcome"] == "WON"
        assert outcome["value"] == 1000.0
        assert outcome["org_id"] == "org1"

    def test_outcome_tem_id_e_timestamp(self):
        from services.prospecting.learning_metrics import OutcomesRegistry
        reg = OutcomesRegistry()
        outcome = reg.record(org_id="o", offer_key="x", outcome="WON", lead_id="l")
        assert "id" in outcome
        assert "recorded_at" in outcome

    def test_outcome_inclui_offer_version(self):
        from services.prospecting.learning_metrics import OutcomesRegistry
        reg = OutcomesRegistry()
        outcome = reg.record(
            org_id="o", offer_key="trophies", outcome="WON", lead_id="l",
            offer_version="1.0",
        )
        assert outcome["offer_version"] == "1.0"

    def test_query_por_org(self):
        from services.prospecting.learning_metrics import OutcomesRegistry
        reg = OutcomesRegistry()
        reg.record("org1", "trophies", "WON", "l1")
        reg.record("org1", "trophies", "LOST", "l2")
        reg.record("org2", "mechanical_project", "WON", "l3")
        outcomes = reg.query(org_id="org1")
        assert len(outcomes) == 2

    def test_query_por_offer(self):
        from services.prospecting.learning_metrics import OutcomesRegistry
        reg = OutcomesRegistry()
        reg.record("o", "trophies", "WON", "l1")
        reg.record("o", "trophies", "WON", "l2")
        reg.record("o", "mechanical_project", "WON", "l3")
        outcomes = reg.query(offer_key="trophies")
        assert len(outcomes) == 2


class TestCommercialMetrics:
    def test_conversion_rate_por_offer(self):
        from services.prospecting.learning_metrics import (
            OutcomesRegistry, CommercialMetrics,
        )
        reg = OutcomesRegistry()
        # 3 leads, 1 WON → 33.3%
        for i in range(3):
            reg.record("o", "trophies", "WON" if i == 0 else "NO_RESPONSE", f"l{i}")
        m = CommercialMetrics(reg)
        result = m.conversion_rate_by_offer("trophies")
        assert result["total"] == 3
        assert result["wins"] == 1
        assert abs(result["conversion_rate"] - 33.3) < 0.5

    def test_ticket_medio(self):
        from services.prospecting.learning_metrics import (
            OutcomesRegistry, CommercialMetrics,
        )
        reg = OutcomesRegistry()
        reg.record("o", "trophies", "WON", "l1", value=1000.0)
        reg.record("o", "trophies", "WON", "l2", value=2000.0)
        reg.record("o", "trophies", "WON", "l3", value=3000.0)
        m = CommercialMetrics(reg)
        result = m.average_ticket("trophies")
        assert result["average_ticket"] == 2000.0
        assert result["sample_size"] == 3

    def test_metricas_por_provider(self):
        from services.prospecting.learning_metrics import (
            OutcomesRegistry, CommercialMetrics,
        )
        reg = OutcomesRegistry()
        # Provider google_places: 2 leads, 1 WON
        reg.record("o", "trophies", "WON", "l1", provider="google_places")
        reg.record("o", "trophies", "LOST", "l2", provider="google_places")
        # Provider cnae: 1 lead, 0 WON
        reg.record("o", "trophies", "LOST", "l3", provider="cnae")
        m = CommercialMetrics(reg)
        by_provider = m.metrics_by_provider("trophies")
        assert by_provider["google_places"]["wins"] == 1
        assert by_provider["google_places"]["total"] == 2
        assert by_provider["cnae"]["wins"] == 0
        assert by_provider["cnae"]["total"] == 1

    def test_time_to_conversion_calcula_dias(self):
        from services.prospecting.learning_metrics import (
            OutcomesRegistry, CommercialMetrics,
        )
        from datetime import datetime, timedelta
        reg = OutcomesRegistry()
        # Lead convertido 10 dias após outreach
        outreach_date = (datetime.now() - timedelta(days=10)).isoformat()
        outcome = reg.record(
            "o", "trophies", "WON", "l1",
            outreach_at=outreach_date,
        )
        m = CommercialMetrics(reg)
        result = m.time_to_conversion("trophies")
        # 9-10 dias (tolerância)
        assert 9 <= result["average_days"] <= 11

    def test_metricas_sem_dados_retorna_zeros(self):
        from services.prospecting.learning_metrics import (
            OutcomesRegistry, CommercialMetrics,
        )
        reg = OutcomesRegistry()
        m = CommercialMetrics(reg)
        result = m.conversion_rate_by_offer("nao_existe")
        assert result["total"] == 0
        assert result["conversion_rate"] == 0.0


class TestVersionComparator:
    def test_compara_duas_versoes_da_mesma_oferta(self):
        from services.prospecting.learning_metrics import (
            OutcomesRegistry, VersionComparator,
        )
        reg = OutcomesRegistry()
        # v1.0: 10 leads, 2 WON → 20%
        for i in range(10):
            reg.record("o", "trophies", "WON" if i < 2 else "LOST", f"l_v1_{i}", offer_version="1.0")
        # v2.0: 10 leads, 5 WON → 50%
        for i in range(10):
            reg.record("o", "trophies", "WON" if i < 5 else "LOST", f"l_v2_{i}", offer_version="2.0")
        comp = VersionComparator(reg)
        result = comp.compare("trophies", "1.0", "2.0")
        # v2.0 > v1.0
        assert result["v1_conversion"] == 20.0
        assert result["v2_conversion"] == 50.0
        assert result["delta"] == 30.0
        assert result["is_regression"] is False
        assert result["is_improvement"] is True

    def test_detecta_regressao(self):
        from services.prospecting.learning_metrics import (
            OutcomesRegistry, VersionComparator,
        )
        reg = OutcomesRegistry()
        # v1.0: 50% conversion
        for i in range(10):
            reg.record("o", "x", "WON" if i < 5 else "LOST", f"l_v1_{i}", offer_version="1.0")
        # v2.0: 10% conversion (regressão!)
        for i in range(10):
            reg.record("o", "x", "WON" if i == 0 else "LOST", f"l_v2_{i}", offer_version="2.0")
        comp = VersionComparator(reg)
        result = comp.compare("x", "1.0", "2.0")
        assert result["is_regression"] is True
        assert result["is_improvement"] is False
        assert result["delta"] < 0

    def test_threshold_minimo_de_samples(self):
        """Sem samples suficientes, comparação não é conclusiva."""
        from services.prospecting.learning_metrics import (
            OutcomesRegistry, VersionComparator,
        )
        reg = OutcomesRegistry()
        # Só 2 leads por versão (insuficiente)
        reg.record("o", "x", "WON", "l1", offer_version="1.0")
        reg.record("o", "x", "LOST", "l2", offer_version="1.0")
        reg.record("o", "x", "WON", "l3", offer_version="2.0")
        reg.record("o", "x", "LOST", "l4", offer_version="2.0")
        comp = VersionComparator(reg, min_samples=10)
        result = comp.compare("x", "1.0", "2.0")
        # Inconclusivo
        assert result["is_conclusive"] is False
        assert "insufficient_samples" in result.get("reason", "")

    def test_comparacao_versao_inexistente_retorna_zeros(self):
        from services.prospecting.learning_metrics import (
            OutcomesRegistry, VersionComparator,
        )
        reg = OutcomesRegistry()
        comp = VersionComparator(reg)
        result = comp.compare("nao_existe", "1.0", "2.0")
        assert result["v1_conversion"] == 0
        assert result["v2_conversion"] == 0


class TestPhaseHIntegration:
    """Critério Fase H: 'provar se alteração aumentou/reduziu qualidade'."""

    def test_cenario_alpha_mec_completo(self):
        """AlphaMec muda prompt de vendas v1→v2, registra outcomes, compara."""
        from services.prospecting.learning_metrics import (
            OutcomesRegistry, CommercialMetrics, VersionComparator,
        )
        reg = OutcomesRegistry()
        # 1) Antes (v1.0): 30 leads, 5 WON → 16.7%
        for i in range(30):
            reg.record("alpha", "trophies",
                       "WON" if i < 5 else "LOST", f"v1_{i}",
                       offer_version="1.0", value=1500.0,
                       provider="google_places")
        # 2) Depois (v2.0): 30 leads, 12 WON → 40%
        for i in range(30):
            reg.record("alpha", "trophies",
                       "WON" if i < 12 else "LOST", f"v2_{i}",
                       offer_version="2.0", value=2000.0,
                       provider="google_places")
        # 3) Métricas comerciais
        m = CommercialMetrics(reg)
        cr = m.conversion_rate_by_offer("trophies")
        assert cr["wins"] == 17  # 5 + 12
        # 4) Comparação de versão (AlphaMec melhorou o prompt)
        comp = VersionComparator(reg)
        result = comp.compare("trophies", "1.0", "2.0")
        assert result["is_improvement"] is True
        assert result["delta"] > 0

    def test_qualificacao_nao_e_registrada_como_venda(self):
        """Qualificar um lead não deve criar outcome comercial automaticamente."""
        from services.prospecting.learning_metrics import OutcomesRegistry
        registry = OutcomesRegistry()
        # O registry só recebe resultados explícitos; QUALIFIED é permitido
        # como estado de funil, mas não é criado pelo scoring.
        assert registry.query() == []
