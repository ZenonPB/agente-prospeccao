"""Testes da detecção de templates gerados corrompidos (S5 — correção cirúrgica).

Cobrem apenas a lógica pura (regex de presença-invertida), sem banco. O script
completo roda contra o banco via `python -m src.scripts.fix_generated_web_templates`.
"""
from types import SimpleNamespace

# O pacote `scripts` do workers resolve como top-level (WORKERS_SRC no
# conftest). `src.scripts` colidiria com o pacote `src` da API.
from scripts.fix_generated_web_templates import _has_presence_positive


def test_detecta_presenca_online_como_positivo():
    # Assinatura do template corrompido do roadmap: presença online = positivo.
    tmpl = SimpleNamespace(positive_signals=[
        {"label": "Presença Online", "description": "Clínica com site próprio ou perfil em redes sociais"},
    ])
    assert _has_presence_positive(tmpl) is True


def test_detecta_site_proprio_como_positivo():
    tmpl = SimpleNamespace(positive_signals=[
        {"label": "Site próprio moderno", "description": "empresa já possui website atualizado"},
    ])
    assert _has_presence_positive(tmpl) is True


def test_nao_detecta_ausencia_de_site_como_corrompido():
    # "Sem site próprio" descreve o COMPRADOR — é o sinal correto p/ serviço web.
    tmpl = SimpleNamespace(positive_signals=[
        {"label": "Sem site próprio", "description": "usa Instagram/Canva — comprador"},
        {"label": "Site desatualizado sem CTA", "description": "presença fraca"},
    ])
    assert _has_presence_positive(tmpl) is False


def test_nao_detecta_sinais_nao_web():
    tmpl = SimpleNamespace(positive_signals=[
        {"label": "Indústria/fábrica", "description": "categoria industrial"},
    ])
    assert _has_presence_positive(tmpl) is False
