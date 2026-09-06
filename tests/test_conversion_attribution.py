"""Contrato de atribuição explícita das conversões comerciais."""


def test_nova_conversao_exige_oferta_explicita():
    from pydantic import ValidationError
    from src.routes.leads import RegisterConversionRequest

    try:
        RegisterConversionRequest(contract_value=1000)
    except ValidationError as exc:
        assert "offer_key" in str(exc)
    else:
        raise AssertionError("Conversão nova sem offer_key deve ser rejeitada")


def test_conversao_desconhecida_precisa_ser_explicitamente_revisavel():
    from src.routes.leads import RegisterConversionRequest

    request = RegisterConversionRequest(offer_key="unknown", contract_value=1000)
    assert request.offer_key == "unknown"
    assert request.lead_opportunity_id is None


def test_conversao_preserva_atribuicao_da_oportunidade():
    from src.routes.leads import RegisterConversionRequest

    request = RegisterConversionRequest(
        offer_key="landing_page",
        offer_version="1.0",
        lead_opportunity_id="00000000-0000-0000-0000-000000000001",
    )
    assert request.offer_key == "landing_page"
    assert str(request.lead_opportunity_id) == "00000000-0000-0000-0000-000000000001"