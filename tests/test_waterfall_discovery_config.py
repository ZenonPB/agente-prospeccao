"""Config de People Discovery com gates de buyer (P1.36 → operacional).

Seam sob teste: `ContactEnrichmentService.discovery_limits` (config pura do
OfferProfile). Requer dependências do serviço — executar com o venv da API.
"""


class TestDiscoveryLimitsBuyerGates:
    def test_le_gates_de_buyer_do_people_discovery(self):
        from services.contact_enrichment_service import ContactEnrichmentService

        config = ContactEnrichmentService.discovery_limits({
            "enrichment": {
                "people_discovery": {
                    "max_cost": 2,
                    "max_steps": 2,
                    "min_role_fit": 70,
                    "min_identity_confidence": 60,
                    "required_buyer_role": "technical_buyer",
                },
            },
        })

        assert config["min_identity_confidence"] == 60.0
        assert config["required_buyer_role"] == ["TECHNICAL_BUYER"]

    def test_gates_invalidos_voltam_para_neutro_sem_quebrar_legado(self):
        from services.contact_enrichment_service import ContactEnrichmentService

        config = ContactEnrichmentService.discovery_limits({
            "enrichment": {
                "min_identity_confidence": 101,
                "required_buyer_role": ["", "  "],
            },
        })

        assert config["min_identity_confidence"] is None
        assert config["required_buyer_role"] == []

    def test_config_sem_gates_mantem_neutro(self):
        from services.contact_enrichment_service import ContactEnrichmentService

        config = ContactEnrichmentService.discovery_limits({})

        assert config["min_identity_confidence"] is None
        assert config["required_buyer_role"] == []

    def test_buyer_types_do_perfil_como_fallback_do_gate(self):
        from services.contact_enrichment_service import ContactEnrichmentService

        config = ContactEnrichmentService.discovery_limits({
            "enrichment": {"max_cost": 2, "max_steps": 2},
            "decision_makers": {"buyer_types": ["TECHNICAL_BUYER"]},
        })

        assert config["required_buyer_role"] == ["TECHNICAL_BUYER"]

    def test_gate_explicito_prevalece_sobre_buyer_types(self):
        from services.contact_enrichment_service import ContactEnrichmentService

        config = ContactEnrichmentService.discovery_limits({
            "enrichment": {
                "people_discovery": {"required_buyer_role": "CHAMPION"},
            },
            "decision_makers": {"buyer_types": ["TECHNICAL_BUYER"]},
        })

        assert config["required_buyer_role"] == ["CHAMPION"]
