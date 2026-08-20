"""Testes do bloco 2 — vertentes flexíveis (enriquecimento + cadência).

Cobre as funções puras adicionadas:
- `_normalize_cadence_days` (fallback seguro para calendários inválidos)
- validação dos campos `enrichment_steps`/`cadence_schedule` na rota de templates
- `resolve_enrichment_steps` (fontes de informação por vertical)
- `extract_business_facts` com dados da Receita (CNAE + porte)
"""
import pytest

from src.services.cadence_service import _normalize_cadence_days, DEFAULT_CADENCE_DAYS
from src.routes.scoring_templates import (
    CreateScoringTemplateRequest,
    PatchScoringTemplateRequest,
)
from services.scoring_service import extract_business_facts
from services.enrichment_orchestrator import (
    resolve_enrichment_steps,
    DEFAULT_ENRICHMENT_STEPS,
    ENRICHMENT_STEP_KEYS,
)


# ---------------------------------------------------------------- cadence days


class TestNormalizeCadenceDays:
    def test_default_quando_ausente(self):
        assert _normalize_cadence_days(None) == [0, 3, 7, 14]
        assert DEFAULT_CADENCE_DAYS == [0, 3, 7, 14]

    def test_ciclo_longo_valido(self):
        assert _normalize_cadence_days([0, 7, 30, 60]) == [0, 7, 30, 60]

    def test_tamanho_diferente_de_4_cai_no_default(self):
        assert _normalize_cadence_days([0, 7]) == [0, 3, 7, 14]
        assert _normalize_cadence_days([0, 7, 30, 60, 90]) == [0, 3, 7, 14]

    def test_dia_negativo_cai_no_default(self):
        assert _normalize_cadence_days([0, 7, -1, 60]) == [0, 3, 7, 14]

    def test_nao_inteiro_cai_no_default(self):
        assert _normalize_cadence_days(["0", 7, 30, 60]) == [0, 3, 7, 14]


# ---------------------------------------------------- validation dos templates


class TestTemplateScheduleValidation:
    def test_create_com_enrichment_steps_validos(self):
        body = CreateScoringTemplateRequest(
            service_label="Engenharia Mecânica",
            enrichment_steps=["cnpj_receita", "business_social"],
        )
        assert body.enrichment_steps == ["cnpj_receita", "business_social"]

    def test_create_rejeita_fonte_desconhecida(self):
        with pytest.raises(ValueError):
            CreateScoringTemplateRequest(
                service_label="X",
                enrichment_steps=["hacker", "business_social"],
            )

    def test_create_com_cadence_schedule_valido(self):
        body = CreateScoringTemplateRequest(
            service_label="X",
            cadence_schedule=[0, 7, 30, 60],
        )
        assert body.cadence_schedule == [0, 7, 30, 60]

    def test_create_rejeita_schedule_com_tamanho_errado(self):
        with pytest.raises(ValueError):
            CreateScoringTemplateRequest(service_label="X", cadence_schedule=[0, 7])

    def test_create_rejeita_dia_negativo(self):
        with pytest.raises(ValueError):
            CreateScoringTemplateRequest(service_label="X", cadence_schedule=[0, 7, -1, 14])

    def test_patch_aceita_limpeza_com_null(self):
        body = PatchScoringTemplateRequest(service_label="Y")
        assert body.enrichment_steps is None

    def test_patch_rejeita_schedule_invalido(self):
        with pytest.raises(ValueError):
            PatchScoringTemplateRequest(cadence_schedule=[1, 2])


# ---------------------------------------------------- enrichment steps


class TestResolveEnrichmentSteps:
    def test_sem_template_usa_todas_as_fontes(self):
        assert resolve_enrichment_steps(None) == DEFAULT_ENRICHMENT_STEPS

    def test_declarado_explícito(self):
        tmpl = {
            "enrichment_steps": ["cnpj_receita", "business_social"],
            "requires_technical_report": False,
        }
        assert resolve_enrichment_steps(tmpl) == ["cnpj_receita", "business_social"]

    def test_declarado_filtra_fontes_desconhecidas(self):
        tmpl = {"enrichment_steps": ["cnpj_receita", "sei_lá", "technical_site"]}
        out = resolve_enrichment_steps(tmpl)
        assert set(out).issubset(ENRICHMENT_STEP_KEYS)
        assert "sei_lá" not in out

    def test_fallback_por_flags_tecnico_sim(self):
        tmpl = {"requires_technical_report": True, "requires_business_data": True}
        assert resolve_enrichment_steps(tmpl) == DEFAULT_ENRICHMENT_STEPS

    def test_fallback_por_flags_industrial(self):
        tmpl = {"requires_technical_report": False, "requires_business_data": True}
        assert resolve_enrichment_steps(tmpl) == ["cnpj_receita", "business_social"]

    def test_fallback_sem_flags_explicitos(self):
        # Template sem flags (dict antigo) assume os defaults do seed.
        assert resolve_enrichment_steps({}) == DEFAULT_ENRICHMENT_STEPS


# ---------------------------------------------------------------- business facts


class TestExtractBusinessFactsReceita:
    def test_sem_dados_receita_nao_injeta_facts(self):
        facts = extract_business_facts(
            company_name="Metalúrgica Brasil",
            category="metalúrgica",
            city="Sorocaba",
            state="SP",
            website=None,
        )
        text = "\n".join(facts)
        assert "Atividade econômica" not in text
        assert "Porte/Estrutura" not in text

    def test_com_cnae_e_porte_injeta_facts(self):
        facts = extract_business_facts(
            company_name="Metalúrgica Brasil",
            category="metalúrgica",
            city="Sorocaba",
            state="SP",
            website=None,
            cnae_info="259933 - Fabricação de máquinas",
            company_size_info="porte: MÉDIO; idade: 22 anos",
        )
        text = "\n".join(facts)
        assert "Atividade econômica (CNAE/Receita): 259933 - Fabricação de máquinas" in text
        assert "Porte/Estrutura cadastral: porte: MÉDIO; idade: 22 anos" in text

    def test_cnae_sem_codigo(self):
        facts = extract_business_facts(
            company_name="A", category="", city="", state="",
            website=None,
            cnae_info="Fabricação de máquinas",
            company_size_info=None,
        )
        assert any("Fabricação de máquinas" in f for f in facts)