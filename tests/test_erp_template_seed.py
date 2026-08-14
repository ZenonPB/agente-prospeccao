"""Testes do seed do template de Aplicações Web / ERP.

C5: para vender aplicações web completas / sistemas ERP, o perfil de análise é o
mesmo `web_presence` — o que muda são os critérios (sinais) do template. A
decisão registrada foi **criar template de categoria** (seed) em vez
de um terceiro perfil. Estes testes garantem que o seed carrega a estrutura
certa sem depender de banco.
"""
from seeds.scoring_templates import DEFAULT_TEMPLATES


def _erp_template():
    matches = [t for t in DEFAULT_TEMPLATES if t["service_label"] == "Aplicações Web / ERP"]
    assert len(matches) == 1, "seed deve ter exatamente 1 template de Aplicações Web / ERP"
    return matches[0]


def test_template_erp_presente_no_seed():
    _erp_template()


def test_template_erp_mesmo_perfil_web_presence():
    # C5: ERP/web apps usam o MESMO perfil de análise (técnica do site) —
    # não é um terceiro perfil.
    tmpl = _erp_template()
    assert tmpl["requires_technical_report"] is True
    assert tmpl["requires_business_data"] is True


def test_template_erp_sinais_de_processo_manual():
    # Público-alvo: quem opera manualmente (planilha) e não tem portal.
    tmpl = _erp_template()
    labels = {s["label"] for s in tmpl["positive_signals"]}
    assert "Processo manual / planilha" in labels
    assert "Sem área logada / portal do cliente" in labels
    assert "Site institucional / landing sem função" in labels


def test_template_erp_sinais_de_ja_tem_sistema():
    # Quem já tem sistema (portal/painel/API) é negócio fechado → reduz score.
    tmpl = _erp_template()
    labels = {s["label"] for s in tmpl["negative_signals"]}
    assert "Painel / área do cliente presente" in labels
    assert "Menção a integrações/API" in labels


def test_template_erp_instrucao_anti_desqualificacao():
    # Nunca desqualificar por "site desatualizado" — manual = público-alvo.
    tmpl = _erp_template()
    instructions = tmpl.get("extra_instructions", "").lower()
    assert "processo manual" in instructions
    assert "área logada" in instructions
