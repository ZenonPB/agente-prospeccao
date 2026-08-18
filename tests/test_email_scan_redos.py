"""Regressão do ReDoS na extração de e-mails de HTML.

O regex antigo (`[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@...`) tinha backtracking
catastrófico em HTML grande contendo blobs base64/URLs de CDN — o local part
aceita `/`, `+` e `=`, então um blob de ~40KB fazia a varredura virar O(n²)
e travava a API inteira a 100% de CPU (nada carregava no site).

O scanner atual é linear (`_scan_email_candidates`) e imune a esse padrão.
"""
import time

from services.contact_enrichment_service import (
    _extract_emails_from_html,
    _scan_email_candidates,
)


def test_scan_email_candidates_extrai_local_e_dominio():
    assert _scan_email_candidates("fale com foo@bar.com.br hoje") == ["foo@bar.com.br"]


def test_scan_email_candidates_para_em_pontuacao():
    assert _scan_email_candidates("(foo@bar.com.br);") == ["foo@bar.com.br"]
    assert _scan_email_candidates("email: foo@bar.com.br, ok") == ["foo@bar.com.br"]


def test_scan_email_candidates_ignora_arroba_sem_local_ou_dominio():
    assert _scan_email_candidates("@foo.com") == []
    assert _scan_email_candidates("foo@") == []


def test_extract_emails_blob_base64_nao_trava():
    # Local part de ~20k chars em seguida de `@` — com o regex antigo isso
    # fazia backtracking quadrático (o class aceita letras/dígitos/`+/=`).
    blob = "A" * 20000 + "@x"
    start = time.monotonic()
    emails = _extract_emails_from_html(blob)
    elapsed = time.monotonic() - start
    assert emails == []
    assert elapsed < 2.0


def test_extract_emails_nao_captura_blob_como_email_valido():
    # Candidato absurdo além do limite de tamanho é descartado (não vira e-mail).
    html = "<p>" + "A" * 5000 + "@exemplo.com.br</p>"
    assert _extract_emails_from_html(html) == []