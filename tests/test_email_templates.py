"""Testes dos templates HTML de e-mail (marca Prospect.ai).

Cobrem a estrutura dos templates de cadência e transacional:
preheader, DOCTYPE, marca, CTA com fallback MSO, dark mode e footer.
"""
from src.services.email_templates import (
    render_outreach_email,
    render_transactional_email,
)


def _strip(_s: str) -> str:
    return " ".join(_s.split())


def test_outreach_template_estrutura_completa():
    out = _strip(render_outreach_email(
        "<p>Olá, veja o link.</p>",
        sender_name="João Vendas",
        sender_email="joao@empresa.com.br",
        preheader="Preview do e-mail",
    ))
    assert out.startswith("<!DOCTYPE html>")
    assert "alpha-eml-card" in out and "max-width:600px" in out
    assert "João Vendas" in out and "joao@empresa.com.br" in out
    assert "#910001" in out  # vinho da marca (radar)
    assert "font-family" in out  # system stack
    assert "© Prospect.ai" in out  # footer
    assert "mso-hide:all" in out  # preheader oculto
    assert "prefers-color-scheme" in out  # dark mode


def test_outreach_template_nao_tem_cta_hero():
    out = _strip(render_outreach_email("<p>Texto.</p>", "João Vendas"))
    assert "v:roundrect" not in out
    assert "Definir nova senha" not in out


def test_transactional_template_cta_mso_e_fallback():
    out = _strip(render_transactional_email(
        "Redefinição de senha",
        "<p>Corpo.</p>",
        cta_label="Definir nova senha",
        cta_url="https://app.example.com/reset?token=ABC",
        fallback_url="https://app.example.com/reset?token=ABC",
        footnote="Este link expira em 2 horas.",
        preheader="Redefina a senha",
    ))
    assert out.startswith("<!DOCTYPE html>")
    assert "Redefinição de senha" in out
    assert "v:roundrect" in out  # fallback MSO (Outlook)
    assert 'fillcolor="#910001"' in out
    assert "Definir nova senha" in out
    assert "copie este link" in out
    assert "font-weight:600" in out
    assert "Este link expira em 2 horas." in out
    assert "color-scheme" in out


def test_transactional_sem_cta():
    out = _strip(render_transactional_email("Aviso", "<p>Corpo.</p>"))
    assert "v:roundrect" not in out


def test_escape_de_entrada_usuario():
    out = _strip(render_transactional_email(
        "Convite para <Org> & Cia",
        "<p>Texto <b>seguro</b>.</p>",
        cta_label="Aceitar <b>convite</b>",
        cta_url="https://app.example.com?token=A&B",
    ))
    assert "&lt;Org&gt;" in out  # título escapado
    assert "<b>seguro</b>" in out  # body já é HTML pronto (confiável)
    assert "Aceitar &lt;b&gt;convite&lt;/b&gt;" in out  # rótulo escapado
    assert "token=A&amp;B" in out  # URL escapada no atributo href