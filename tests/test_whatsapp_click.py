"""Testes do fluxo WhatsApp de 1 clique + registro na trilha."""
from src.db.models import LeadActivityAction
from src.routes.leads import _format_whatsapp_url


def test_whatsapp_sent_action_enum():
    assert LeadActivityAction.WHATSAPP_SENT.value == "WHATSAPP_SENT"


def test_format_whatsapp_url_valido_br():
    url, formatted, is_mobile = _format_whatsapp_url("(16) 99999-8888", "Olá!")
    assert url == "https://wa.me/5516999998888?text=Ol%C3%A1%21"
    assert formatted == "5516999998888"
    assert is_mobile is True


def test_format_whatsapp_url_com_codigo_pais():
    url, formatted, is_mobile = _format_whatsapp_url("+55 11 91234-5678")
    assert url == "https://wa.me/5511912345678"
    assert formatted == "5511912345678"
    assert is_mobile is True


def test_format_whatsapp_url_invalido():
    url, formatted, is_mobile = _format_whatsapp_url("1234")
    assert url is None
    assert is_mobile is False
