"""Testes do Decision Maker Resolution (Fase G — consolidação §Fase G).

Seam: `DecisionMakerResolver.resolve(lead_data, profile, sources)`,
       `IdentityResolver.merge(contacts)`, `ContactConfidence.aggregate()`,
       `ContactVerification.verify(contact, sources)`.

Capacidade: dado um lead, retornar pessoa(s) reais (verificadas) ou
estado explícito de falha. Pipeline não inventa pessoas.

Critério: "Pipeline retorna pessoa(s) reais ou um estado explícito de
falha, não apenas roles desejados."
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))


class TestDecisionMakerResolver:
    def test_resolver_retorna_pessoas_reais_ou_falha(self):
        from services.prospecting.decision_maker_resolution import (
            DecisionMakerResolver, PersonContact, ResolutionResult,
        )
        resolver = DecisionMakerResolver()
        # Fontes reais (ex.: Receita Federal)
        sources = {
            "receita_federal": [
                {"name": "Maria Silva", "role": "Sócio-Diretor", "cnpj": "12345678000190"},
            ]
        }
        result = resolver.resolve(
            company_data={"cnpj": "12345678000190"},
            profile={"decision_makers": {"roles": ["plant_engineer"]}},
            sources=sources,
        )
        # Tem pessoa real
        assert result.status in ("resolved", "partial")
        if result.status == "resolved":
            assert len(result.people) >= 1
            assert result.people[0].name == "Maria Silva"
        # SEMPRE tem decisão rastreável
        assert result.audit is not None
        assert "sources_used" in result.audit

    def test_resolver_sem_fontes_retorna_falha_explicita(self):
        from services.prospecting.decision_maker_resolution import (
            DecisionMakerResolver,
        )
        resolver = DecisionMakerResolver()
        result = resolver.resolve(
            company_data={"cnpj": "99999999000199"},
            profile={"decision_makers": {"roles": ["ceo"]}},
            sources={},  # NENHUMA FONTE
        )
        # Estado explícito de falha (consolidação §Fase G)
        assert result.status == "not_found"
        assert result.people == []
        assert "reason" in result.audit
        # Não inventa pessoas
        assert result.people == []

    def test_resolver_usa_buyer_types_do_profile(self):
        """Critério: role resolver por OfferProfile."""
        from services.prospecting.decision_maker_resolution import DecisionMakerResolver
        resolver = DecisionMakerResolver()
        sources = {
            "receita_federal": [
                {"name": "Eng. João", "role": "Engenheiro"},
            ]
        }
        result = resolver.resolve(
            company_data={"cnpj": "111"},
            profile={"decision_makers": {"roles": ["plant_engineer"], "buyer_types": ["TECHNICAL_BUYER"]}},
            sources=sources,
        )
        # roles do profile guiam busca
        assert "plant_engineer" in str(result.audit.get("profile_roles_searched", []))


class TestIdentityResolver:
    def test_merge_contatos_duplicados_por_cpf(self):
        from services.prospecting.decision_maker_resolution import (
            IdentityResolver, PersonContact,
        )
        resolver = IdentityResolver()
        # Mesma pessoa de 2 fontes
        contacts = [
            PersonContact(name="Maria Silva", source="receita_federal", document_cpf="123.456.789-00"),
            PersonContact(name="Maria S.", source="linkedin", document_cpf="123.456.789-00"),
        ]
        merged = resolver.merge(contacts)
        # 2 contatos viram 1
        assert len(merged) == 1
        assert len(merged[0].source_merged) == 2
        assert "receita_federal" in merged[0].source_merged
        assert "linkedin" in merged[0].source_merged

    def test_merge_contatos_diferentes_por_cpf(self):
        from services.prospecting.decision_maker_resolution import (
            IdentityResolver, PersonContact,
        )
        resolver = IdentityResolver()
        contacts = [
            PersonContact(name="Maria", source="receita", document_cpf="111"),
            PersonContact(name="João", source="receita", document_cpf="222"),
        ]
        merged = resolver.merge(contacts)
        assert len(merged) == 2

    def test_merge_sem_cpf_usa_nome_como_heuristica(self):
        from services.prospecting.decision_maker_resolution import (
            IdentityResolver, PersonContact,
        )
        resolver = IdentityResolver()
        contacts = [
            PersonContact(name="Maria Silva", source="receita", email="m@x.com"),
            PersonContact(name="Maria Silva", source="linkedin", email="m@x.com"),
        ]
        # Mesmo email → mesmo CPF implícito
        merged = resolver.merge(contacts)
        assert len(merged) == 1

    def test_merge_com_contradicao_nao_dedupa(self):
        """Se nome bate mas email diverge, mantém separados (evita confusão)."""
        from services.prospecting.decision_maker_resolution import (
            IdentityResolver, PersonContact,
        )
        resolver = IdentityResolver()
        contacts = [
            PersonContact(name="Maria Silva", source="receita", email="m1@x.com"),
            PersonContact(name="Maria Silva", source="linkedin", email="m2@y.com"),
        ]
        merged = resolver.merge(contacts)
        # Email diferente → não dedup
        assert len(merged) == 2


class TestContactConfidence:
    def test_aggregate_de_multiplas_fontes(self):
        from services.prospecting.decision_maker_resolution import (
            ContactConfidence, PersonContact,
        )
        agg = ContactConfidence()
        # Pessoa aparece em 3 fontes com confidências diferentes
        p = PersonContact(
            name="Maria", source="receita", document_cpf="111",
            email="m@x.com",
        )
        sources = [
            {"source": "receita", "confidence": 90},
            {"source": "linkedin", "confidence": 70},
            {"source": "hunter", "confidence": 50},
        ]
        result = agg.aggregate(p, sources)
        # Confidence combinada deve ser maior que qualquer individual
        assert result["confidence"] > 70
        assert result["confidence"] <= 100
        assert result["sources_count"] == 3

    def test_aggregate_com_uma_fonte_mantem_confidence(self):
        from services.prospecting.decision_maker_resolution import (
            ContactConfidence, PersonContact,
        )
        agg = ContactConfidence()
        p = PersonContact(name="X", source="receita", document_cpf="111")
        result = agg.aggregate(p, [{"source": "receita", "confidence": 60}])
        assert result["confidence"] == 60

    def test_aggregate_sem_fontes_retorna_zero(self):
        from services.prospecting.decision_maker_resolution import (
            ContactConfidence, PersonContact,
        )
        agg = ContactConfidence()
        p = PersonContact(name="X", source="receita")
        result = agg.aggregate(p, [])
        assert result["confidence"] == 0


class TestContactVerification:
    def test_email_verificado_via_mx(self):
        from services.prospecting.decision_maker_resolution import (
            ContactVerification, PersonContact,
        )
        verifier = ContactVerification()
        p = PersonContact(
            name="Maria", source="receita", email="m@alpha.com",
            document_cpf="111",
        )
        result = verifier.verify(p, mock_mx_check=lambda d: d == "alpha.com")
        # Email + MX confirmado → verificado
        assert result["email_verified"] is True
        assert result["identity_verified"] is True

    def test_email_heuristico_nao_e_verificado(self):
        """Heurística (infer_email_pattern) nunca cruza gate de outreach."""
        from services.prospecting.decision_maker_resolution import (
            ContactVerification, PersonContact,
        )
        verifier = ContactVerification()
        p = PersonContact(
            name="Maria", source="heuristic", email="m.silva@alpha.com",
            document_cpf=None,  # sem CPF → não verifica
        )
        result = verifier.verify(p, mock_mx_check=lambda d: True)
        # Email heurístico sem CPF → não verificado
        assert result["email_verified"] is False

    def test_sem_email_nao_verifica(self):
        from services.prospecting.decision_maker_resolution import (
            ContactVerification, PersonContact,
        )
        verifier = ContactVerification()
        p = PersonContact(name="X", source="receita", document_cpf="111")
        result = verifier.verify(p, mock_mx_check=lambda d: True)
        assert result["email_verified"] is False
        assert result["identity_verified"] is True  # só tem CPF, sem email


class TestDecisionMakerResolutionIntegration:
    """Critério Fase G: pipeline retorna pessoa(s) reais ou falha explícita."""

    def test_pipeline_completo_retorna_pessoa_real(self):
        from services.prospecting.decision_maker_resolution import (
            DecisionMakerResolver, IdentityResolver, ContactConfidence, ContactVerification,
        )
        from services.prospecting import OfferProfile
        from services.prospecting.default_profiles import get_default_registry

        # 1) Oferta (industrial → plant_engineer)
        registry = get_default_registry()
        profile = registry.get("mechanical_project")

        # 2) Fontes reais: Receita devolve 2 pessoas
        sources = {
            "receita_federal": [
                {"name": "João Silva", "role": "Sócio-Diretor", "document_cpf": "111.111.111-11"},
                {"name": "Maria Souza", "role": "Engenheiro", "document_cpf": "222.222.222-22"},
            ]
        }
        # 3) Resolver
        resolver = DecisionMakerResolver()
        result = resolver.resolve(
            company_data={"cnpj": "12345678000190"},
            profile={
                "decision_makers": profile.decision_makers,
            },
            sources=sources,
        )
        assert result.status == "resolved"
        # 4) Identity resolution (sem duplicatas, mantém 2)
        identity = IdentityResolver()
        people = identity.merge(result.people)
        # 5) Confidence agregada
        conf = ContactConfidence()
        for p in people:
            agg = conf.aggregate(p, [{"source": "receita", "confidence": 80}])
            assert agg["confidence"] > 0
        # 6) Verificação (sem email real aqui)
        verif = ContactVerification()
        for p in people:
            v = verif.verify(p, mock_mx_check=lambda d: True)
            # Sem email → verification_status = "no_email"
            assert "verification_status" in v

    def test_pipeline_retorna_falha_explicita(self):
        """Sem fontes disponíveis → failure explícito, não inventa."""
        from services.prospecting.decision_maker_resolution import DecisionMakerResolver
        resolver = DecisionMakerResolver()
        result = resolver.resolve(
            company_data={"cnpj": "x"},
            profile={"decision_makers": {"roles": ["ceo"]}},
            sources={},  # nada
        )
        # FAIL explícito
        assert result.status == "not_found"
        assert result.people == []
        assert "reason" in result.audit
        assert "not_found" in result.audit["reason"].lower() or "no_sources" in result.audit["reason"].lower()
