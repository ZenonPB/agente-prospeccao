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


def test_template_erp_sinais_medidos_no_html():
    # Sinais de portal/área logada agora são medidos deterministicamente no
    # HTML (não mais "critério a CONFIRMAR") — ancoram o score no fact.
    tmpl = _erp_template()
    descs = " ".join(
        s["description"]
        for s in tmpl["positive_signals"] + tmpl["negative_signals"]
    ).lower()
    assert "a confirmar" not in descs


def test_template_erp_negativo_microempresa():
    # Porte é o sinal mais decisivo para ERP: microempresa/MEI é fraco fito.
    tmpl = _erp_template()
    labels = {s["label"] for s in tmpl["negative_signals"]}
    assert "Microempresa / MEI" in labels


def test_template_erp_processo_manual_baixo_peso():
    # "Processo manual / planilha" não é mensurável no site — vira inferência
    # de segmento e não pode pesar como evidência técnica alta.
    tmpl = _erp_template()
    manual = [
        s for s in tmpl["positive_signals"] if s["label"] == "Processo manual / planilha"
    ]
    assert manual and manual[0]["weight_hint"] == "low"


def test_template_erp_negativo_setor_software():
    # Lead do setor de software/TI é potencial concorrente ou já é digital
    # demais — deve pesar como negativo no scoring de ERP.
    tmpl = _erp_template()
    labels = {s["label"] for s in tmpl["negative_signals"]}
    assert any("software" in lbl.lower() or "ti" in lbl.lower() or "saas" in lbl.lower()
               for lbl in labels)


def test_template_erp_positivo_lead_jovem_estruturando():
    # Empresa < 2 anos está estruturando processos — público-alvo de ERP.
    tmpl = _erp_template()
    labels = {s["label"] for s in tmpl["positive_signals"]}
    assert any("jovem" in lbl.lower() or "estrutur" in lbl.lower() for lbl in labels)


def test_template_erp_positivo_operacao_pequena_bem_avaliada():
    # Boa nota Google + poucas avaliações = operação pequena sem gestão.
    tmpl = _erp_template()
    labels = {s["label"] for s in tmpl["positive_signals"]}
    assert any("pequena" in lbl.lower() or "operação pequena" in lbl.lower()
               or "bem avaliada" in lbl.lower() for lbl in labels)


def test_template_erp_positivo_cnae_sistema_replicavel():
    # Setor de serviço/operação com processos replicáveis = público-alvo.
    tmpl = _erp_template()
    labels = {s["label"] for s in tmpl["positive_signals"]}
    assert any("cnae" in lbl.lower() or "replic" in lbl.lower() for lbl in labels)


def test_template_erp_extra_instrucoes_diferenciam_saas_de_sistema():
    # A instrução extra deve diferenciar SaaS de pedidos (anota.ai/iFood) de
    # sistema de gestão próprio. Sem isso, o LLM trata SaaS de delivery
    # como "já tem sistema" e derruba o score errado.
    tmpl = _erp_template()
    instr = tmpl.get("extra_instructions", "").lower()
    assert "saas" in instr
    assert "delivery" in instr or "pedidos" in instr
    assert "erp" in instr or "gestão" in instr
    # CN concorrente.
    assert "concorrent" in instr or "ti" in instr or "software" in instr


def test_template_erp_extra_instrucoes_consideram_porte_idade():
    # O foco do scoring ERP é porte/idade/CNAE, não qualidade do site.
    tmpl = _erp_template()
    instr = tmpl.get("extra_instructions", "").lower()
    assert "porte" in instr
    assert "idade" in instr
    assert "cnae" in instr


def test_template_erp_playbook_hook_saas_delivery():
    # O playbook traz gancho específico para lead que já usa SaaS de delivery.
    tmpl = _erp_template()
    hooks = tmpl.get("playbook", {}).get("hooks", [])
    assert any("anota.ai" in h.lower() or "ifood" in h.lower() or "saas" in h.lower()
               or "delivery" in h.lower() for h in hooks)
