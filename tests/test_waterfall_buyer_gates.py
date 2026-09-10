"""Gates de buyer no waterfall de People Discovery (P1.36 → operacional).

Seams sob teste (acordados no plano da branch):
- `PeopleProviderRegistry.waterfall_search` — gates de early stopping;
- `ContactEnrichmentService.discovery_limits` — leitura de config do OfferProfile;
- `buyer_persona` — inferência determinística de buyer role e personas.

Slice A: `min_identity_confidence` só libera early stopping quando a
identidade da pessoa atinge o mínimo (contato forte com identidade fraca
não encerra a cascata).
"""
import asyncio


class TestMinIdentityConfidenceGate:
    def test_identidade_fraca_nao_encerra_cascata(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        calls = []

        class LowIdentityProvider:
            name = "low_identity"
            cost = 1

            async def search(self, domain, titles):
                calls.append(self.name)
                return [{
                    "name": "Ana",
                    "title": "Engineering Manager",
                    "confidence": 90,
                    "identity_confidence": 20,
                }]

        class HighIdentityProvider:
            name = "high_identity"
            cost = 1

            async def search(self, domain, titles):
                calls.append(self.name)
                return [{
                    "name": "Bruno",
                    "title": "Engineering Manager",
                    "confidence": 90,
                    "identity_confidence": 90,
                }]

        result = asyncio.run(PeopleProviderRegistry(
            [LowIdentityProvider(), HighIdentityProvider()],
        ).waterfall_search(
            "empresa.com", ["Engineering Manager"],
            min_identity_confidence=70,
        ))

        assert calls == ["low_identity", "high_identity"]
        assert result["early_stopped"] is True
        assert result["status"] == "success"

    def test_sem_gate_identidade_mantem_comportamento_legado(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        calls = []

        class FirstProvider:
            name = "first"
            cost = 1

            async def search(self, domain, titles):
                calls.append(self.name)
                return [{
                    "name": "Ana",
                    "title": "Engineering Manager",
                    "confidence": 90,
                    "identity_confidence": 20,
                }]

        class SecondProvider:
            name = "second"
            cost = 1

            async def search(self, domain, titles):
                calls.append(self.name)
                return [{"name": "Bruno", "title": "Manager", "confidence": 90}]

        result = asyncio.run(PeopleProviderRegistry(
            [FirstProvider(), SecondProvider()],
        ).waterfall_search("empresa.com", ["Engineering Manager"]))

        assert calls == ["first"]
        assert result["early_stopped"] is True


class TestInferBuyerRole:
    """Seam `buyer_persona`: inferência determinística sem inventar decisor."""

    def test_mapeia_cargos_para_buyer_role_conhecido(self):
        from services.prospecting.buyer_persona import infer_buyer_role

        assert infer_buyer_role("Engineering Manager") == "TECHNICAL_BUYER"
        assert infer_buyer_role("Founder") == "ECONOMIC_BUYER"
        assert infer_buyer_role("Marketing Manager") == "CHAMPION"

    def test_sem_cargo_retorna_unknown(self):
        from services.prospecting.buyer_persona import infer_buyer_role

        assert infer_buyer_role(None) == "UNKNOWN"
        assert infer_buyer_role("") == "UNKNOWN"

    def test_normaliza_lista_exigida(self):
        from services.prospecting.buyer_persona import normalize_buyer_roles

        assert normalize_buyer_roles("technical_buyer") == ["TECHNICAL_BUYER"]
        assert normalize_buyer_roles(["ECONOMIC_BUYER", "  champion "]) == [
            "ECONOMIC_BUYER", "CHAMPION",
        ]
        assert normalize_buyer_roles(None) == []


class TestRequiredBuyerRoleGate:
    """`required_buyer_role` só libera early stopping com buyer role exigido."""

    def test_buyer_role_divergente_nao_encerra_cascata(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        calls = []

        class ChampionProvider:
            name = "champion_source"
            cost = 1

            async def search(self, domain, titles):
                calls.append(self.name)
                return [{
                    "name": "Ana",
                    "title": "Marketing Manager",
                    "confidence": 90,
                }]

        class TechnicalProvider:
            name = "technical_source"
            cost = 1

            async def search(self, domain, titles):
                calls.append(self.name)
                return [{
                    "name": "Bruno",
                    "title": "Engineering Manager",
                    "confidence": 90,
                }]

        result = asyncio.run(PeopleProviderRegistry(
            [ChampionProvider(), TechnicalProvider()],
        ).waterfall_search(
            "empresa.com", ["Engineering Manager"],
            required_buyer_role="TECHNICAL_BUYER",
        ))

        assert calls == ["champion_source", "technical_source"]
        assert result["early_stopped"] is True
        assert result["people"][-1]["buyer_role"] == "TECHNICAL_BUYER"

    def test_nenhum_match_de_buyer_role_tem_status_explicito(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        class ChampionProvider:
            name = "champion_source"
            cost = 1

            async def search(self, domain, titles):
                return [{
                    "name": "Ana",
                    "title": "Marketing Manager",
                    "confidence": 90,
                }]

        result = asyncio.run(PeopleProviderRegistry(
            [ChampionProvider()],
        ).waterfall_search(
            "empresa.com", ["Engineering Manager"],
            required_buyer_role="TECHNICAL_BUYER",
        ))

        assert result["early_stopped"] is False
        assert result["status"] == "buyer_role_not_matched"
        assert result["people"][0]["buyer_role_status"] == "not_matched"

    def test_sem_gate_buyer_role_mantem_comportamento_legado(self):
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        class Provider:
            name = "people"
            cost = 1

            async def search(self, domain, titles):
                return [{
                    "name": "Ana",
                    "title": "Marketing Manager",
                    "confidence": 90,
                }]

        result = asyncio.run(PeopleProviderRegistry(
            [Provider()],
        ).waterfall_search("empresa.com", ["Marketing Manager"]))

        assert result["early_stopped"] is True
        assert result["status"] == "success"
        assert result["people"][0]["buyer_role_status"] == "not_requested"


class TestBuyerPersonas:
    """Entidade BuyerPersona: 8 personas iniciais do roadmap (§4.4)."""

    def test_oito_personas_com_campos_obrigatorios(self):
        from services.prospecting.buyer_persona import list_personas

        personas = list_personas()
        assert {p.key for p in personas} == {
            "founder", "marketing_manager", "operations_director",
            "engineering_manager", "maintenance_manager", "safety_manager",
            "event_director", "procurement",
        }
        for persona in personas:
            assert persona.title_patterns
            assert persona.buyer_type in {
                "ECONOMIC_BUYER", "TECHNICAL_BUYER", "CHAMPION",
                "END_USER", "INFLUENCER",
            }
            assert persona.preferred_channels

    def test_match_persona_por_cargo(self):
        from services.prospecting.buyer_persona import match_persona_for_role

        assert match_persona_for_role("Engineering Manager") == "engineering_manager"
        assert match_persona_for_role("Sócio Fundador") == "founder"
        assert match_persona_for_role("") is None

    def test_buyer_types_do_perfil_viram_gate_exigido(self):
        from services.prospecting.buyer_persona import required_buyer_role_for_profile

        assert required_buyer_role_for_profile({
            "decision_makers": {"buyer_types": ["TECHNICAL_BUYER", "ECONOMIC_BUYER"]},
        }) == ["TECHNICAL_BUYER", "ECONOMIC_BUYER"]
        assert required_buyer_role_for_profile({}) == []
        assert required_buyer_role_for_profile({"decision_makers": {}}) == []
