"""Testes do Contact Provider Registry (Fase 3 — docs 37, 38, 39, 44, 46).

Seam: `register_provider`, `get_provider`, `list_providers`,
       `infer_email_pattern`, `cascade_contact_search`,
       `domain_first_person_search`, `classify_qsa_role`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.contact_provider_registry import (  # noqa: E402
    register_provider,
    get_provider,
    list_providers,
    infer_email_pattern,
    cascade_contact_search,
    domain_first_person_search,
    classify_qsa_role,
)


class TestRegistry:
    def test_list_providers_retorna_lista(self):
        providers = list_providers()
        assert isinstance(providers, list)
        # Pode incluir 'hunter' se HUNTER_API_KEY configurado (conftest)

    def test_get_provider_inexistente_retorna_none(self):
        assert get_provider("provider_inexistente_xyz") is None

    def test_register_provider_anonimo(self):
        class _P:
            name = "test_provider_anon_xyz"
            quota_used = 0
            quota_max = 100
            def find_people(self, *a, **kw): return []
        register_provider(_P())
        assert get_provider("test_provider_anon_xyz") is not None


class TestInferEmailPattern:
    def test_nome_completo_gera_primeiro_ponto_ultimo(self):
        r = infer_email_pattern("alpha.com", "João Silva", verify=False)
        assert r["candidate"] == "joao.silva@alpha.com"
        assert r["pattern"] == "{first}.{last}@{domain}"

    def test_acentos_sao_normalizados(self):
        """Consolidação §27: nomes com acento viram ASCII (não joão@, mas joao@)."""
        r = infer_email_pattern("alpha.com", "Conceição Müller", verify=False)
        assert "ç" not in r["candidate"]
        assert "ã" not in r["candidate"]
        assert "ü" not in r["candidate"]

    def test_nome_unico_nao_gera_pattern(self):
        r = infer_email_pattern("alpha.com", "Cher", verify=False)
        assert r["candidate"] is None
        assert r["verification_status"] == "needs_full_name"

    def test_sem_domain_nao_gera_pattern(self):
        r = infer_email_pattern("", "João Silva", verify=False)
        assert r["candidate"] is None

    def test_verify_flag_muda_status(self):
        r1 = infer_email_pattern("alpha.com", "João Silva", verify=False)
        r2 = infer_email_pattern("alpha.com", "João Silva", verify=True)
        assert r1["verification_status"] == "inferred"
        assert r2["verification_status"] == "pending_verification"


class TestCascadeContactSearch:
    def test_com_cnpj_usa_receita_qsa(self):
        r = cascade_contact_search(
            lead_data={"cnpj": "12345678000190"},
            target_roles=["ceo"],
        )
        steps = [s["step"] for s in r["cascaded_steps"]]
        assert "receita_qsa" in steps

    def test_sem_cnpj_pula_receita(self):
        r = cascade_contact_search(
            lead_data={"cnpj": None, "domain": "alpha.com"},
            target_roles=["ceo"],
        )
        receita_step = next(s for s in r["cascaded_steps"] if s["step"] == "receita_qsa")
        assert receita_step["used"] is False

    def test_max_steps_2_para_no_passo_2(self):
        r = cascade_contact_search(
            lead_data={"cnpj": "12345678000190"},
            target_roles=["ceo"],
            max_steps=2,
        )
        assert r["stopped_at"] == 2


class TestDomainFirstPersonSearch:
    def test_com_domain_retorna_domain_first(self):
        r = domain_first_person_search("alpha.com", ["CEO"])
        assert r["strategy"] == "domain_first"
        assert r["domain"] == "alpha.com"

    def test_sem_domain_usa_name_location_fallback(self):
        r = domain_first_person_search("", ["CEO"])
        assert r["strategy"] == "name_location_fallback"


class TestClassifyQsaRole:
    def test_socio_diretor_e_economic_buyer(self):
        assert classify_qsa_role("Sócio-Diretor") == "ECONOMIC_BUYER"

    def test_administrador_e_legal(self):
        assert classify_qsa_role("Administrador") == "LEGAL_DECISION_MAKER"

    def test_role_generico_e_other(self):
        assert classify_qsa_role("Gerente de Operações") == "OTHER"
