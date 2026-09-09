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

    def test_resolver_pode_resolver_sem_cpf_com_evidencias_concordantes(self):
        from services.prospecting.decision_maker_resolution import DecisionMakerResolver

        result = DecisionMakerResolver().resolve(
            company_data={"domain": "empresa.com.br"},
            profile={"decision_makers": {"roles": ["founder"]}},
            sources={
                "company_site": [{
                    "name": "Maria Silva",
                    "email": "maria@empresa.com.br",
                    "linkedin_url": "https://www.linkedin.com/in/maria-silva",
                }],
                "verified_email": [{
                    "name": "Maria Silva",
                    "email": "maria@empresa.com.br",
                }],
            },
        )

        assert result.status == "resolved"
        assert result.audit["has_cpf"] is False
        assert result.audit["identity_confidence"] >= 70


    def test_resolver_marca_needs_review_quando_identidade_ambigua_sem_cpf(self):
        """needs_review: mesmo nome com e-mails distintos, sem CPF e confiança baixa."""
        from services.prospecting.decision_maker_resolution import DecisionMakerResolver

        result = DecisionMakerResolver().resolve(
            company_data={"domain": "empresa.com.br"},
            profile={"decision_makers": {"roles": ["founder"]}},
            sources={
                "site_oficial": [
                    {"name": "Ana Souza", "email": "ana@empresa.com.br"},
                ],
                "busca_passiva": [
                    {"name": "Ana Souza", "email": "ana.souza@outra.com"},
                ],
            },
        )
        assert result.status == "needs_review"
        assert "reason" in result.audit


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
    def test_source_reliability_tem_pesos_calibraveis(self):
        from services.prospecting.decision_maker_resolution import ContactConfidence

        confidence = ContactConfidence()

        assert confidence.source_reliability("receita_qsa") == 0.95
        assert confidence.source_reliability("company_site") == 0.90
        assert confidence.source_reliability("provider_desconhecido") == 0.30

    def test_identity_confidence_resolve_sem_cpf_com_fontes_concordantes(self):
        from services.prospecting.decision_maker_resolution import ContactConfidence, PersonContact

        person = PersonContact(
            name="Maria Silva",
            source="company_site",
            email="maria@empresa.com.br",
            linkedin_url="https://www.linkedin.com/in/maria-silva",
        )
        confidence = ContactConfidence().identity_confidence(
            person,
            ["company_site", "verified_email", "linkedin_current"],
        )

        assert confidence["status"] == "resolved"
        assert confidence["confidence"] >= 70
        assert confidence["has_cpf"] is False
        assert confidence["sources"] == ["company_site", "verified_email", "linkedin_current"]

    def test_identity_confidence_partial_com_uma_fonte_fraca(self):
        from services.prospecting.decision_maker_resolution import ContactConfidence, PersonContact

        person = PersonContact(name="Maria Silva", source="search_engine")
        confidence = ContactConfidence().identity_confidence(person, ["search_engine"])

        assert confidence["status"] == "partial"
        assert confidence["confidence"] < 70

    def test_contact_confidence_considera_fonte_e_canais_verificados(self):
        from services.prospecting.decision_maker_resolution import ContactConfidence, PersonContact

        person = PersonContact(
            name="Maria Silva",
            source="company_site",
            email="maria@empresa.com.br",
            linkedin_url="https://www.linkedin.com/in/maria-silva",
        )
        confidence = ContactConfidence().contact_confidence(
            person,
            sources=["company_site", "verified_email"],
            email_verified=True,
        )

        assert confidence["confidence"] >= 80
        assert confidence["actionable"] is True
        assert confidence["identity"]["status"] == "resolved"
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


    def test_resolver_distinguido_de_falha_de_provider(self):
        """failed: exceção de fonte é falha, não ausência de pessoa."""
        from services.prospecting.decision_maker_resolution import (
            DecisionMakerResolver, ResolutionResult,
        )

        result = ResolutionResult.failed(
            reason="provider_receita_timeout",
            profile_roles=["ceo"],
            sources_attempted=["receita_federal"],
            retryable=True,
        )
        assert result.status == "failed"
        assert result.people == []
        assert result.audit["retryable"] is True

        resolved = DecisionMakerResolver().resolve(
            company_data={"cnpj": "123"},
            profile={"decision_makers": {"roles": ["ceo"]}},
            sources={"receita_federal": [{"name": "Ana", "document_cpf": "1"}]},
        )
        assert resolved.status in ("resolved", "partial", "needs_review")
        assert resolved.audit.get("reason") != "provider_receita_timeout"


class TestContactVerifierAsyncSeam:
    def test_verify_email_async_nao_abre_thread_no_resolver(self):
        """ContactVerifier async é o seam de I/O; resolver sync não faz rede."""
        import inspect
        from services.prospecting import contact_verifier

        assert inspect.iscoroutinefunction(contact_verifier.ContactVerifier.verify_email)
        assert "threading" not in inspect.getsource(contact_verifier)

    def test_verify_email_async_confirma_mx_via_servico_injetado(self):
        """Verificação real passa por EmailVerificationService injetado."""
        import asyncio
        from services.prospecting.contact_verifier import ContactVerifier
        from services.prospecting.decision_maker_resolution import PersonContact

        calls = []

        class FakeEmailService:
            async def verify_email(self, email):
                calls.append(email)
                return {"verified": True, "reason": "ok"}

        result = asyncio.run(ContactVerifier(FakeEmailService()).verify_email(
            PersonContact(name="Maria", source="receita", email="m@alpha.com")
        ))
        assert calls == ["m@alpha.com"]
        assert result["email_verified"] is True

    def test_contact_enrichment_considera_email_verified_do_seam_async(self):
        """O enriquecimento consome a chave oficial `email_verified`."""
        import asyncio
        from services.contact_enrichment_service import ContactEnrichmentService
        from database.models import Contact

        class FakeVerifier:
            async def verify_email(self, person):
                return {
                    "email_verified": True,
                    "verification_status": "verified",
                    "reason": "ok",
                }

        contact = Contact(name="Maria Silva", email="maria@alpha.com", email_verified=False)
        service = ContactEnrichmentService(contact_verifier=FakeVerifier())
        asyncio.run(service._verify_email(None, contact))

        assert contact.email_verified is True


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
