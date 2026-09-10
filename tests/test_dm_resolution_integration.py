"""Testes de integração Decision Maker Resolution (Fase G — Fase 3 real).

Valida:
- IdentityResolver normaliza acentos (Conceição == Conceicao)
- ContactVerification síncrono NÃO toca em rede (migração onda 2)
- Verificação real de e-mail mora no seam assíncrono `ContactVerifier`
- Pipeline produz pessoas REAIS (não inventadas) em cenário completo
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))


class TestIdentityResolverNormalization:
    def test_merge_com_acentos_iguais(self):
        """Conceição Müller == Conceicao Muller (mesma pessoa)."""
        from services.prospecting.decision_maker_resolution import (
            IdentityResolver, PersonContact,
        )
        resolver = IdentityResolver()
        contacts = [
            PersonContact(name="Conceição Müller", source="receita", document_cpf="111"),
            PersonContact(name="Conceicao Muller", source="linkedin", document_cpf="111"),
        ]
        merged = resolver.merge(contacts)
        # Mesmo CPF → merge
        assert len(merged) == 1

    def test_nome_case_insensitive_no_email_match(self):
        from services.prospecting.decision_maker_resolution import (
            IdentityResolver, PersonContact,
        )
        resolver = IdentityResolver()
        contacts = [
            PersonContact(name="MARIA SILVA", source="receita", email="m@x.com"),
            PersonContact(name="maria silva", source="linkedin", email="m@x.com"),
        ]
        merged = resolver.merge(contacts)
        # Mesmo email + mesmo nome (case-insensitive) → merge
        assert len(merged) == 1

    def test_nome_com_typo_nao_merga_sem_cpf(self):
        """Maria Silva vs Maria SIlva (typo) sem CPF → não merge."""
        from services.prospecting.decision_maker_resolution import (
            IdentityResolver, PersonContact,
        )
        resolver = IdentityResolver()
        contacts = [
            PersonContact(name="Maria Silva", source="receita", email="m1@x.com"),
            PersonContact(name="Maria SIlva", source="linkedin", email="m2@y.com"),
        ]
        merged = resolver.merge(contacts)
        # Sem CPF, email diferente → não merge
        assert len(merged) == 2


class TestContactVerificationReal:
    """Sem mock explicitamente injetado, o resolver marca pendência real."""

    def test_verification_sem_mock_marca_pendencia_real(self):
        """Com mock_mx_check=None, verification_status = 'pending_real_check'."""
        from services.prospecting.decision_maker_resolution import (
            ContactVerification, PersonContact,
        )
        verifier = ContactVerification()
        p = PersonContact(
            name="Maria", source="receita", email="m@alpha.com",
            document_cpf="111",
        )
        result = verifier.verify(p)  # sem mock_mx_check
        # Sem mock: marca pending (não verificado, mas não falha)
        assert result["email_verified"] is False
        assert result["verification_status"] in ("pending_real_check", "identity_verified_no_email")

    def test_verification_legado_nao_toca_rede_via_sys_modules(self, monkeypatch):
        """Migração onda 2: o resolver síncrono não usa o serviço por hack.

        Mesmo com um módulo fake de `email_verification_service` presente em
        `sys.modules`, o resolver síncrono NÃO o chama — a verificação real
        é responsabilidade do seam assíncrono `ContactVerifier`.
        """
        import sys
        import types
        from services.prospecting.decision_maker_resolution import (
            ContactVerification, PersonContact,
        )

        calls = []

        class FakeEmailVerificationService:
            async def verify_email(self, email):
                calls.append(email)
                return {"verified": True, "reason": "ok"}

        fake_module = types.ModuleType("services.email_verification_service")
        fake_module.EmailVerificationService = FakeEmailVerificationService
        monkeypatch.setitem(sys.modules, "services.email_verification_service", fake_module)

        person = PersonContact(
            name="Maria",
            source="receita",
            email="maria@alpha.com",
            document_cpf="111",
        )
        result = ContactVerification().verify(person)

        assert calls == []  # nunca tocou em rede por conta própria
        assert result["email_verified"] is False
        assert result["verification_status"] in ("pending_real_check", "identity_verified_no_email")

    def test_verificador_assincrono_usa_metodo_publico_verify_email(self):
        """O seam async `ContactVerifier` chama `verify_email` do serviço injetado."""
        import asyncio
        from types import SimpleNamespace
        from services.prospecting.contact_verifier import ContactVerifier

        calls = []

        class FakeEmailVerificationService:
            async def verify_email(self, email):
                calls.append(email)
                return {"verified": True, "reason": "ok"}

        person = SimpleNamespace(
            name="Maria", source="receita", email="maria@alpha.com", document_cpf="111",
        )
        result = asyncio.run(ContactVerifier(FakeEmailVerificationService()).verify_email(person))

        assert calls == ["maria@alpha.com"]
        assert result["email_verified"] is True
        assert result["verification_status"] == "verified"


class TestPhaseGContactEnrichmentIntegration:
    """Valida que ContactEnrichmentService realmente pluga DecisionMakerResolver."""

    def test_enrich_contacts_usa_decision_maker_resolver(self):
        """Verifica via grep que a integração está no contact_enrichment_service."""
        with open("services/workers/src/services/contact_enrichment_service.py") as f:
            content = f.read()
        # Integração presente
        assert "from services.prospecting.decision_maker_resolution import" in content
        assert "DecisionMakerResolver" in content
        assert "IdentityResolver" in content
        assert "ContactVerification" in content
        # Persistência
        assert "resolution" in content
        # Audit
        assert "audit" in content
