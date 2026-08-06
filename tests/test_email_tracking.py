"""Testes do rastreamento de abertura/clique (roadmap-vendas 4.2).

Cobrem o construtor de HTML rastreado (`email_service._build_html_tracked`) e
os handlers das rotas públicas (`routes/tracking`) com `db` fake — sem banco.
"""
from fastapi import HTTPException
from fastapi.responses import RedirectResponse

from src.services.email_service import _build_html_tracked
from src.routes.tracking import tracking_pixel, tracking_redirect


class _FakeMsg:
    def __init__(self):
        self.opened_at = None
        self.clicked_at = None


class _FakeQuery:
    def __init__(self, msg):
        self._msg = msg

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._msg


class _FakeDb:
    def __init__(self, msg):
        self._q = _FakeQuery(msg)
        self._msg = msg

    def query(self, *_a):
        return self._q

    def commit(self):
        pass

    def rollback(self):
        pass


def test_build_html_tracked_insere_pixel_e_reescreve_links():
    body = "Oi, veja nossa proposta: https://exemplo.com.br/sobre e também http://outro.com"
    html_body = _build_html_tracked(body, "https://api.alphamec.com.br", "tok123")
    assert f'<img src="https://api.alphamec.com.br/t/tok123"' in html_body
    assert '/c/tok123?url=' in html_body
    assert 'https://exemplo.com.br/sobre' in html_body  # texto do link = URL original
    assert 'https://api.alphamec.com.br/c/tok123' in html_body  # href rastreado
    assert html_body.startswith("<!DOCTYPE html>")


def test_tracking_pixel_grava_abertura():
    msg = _FakeMsg()
    resp = tracking_pixel("tok123", db=_FakeDb(msg))
    assert resp.status_code == 200
    assert resp.media_type == "image/gif"
    assert msg.opened_at is not None


def test_tracking_pixel_nao_quebra_token_desconhecido():
    # Pixel não encontrado NÃO deve quebrar o e-mail (load silencioso de imagem).
    resp = tracking_pixel("sem-token", db=_FakeDb(None))
    assert resp.status_code == 200
    assert resp.media_type == "image/gif"


def test_tracking_redirect_grava_clique_e_redireciona():
    msg = _FakeMsg()
    resp = tracking_redirect("tok123", url="https://exemplo.com.br/sobre", db=_FakeDb(msg))
    assert isinstance(resp, RedirectResponse)
    assert resp.status_code == 302
    assert resp.headers.get("location") == "https://exemplo.com.br/sobre"
    assert msg.clicked_at is not None


def test_tracking_redirect_rejeita_url_invalida():
    try:
        tracking_redirect("tok123", url="javascript:alert(1)", db=_FakeDb(_FakeMsg()))
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("URL inválida deveria retornar 400")
