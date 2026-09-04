"""AIScoringService — scoring contextual e explicável via Groq.

Esta versão substitui a abordagem anterior (específica para tecnologia):

- NÃO há mais prompts hard-coded para segurança/SEO/HTTPS/WordPress.
- O prompt é montado a partir de:
  - contexto da campanha (target_service / target_segment)
  - template de critérios (CampaignScoringTemplate) — editável no banco,
    uma entrada por categoria de serviço. Permite adicionar novas categorias
    sem tocar no código.
  - facts técnicos determinísticos extraídos do relatório do site (quando
    relevante para a categoria) — ex.: "WordPress detectado", "SSL válido".
    Esses facts são a evidência bruta; a LLM apenas interpreta.
  - dados cadastrais do lead (categoria, porte inferido, cidade, segmento).
- A resposta é expandida para incluir explicabilidade completa:
  - score_factors[] : fatores + (impacto positivo) / − (impacto negativo)
                       com caption curta e referência à evidência
  - evidence[]      : lista de evidências estruturadas
                      {type, severity, title, description, source}
  - priority        : HOT | WARM | COLD (decisão LLM, não faixa de score)
  - priority_reasoning : justificativa textual da prioridade
  - executive_summary : resumo consultor comercial (2-4 frases)
  - pitch_angle / suggested_subject : mantidos para outreach
"""
import json
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional

from config.settings import settings  # noqa: E402

logger = logging.getLogger(__name__)

# Padrões de alegação de ausência/presença de site que a LLM pode inventar
# apesar dos facts ("Tem website: sim" nos facts vs "sem site próprio" na
# resposta). Guard determinístico: evidência que contradiz o fato é removida.
_NO_SITE_CLAIM = re.compile(
    r"sem\s+(site|p[áa]gina|presen[çc]a|website|home)|"
    r"n[aã]o\s+(tem|possui|h[aá])\s+(um|uma|nenhum|nenhuma)?\s*(site|website|p[áa]gina)|"
    r"aus[eê]ncia\s+de\s+(site|website|presen[çc]a)",
    re.IGNORECASE,
)
_HAS_SITE_CLAIM = re.compile(
    r"(tem|possui)\s+(um|uma|o|a)?\s*(site|website|homepage)|com\s+site\s+pr[oó]prio",
    re.IGNORECASE,
)

# Campanhas cujo serviço é presença digital/desenvolvimento de site — para elas,
# um lead SEM site é público-alvo (o prompt pondera positivamente a ausência).
# Decisão por template (autoridade de critérios): só os labels de presença web
# tratam ausência de site como oportunidade. A regex é fallback apenas quando
# não há template específico (rota GENERIC com o template "Genérico" ou None).
_WEB_PRESENCE_LABELS = frozenset({
    "desenvolvimento de sites",
    "seo / marketing digital",
})
_SELLS_WEB_PRESENCE = re.compile(
    r"site|website|p[áa]gina|loja virtual|presen[çc]a digital|landing|"
    r"marketing digital|seo|e-?commerce|web\s?(design|sites?|presen)",
    re.IGNORECASE,
)


def _campaign_sells_web_presence(template: Optional[Dict[str, Any]], target_service: str) -> bool:
    """True se a campanha trata ausência de site como público-alvo.

    Template específico decide pelos critérios que ele define (ex.: o template
    "Aplicações Web / ERP" não trata ausência de site como dor; "Desenvolvimento
    de Sites" trata). Sem template específico (Genérico/None), cai na regex sobre
    o serviço como aproximação de rota GENERATE_NEW ainda sem template.
    """
    if template:
        label = (template.get("service_label") or "").strip().lower()
        if label not in _WEB_PRESENCE_LABELS and label != "genérico":
            return False
    return bool(_SELLS_WEB_PRESENCE.search(target_service or ""))


# Labels de template cuja venda é sistema web completo / ERP — para essas
# campanhas, o fito vem principalmente do cadastro (porte, idade, CNAE) e do
# segmento, NÃO da qualidade do site. Adicionar novos labels aqui expande a
# aplicação da instrução 8c para outros templates de venda de sistemas sob
# medida sem tocar no build_prompt.
_ERP_WEBAPP_LABELS = frozenset({
    "aplicações web / erp",
    "sistemas web / erp",
    "aplicações web completas",
    "erp personalizado",
    "sistema web sob medida",
})


def _campaign_sells_erp_webapps(template: Optional[Dict[str, Any]], target_service: str) -> bool:
    """True se a campanha vende SISTEMA WEB COMPLETO / ERP sob medida.

    Determina se a instrução 8c (foco em porte/CNAE/idade/segmento) deve
    aparecer no prompt. Critério principal: template com label de ERP/webapp
    sob medida. Fallback por regex no target_service cobre campanhas com
    template "Genérico" ou ainda sem template específico (rota GENERATE_NEW).
    """
    if template:
        label = (template.get("service_label") or "").strip().lower()
        if label in _ERP_WEBAPP_LABELS:
            return True
        if label and label != "genérico":
            # Template específico de outra categoria — não é ERP.
            return False
    if not target_service:
        return False
    svc = target_service.lower()
    return bool(re.search(
        r"erp|sistema(s)?\s+web|aplica[çc][ãa]o\s+web|gest[ãa]o\s+integrada|"
        r"plataforma\s+(web|sob\s+medida)|software\s+sob\s+medida",
        svc,
    ))


def _contradicts_site_state(evidence: Dict[str, Any], has_website: bool) -> bool:
    """True se a evidência contradiz o fato cadastral de presença de site."""
    text = " ".join(str(evidence.get(k) or "") for k in ("title", "description"))
    if has_website:
        return bool(_NO_SITE_CLAIM.search(text))
    # Sem site: negação explícita ("não tem site") tem prioridade e nunca é
    # tratada como claim de posse — o _HAS_SITE_CLAIM casaria no "tem site".
    if _NO_SITE_CLAIM.search(text):
        return False
    return bool(_HAS_SITE_CLAIM.search(text))


# ---------------------------------------------------------------------------
# Grounding do pitch/suggested_subject (Frente A)
#
# O LLM costuma alegar sintomas técnicos/UX (responsividade, formulário, CTA,
# "site desatualizado", etc.) que NÃO estão nos facts — ou repete critérios do
# template como se fossem fatos. Validação determinística: cada alegação de
# risco precisa de um token correspondente nas evidências aprovadas; se o texto
# reprovar, substitui-se por um pitch determinístico construído da evidência
# mais forte (sempre factual, nunca nota 0 de grounding).
# ---------------------------------------------------------------------------
_PERF_SLOW = ("muito lento", "lento")
_PERF_FAST = ("rápido", "rapido")

_RISKY_CLAIMS = [
    # (regex da alegação, tokens que precisam existir no texto das evidências)
    (re.compile(r"responsiv|mobile-?friendly|mobile", re.IGNORECASE), ("viewport", "mobile", "responsiv")),
    (re.compile(r"formul[áa]rio", re.IGNORECASE), ("formul",)),
    (re.compile(r"\bcta\b|chamada para", re.IGNORECASE), ("cta", "formul")),
    (re.compile(r"atualiz|desatualiz|antig", re.IGNORECASE), ("wordpress", "joomla", "drupal", "asp.net", "php", "cms", "desatualiz")),
    (re.compile(r"\blento\b|muito lento|r[áa]pido|performance", re.IGNORECASE), None),  # tratado por _perf_claim_supported
    (re.compile(r"\bssl\b|https|insegur|segur", re.IGNORECASE), ("ssl", "https")),
    (re.compile(r"\bseo\b", re.IGNORECASE), ("seo",)),
    (re.compile(r"lgpd|privacidade|cookies|cookie", re.IGNORECASE), ("lgpd", "privacidade", "cookies")),
    (re.compile(r"whatsapp", re.IGNORECASE), ("whatsapp",)),
    (re.compile(r"telefone|telefon", re.IGNORECASE), ("telefone",)),
    (re.compile(r"blogspot|blogger|plataforma gratuita|hospedagem gratuita|sem dom[ií]nio", re.IGNORECASE), ("plataforma gratuita", "blogspot", "blogger", "domínio próprio")),
]

_PERF_CLAIM = _RISKY_CLAIMS[4][0]


def _evidence_text(evidence: List[Dict[str, Any]]) -> str:
    """Texto normalizado de todas as evidências aprovadas (para busca de tokens)."""
    return " ".join(
        str(e.get("title") or "") + " " + str(e.get("description") or "")
        for e in evidence if isinstance(e, dict)
    ).lower()


def _perf_claim_supported(text: str, ev_text: str) -> bool:
    """Alegações de performance precisam casar com o valor medido (cronometria)."""
    lt = re.search(r"load time[: ]*(\d+)\s*ms", ev_text)
    ms = int(lt.group(1)) if lt else None
    rating = re.search(r"rating:\s*(muito lento|lento|aceitável|aceitavel|r[áa]pido)", ev_text)
    rating_val = rating.group(1).lower() if rating else None

    if re.search(r"muito lento|\blento\b", text):
        return ms is not None and ms > 3000 or rating_val in _PERF_SLOW
    if re.search(r"r[áa]pido", text):
        return ms is not None and ms < 1500 or rating_val in _PERF_FAST
    # menção genérica a "performance" → precisa existir info de performance
    return bool(re.search(r"load time|rating", ev_text))


def _has_evidence_footprint(text: str, evidence: List[Dict[str, Any]]) -> bool:
    """True se o texto referencia de alguma forma uma evidência aprovada
    (palavra com 6+ caracteres do título/descrição aparece no texto)."""
    low = text.lower()
    words = set()
    for e in evidence:
        for field in ("title", "description"):
            for w in re.findall(r"[a-zà-ÿ0-9]+", str(e.get(field) or "").lower()):
                if len(w) >= 6:
                    words.add(w)
    return any(w in low for w in words)


def _pitch_is_grounded(text: str, evidence: List[Dict[str, Any]]) -> bool:
    """Validação determinística do pitch/subject do LLM.

    False se: texto vazio, alguma alegação de risco sem suporte nas evidências,
    ou nenhuma referência (footprint) a uma evidência aprovada.
    """
    if not text or not text.strip():
        return False
    ev_text = _evidence_text(evidence)
    for regex, required in _RISKY_CLAIMS:
        if not regex.search(text):
            continue
        if regex is _PERF_CLAIM:
            if not _perf_claim_supported(text, ev_text):
                return False
        elif not any(k in ev_text for k in required):
            return False
    return _has_evidence_footprint(text, evidence)


def _pick_strongest_evidence(evidence: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Escolhe a evidência de maior gravidade (e mais 'técnica') para o fallback."""
    order = {"CRITICO": 0, "ALTO": 1, "MEDIO": 2, "BAIXO": 3, "INFO": 4}
    ranked = []
    for e in evidence:
        if not isinstance(e, dict):
            continue
        sev = order.get(str(e.get("severity") or "INFO").upper(), 9)
        typ = 0 if e.get("type") == "technical" else (1 if e.get("type") == "business" else 2)
        ranked.append((sev, typ, e))
    ranked.sort(key=lambda t: (t[0], t[1]))
    return ranked[0][2] if ranked else None


def _build_grounded_pitch(
    evidence: List[Dict[str, Any]],
    target_service: str = "",
) -> Dict[str, str]:
    """Pitch/subject determinísticos, montados da evidência aprovada mais forte.

    Usado quando o pitch do LLM reprova o grounding (alegações inventadas).
    Sempre cita a descrição da evidência — factual por construção.
    """
    ev = _pick_strongest_evidence(evidence)
    if not ev:
        return {"pitch_angle": "", "suggested_subject": ""}
    title = str(ev.get("title") or "").strip()
    desc = str(ev.get("description") or "").strip()
    desc_first = (desc[:1].lower() + desc[1:]) if desc else ""
    angle = ""
    if target_service:
        angle = f" Isso é o alvo direto de um serviço de {target_service.strip().lower()}."
    pitch = (
        f"Observamos no site: {desc_first}.{angle} "
        "Se essa dor está tirando conversão, dá para resolver com um plano objetivo — quer ver como?"
    )
    subject = f"O que notamos: {title[:80]}" if title else "Uma observação concreta sobre o site de vocês"
    return {"pitch_angle": pitch, "suggested_subject": subject}


def _ground_pitch_fields(
    parsed: Dict[str, Any],
    evidence: List[Dict[str, Any]],
    target_service: str = "",
) -> None:
    """Substitui pitch/subject reprovados no grounding por versão determinística."""
    fallback = None
    for field in ("pitch_angle", "suggested_subject"):
        text = str(parsed.get(field) or "")
        if not _pitch_is_grounded(text, evidence):
            if fallback is None:
                fallback = _build_grounded_pitch(evidence, target_service)
            parsed[field] = fallback.get(field, "")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = settings.GROQ_MODEL_CLASSIFY

SYSTEM_PROMPT = (
    "Você é um consultor comercial B2B especializado em prospecção qualificada. "
    "Avalia empresas com base no CONTEXTO da campanha (serviço que se quer vender + "
    "segmento prospectado) e nos critérios orientadores fornecidos. "
    "Toda conclusão deve ser JUSTIFICADA por evidências explícitas — nunca retorne "
    "apenas uma pontuação. "
    "Os CRITÉRIOS/sinais do template são categorias de análise, NÃO fatos sobre o lead: "
    "nunca inclua em evidence[], pitch_angle ou suggested_subject um sintoma "
    "(ex.: 'sem responsividade', 'sem formulário/CTA', 'site desatualizado', 'sem SEO') "
    "que não tenha um fact correspondente nas evidências fornecidas. "
    "pitch_angle e suggested_subject DEVEM referenciar um título de evidence[] e só "
    "podem alegar sintomas técnicos/UX (responsividade, formulário, CTA, atualização, "
    "performance, SSL, CMS, WhatsApp) se houver evidência explícita e correspondente. "
    "As frases do schema (pitch_angle, suggested_subject, etc.) são IMPLEMENTADAS "
    "especificamente a partir das evidence[] DESTE lead — NUNCA copie, repita ou "
    "parafraseie exemplos do schema ou de outros leads. "
    "A presença de site é um FATO determinístico dos facts fornecidos ('Tem website: sim/não'). "
    "Se os facts disserem que o lead TEM website, NUNCA declare que ele não tem site, "
    "NUNCA use 'sem site próprio'/'ausência de site' como dor e NUNCA invente evidência "
    "nesse sentido (vale o contrário quando os facts disserem que não tem). "
    "Se o lead NÃO tem site próprio (usa Instagram/Canva/WhatsApp ou não tem presença "
    "digital), o gancho e o assunto devem citar essa ausência/ferramenta como barreira "
    "concreta a negócios (ex.: 'sem site próprio, pedidos dependem do Instagram'). "
    "A AUSÊNCIA de site próprio NÃO é, por si só, um contra-sinal: se a campanha vende "
    "presença digital/desenvolvimento de site, empresa sem site é PÚBLICO-ALVO (alto fit "
    "e forte oportunidade); se vende outro serviço, avalie o fit pelos demais sinais. "
    "Responda SOMENTE com JSON puro, sem markdown, sem bloco de código, "
    "sem texto antes ou depois do JSON."
)

# Esquema JSON esperado na resposta — compartilhado entre perfis.
RESPONSE_SCHEMA_HINT = """
Retorne um JSON com EXATAMENTE esta estrutura:
{
  "qualification_score": <inteiro 0-100>,
  "primary_need": "<necessidade provável do lead — pt-BR, máx 80 chars>",
  "qualification_reason": "<2-4 frases conectando evidências ao serviço que vendemos>",
  "priority": "HOT" | "WARM" | "COLD",
  "priority_reasoning": "<1-3 frases justificando a prioridade (urgência/fito/sinais), sem apenas repetir a faixa do score>",
  "executive_summary": "<2-4 frases: oportunidade principal + principal risco + abordagem recomendada>",
  "pitch_angle": "<1-2 frases FACTUAIS com PROVA: cite UMA evidência objetiva DESTE lead (descreva a dor concreta observada: ex. problema real apontado na evidência; para SEM site, cite ausência de presença digital/ferramenta usada). NUNCA genérico, NUNCA elogio vazio, NUNCA alegue sintomas técnicos sem evidência>",
  "suggested_subject": "<assunto de e-mail específico citando a dor observada NESTE lead (nunca genérico como 'Proposta de parceria')>",
  "score_factors": [
    {
      "label": "<fator curto>",
      "impact": "+" | "-",
      "weight": "high" | "medium" | "low",
      "rationale": "<1 frase: por que impacta o score>",
      "evidence_ref": "<reference pelo title em evidence[]>"
    }
  ],
  "evidence": [
    {
      "type": "<'technical' | 'business' | 'context'>",
      "severity": "CRITICO" | "ALTO" | "MEDIO" | "BAIXO" | "INFO",
      "title": "<título curto>",
      "description": "<descrição EMBUTINDO o valor concreto do fact (ex.: 'Load time 4800ms', 'Setor: metalomecânica')>",
      "source": "<'relatório técnico' | 'dados cadastrais' | 'contexto da campanha' | 'inferência LLM'>"
    }
  ]
}
"""


def _cap(text: Any, limit: int = 120) -> str:
    """Encurta um texto injetado no prompt (corte em limite de palavra).

    Sem cortar palavras no meio; preserva o início, que é onde fica o núcleo
    do sinal/evidência. Reduz os tokens de entrada por chamada de scoring sem
    trocar a natureza do fato ('a empresa é lenta: 4800ms' permanece, o resto
    de uma descrição longa é cortado com reticências).
    """
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    cut = value[:limit]
    last_space = cut.rfind(" ")
    if last_space > limit // 2:
        cut = cut[:last_space]
    return f"{cut}…"


def _cap_items(items: Optional[List[Any]], limit: int = 6, per_item: int = 120) -> List[str]:
    """Limita uma lista injetada no prompt (quantidade e tamanho de cada item)."""
    out: List[str] = []
    for item in items or []:
        if len(out) >= limit:
            out.append("…")
            break
        out.append(_cap(item, per_item))
    return out


def _format_signals(signals: List[Dict[str, Any]], header: str) -> str:
    """Formata uma lista de sinais (positive/negative/context) em texto para o prompt."""
    if not signals:
        return f"{header}:\n  (nenhum)\n"
    lines = [f"{header}:"]
    for s in signals:
        label = _cap(s.get("label", ""), 120)
        desc = _cap(s.get("description", ""), 200)
        weight = s.get("weight_hint", "medium")
        lines.append(f"  - [{weight}] {label}: {desc}")
    return "\n".join(lines) + "\n"


def build_prompt(
    target_service: str,
    target_segment: str,
    template: Optional[Dict[str, Any]],
    technical_facts: List[Dict[str, Any]],
    business_facts: List[Dict[str, Any]],
    learned_instructions: Optional[List[str]] = None,
) -> str:
    """Monta o prompt do usuário final, contextualizado para a campanha.

    Args:
        target_service: Serviço que queremos vender.
        target_segment: Segmento prospectado.
        template: Template de critérios (dict-like com positive_signals etc.).
                  Pode ser None — nesse caso pede-se à LLM que infera critérios.
        technical_facts: Facts técnicos determinísticos (lista de strings curtas).
        business_facts: Facts cadastrais (lista de strings curtas).
        learned_instructions: Regras de calibração aprendidas com correções de
                  score do time (TemplateLearning). Contexto, não comando.
    """
    lines: List[str] = []

    lines.append("== CONTEXTO DA CAMPANHA ==")
    lines.append(f"Serviço que queremos vender: {target_service or '(não informado)'}")
    lines.append(f"Segmento prospectado: {target_segment or '(não informado)'}")
    lines.append("")

    lines.append("== CRITÉRIOS ORIENTADORES ==")
    if template:
        lines.append(f"Categoria do serviço: {template.get('service_label', '(não informado)')}")
        lines.append(_format_signals(template.get("positive_signals", []), "Sinais que AUMENTAM o score (positivos)"))
        lines.append(_format_signals(template.get("negative_signals", []), "Sinais que DIMINUEM o score (negativos)"))
        lines.append(_format_signals(template.get("context_signals", []), "Sinais contextuais a considerar"))
        if template.get("extra_instructions"):
            lines.append(f"Instruções adicionais:\n  {template['extra_instructions']}\n")
    else:
        lines.append(
            "Não há template específico para este serviço. INFERA os critérios relevantes "
            "a partir do serviço e segmento informados no contexto da campanha, e explique "
            "os critérios usados dentro de priority_reasoning.\n"
        )

    if learned_instructions:
        # Regras de calibração compiladas a partir de correções de score do
        # time (TemplateLearning). Contexto de ponderação — não substituem
        # as evidências nem a decisão da LLM.
        lines.append("== AJUSTES APRENDIDOS COM O TIME ==")
        lines.append(
            "Regras derivadas de correções de score feitas por consultores "
            "desta organização. Use-as para PONDERAR os sinais acima; a "
            "decisão final continua exigindo evidência explícita:"
        )
        for rule in learned_instructions[:10]:
            lines.append(f"  - {_cap(rule, 200)}")
        lines.append("")

    lines.append("== EVIDÊNCIAS DISPONÍVEIS (facts) ==")
    lines.append("Estes são FATOS coletados passivamente — use-os como base para as evidências:")
    if technical_facts:
        lines.append("Facts técnicos do site:")
        for f in technical_facts:
            lines.append(f"  - {f}")
    else:
        lines.append("Facts técnicos do site: (não disponíveis — análise técnica não se aplica a esta categoria ou site inacessível)")
    if business_facts:
        lines.append("Facts cadastrais do lead:")
        for f in business_facts:
            lines.append(f"  - {f}")
    lines.append("")

    lines.append("== INSTRUÇÕES ==")
    lines.append("1. Use EXCLUSIVAMENTE as evidências fornecidas acima (facts + contexto).")
    lines.append("2. Se um fact técnico conflitar com a categoria (ex.: análise técnica de site para 'Engenharia Mecânica'),")
    lines.append("   trate-o como evidência secundária e pondere-o baixo no score_factors.")
    lines.append("3. Cada score_factors PRECISA referenciar uma entrada de evidence[] pelo title.")
    lines.append("4. Cada evidence[] deve EMBUTIR o valor concreto do fact (não dizer apenas 'lento', dizer '4800ms').")
    lines.append("5. priority é decisão LLM: HOT = urgência + fito + sinais de compra; COLD = poucos sinais.")
    lines.append("   Não derive priority matematicamente do score — justifique em priority_reasoning.")
    lines.append("6. qualification_score 0-100, guideline: 80-100 várias evidências fortes; 60-79 fito razoável;")
    lines.append("   40-59 fito parcial; 20-39 poucos sinais; 0-19 não se encaixa ou sinais contrários.")
    lines.append("7. A presença de site é fato determinístico: se os facts disserem 'Tem website: sim',")
    lines.append("   NUNCA afirme que o lead não tem site nem use 'ausência de site' como dor.")
    lines.append("   A mesma regra vale ao contrário.")
    if _campaign_sells_web_presence(template, target_service):
        lines.append("8. ESTA campanha vende presença digital/desenvolvimento de site: um lead SEM site")
        lines.append("   próprio (sem website ou só com Instagram/WhatsApp/Canva) é PÚBLICO-ALVO.")
        lines.append("   Trate a ausência de site como oportunidade FORTE (aumente o score) e não")
        lines.append("   desqualifique por causa dela — use-a como dor no pitch/suggested_subject.")
        lines.append("   TAMBÉM é público-alvo o lead com site próprio de BAIXA QUALIDADE:")
        lines.append("   plataforma gratuita/amadora (Blogspot/Blogger, Wix grátis, Google Sites),")
        lines.append("   sem domínio próprio, ou com vários problemas de UX/SEO (sem responsividade,")
        lines.append("   sem formulário/CTA, SEO quebrado). Esse lead JÁ entende o valor de presença")
        lines.append("   digital e precisa RENOVAR o site — trate como oportunidade FORTE e NUNCA")
        lines.append("   desqualifique pela má qualidade do site; use-a como dor no pitch.")
        lines.append("   Os facts 'Plataforma gratuita/amadora detectada' e 'Qualidade do site:'")
        lines.append("   são as evidências determinísticas desses sinais.")
        # 8b — SaaS de terceiros: SEMPRE presente, mesmo em campanhas de
        # presença digital (um lead com site só de anota.ai não precisa de
        # "site institucional", mas talvez precise de presença digital completa).
        lines.append(
            "8b. Se o fact 'Lead usa plataforma SaaS de terceiros' estiver presente, o "
            "site do lead NÃO é domínio próprio — é uma vitrine/loja de plataforma "
            "(anota.ai, iFood, Rappi, Aimpire, Pedidosky etc.) para pedidos/delivery/"
            "cardápio. NÃO trate esses sinais como 'área logada/portal do lead'. "
            "Pode ser gancho para venda de presença digital completa."
        )
    else:
        lines.append("8. A ausência de site próprio é NEUTRA para o fit desta campanha (engenharia, projetos CAD, corte laser, MDF, troféus, ERP/sistemas ou consultoria):")
        lines.append("   avalie o fito principalmente pelas palavras-chave de atuação/produtos, CNAEs e porte cadastral.")
        lines.append("   NÃO desqualifique nem reduza o score por questões de SEO/SSL/performance do site — elas são irrelevantes.")
        # 8b — SaaS de terceiros: presente em campanhas não-web-presence.
        # Particularmente importante para o template "Aplicações Web / ERP":
        # corrige o falso-positivo histórico em que leads hospedados em
        # plataformas de pedidos eram pontuados como se o "login/sistema" do
        # SaaS fosse automação própria do lead.
        lines.append(
            "8b. Se o fact 'Lead usa plataforma SaaS de terceiros' estiver presente, o "
            "site do lead NÃO é domínio próprio — é uma vitrine/loja de plataforma "
            "(anota.ai, iFood, Rappi, Aimpire, Pedidosky etc.) para pedidos/delivery/"
            "cardápio. Esses SaaS SUBSTITUEM apenas o canal de pedidos online, NÃO "
            "substituem ERP/sistema de gestão. O lead provavelmente AINDA tem processo "
            "manual interno (planilha/WhatsApp/papel) para estoque, financeiro, agenda, "
            "CRM. NUNCA afirme 'o lead já tem sistema próprio' baseado em SaaS de "
            "delivery, e NUNCA afirme 'processo manual' só porque o site é só vitrine."
        )
    # 8c: foco em porte/CNAE/idade/segmento quando ERP. Complementa 8b para a
    # venda B2B de sistemas web completos / ERP — só ativo nesse template.
    if _campaign_sells_erp_webapps(template, target_service):
        lines.append(
            "8c. Venda de SISTEMA WEB COMPLETO / ERP: o fito vem principalmente do "
            "PORTE cadastral, IDADE, CNAE e SEGMENTO do lead, não da qualidade do site:"
        )
        lines.append(
            "    - Microempresa/MEI raramente justifica ERP sob medida — pondere baixo."
        )
        lines.append(
            "    - Lead com CNAE de software/TI/desenvolvimento/SaaS é POTENCIAL "
            "CONCORRENTE ou já é digital demais — pondere baixo."
        )
        lines.append(
            "    - Lead com CNAE de serviço/operação com processos replicáveis "
            "(saúde/educação/serviços especializados/logística/varejo) tem alta chance "
            "de se beneficiar — pondere como público-alvo."
        )
        lines.append(
            "    - Empresa jovem (< 2 anos) ainda estruturando processos: público-alvo "
            "forte (sistema entra junto com a operação). Empresa com > 10 anos e porte "
            "médio/grande provavelmente já tem sistema legado: fito baixo para troca."
        )
        lines.append(
            "    - Empresa com boa reputação Google + poucas avaliações (<=30) = "
            "operação pequena, processo provavelmente manual: pondere como público-alvo."
        )
    lines.append("9. Os sinais do template (CRITÉRIOS) NÃO são fatos do lead: nunca inclua em evidence[],")
    lines.append("   pitch_angle ou suggested_subject um sintoma (ex.: 'sem responsividade', 'sem formulário/CTA',")
    lines.append("   'site desatualizado') que não tenha fact correspondente nas EVIDÊNCIAS acima.")
    lines.append("10. pitch_angle e suggested_subject DEVEM referenciar um evidence.title e só podem alegar")
    lines.append("    sintomas técnicos/UX (responsividade, formulário, CTA, atualização, performance, SSL, CMS, WhatsApp)")
    lines.append("    se houver evidência explícita correspondente.")
    lines.append("")

    lines.append(RESPONSE_SCHEMA_HINT)
    return "\n".join(lines)


def extract_technical_facts(report: Dict[str, Any]) -> List[str]:
    """Camada determinística: transforma o relatório técnico em facts curtos.

    Esta é a fonte de evidência reprodutível — a LLM não inventa valores.
    """
    if not report:
        return []
    facts: List[str] = []

    ssl = report.get("ssl") or {}
    if ssl.get("ssl_ok"):
        facts.append("SSL/HTTPS válido")
    else:
        err = ssl.get("error") or "sem certificado válido"
        facts.append(f"SSL/HTTPS inválido ou ausente: {err}")
    if ssl.get("https_redirect_ok"):
        facts.append("Redirecionamento HTTP→HTTPS ativo")
    else:
        facts.append("Redirecionamento HTTP→HTTPS ausente")

    hh = report.get("http_headers") or {}
    code = hh.get("status_code")
    if code:
        facts.append(f"HTTP status: {code}")
    lt = hh.get("load_time_ms")
    if lt is not None:
        facts.append(f"Load time: {lt}ms")
    missing = hh.get("security_headers_missing") or []
    if missing:
        facts.append(f"Headers de segurança ausentes: {', '.join(_cap_items(missing, limit=5, per_item=40))}")
    else:
        facts.append("Headers de segurança presentes")

    cms = report.get("cms_detection")
    if cms:
        facts.append(f"CMS/tecnologia detectada: {cms}")
    else:
        facts.append("Nenhum CMS/tecnologia identificado")

    # Qualidade da plataforma: hospedagem gratuita/amadora e ausência de
    # domínio próprio são sinais determinísticos de oportunidade de redesign
    # (a LLM decide o peso; campanhas fora de presença digital ponderam baixo).
    pq = report.get("platform_quality") or {}
    if pq.get("is_free_platform"):
        name = pq.get("platform") or "hospedagem gratuita"
        dom = "" if pq.get("custom_domain", True) else ", sem domínio próprio"
        facts.append(
            f"Plataforma gratuita/amadora detectada: {name}{dom} "
            "(indício de pouco investimento em presença digital)"
        )

    perf = report.get("performance") or {}
    if perf.get("rating"):
        facts.append(f"Performance rating: {perf.get('rating')} ({lt}ms)" if lt is not None else f"Performance rating: {perf.get('rating')}")

    seo = report.get("seo") or {}
    if seo:
        issues = seo.get("issues") or []
        if issues:
            facts.append(f"SEO/LGPD issues: {', '.join(_cap_items(issues, limit=5, per_item=60))}")
        else:
            facts.append("SEO e menção a LGPD OK")

    exposed = report.get("exposed_paths") or []
    if exposed:
        facts.append(f"Caminhos sensíveis expostos: {', '.join(_cap_items(exposed, limit=5, per_item=60))}")
    else:
        facts.append("Nenhum caminho sensível exposto")

    ux = report.get("ux") or {}
    if ux:
        if ux.get("viewport_ok"):
            facts.append("Meta viewport presente (layout mobile-friendly)")
        else:
            facts.append("Meta viewport ausente (provável layout não mobile-friendly)")
        if ux.get("contact_form_found"):
            facts.append("Formulário de contato presente na página")
        else:
            facts.append("Formulário de contato ausente na página")
        canais = []
        if ux.get("tel_link_found"):
            canais.append("telefone")
        if ux.get("whatsapp_link_found"):
            canais.append("WhatsApp")
        if ux.get("mailto_link_found"):
            canais.append("e-mail")
        if canais:
            facts.append(f"Canais de contato clicáveis na home: {', '.join(canais)}")
        else:
            facts.append("Nenhum canal de contato clicável (telefone/WhatsApp/e-mail) na home")

        # Plataforma SaaS de terceiros detectada — anota.ai, iFood, Rappi etc.
        # Importante para todos os templates, mas principalmente para "Aplicações
        # Web / ERP": o "login/portal/sistema" que aparece nessas plataformas
        # é do SaaS, não do lead. Tratar isso como evidência de "lead já tem
        # sistema" é o erro clássico do scoring (false positive).
        if ux.get("is_third_party_saas"):
            platform = ux.get("third_party_platform") or "plataforma SaaS"
            facts.append(
                f"Lead usa plataforma SaaS de terceiros ({platform}): o site não é "
                "domínio próprio — é vitrine/loja do SaaS (delivery/pedidos/cardápio). "
                "Sinais de 'login/sistema' detectados pertencem ao SaaS, não ao lead."
            )
        else:
            # Área logada/portal e menção a sistema — evidência determinística
            # usada pelo template "Aplicações Web / ERP": empresa com área logada
            # ou que cita sistema próprio provavelmente JÁ tem automação (reduz o
            # fit); site só institucional sem portal sugere processo manual.
            if ux.get("login_portal_found"):
                facts.append("Área logada/portal/painel presente na página (indício de sistema próprio)")
            else:
                facts.append("Nenhuma área logada/portal/painel encontrada na página")
            if ux.get("system_mention_found"):
                facts.append("Menção a sistema/ERP/software na página (indício de automação)")
            else:
                facts.append("Nenhuma menção a sistema/ERP/software na página")

    # Resumo consolidado de qualidade: quando o site acumula vários problemas
    # de UX/SEO, isso é evidência concreta de necessidade de redesign (o eixo
    # não é "tem site" vs "não tem", é "site bom" vs "site ruim").
    total_issues = len((report.get("seo") or {}).get("issues") or []) + len(
        (report.get("ux") or {}).get("issues") or []
    )
    if total_issues >= 3:
        facts.append(f"Qualidade do site: {total_issues} problemas de UX/SEO detectados (candidato a redesign)")

    warnings = report.get("warnings") or []
    if warnings:
        facts.append(f"Avisos gerais: {', '.join(_cap_items(warnings, limit=5, per_item=60))}")
    errors = report.get("errors") or []
    if errors:
        facts.append(f"Erros gerais: {', '.join(_cap_items(errors, limit=5, per_item=60))}")

    domain_copy = report.get("domain_copy") or {}
    if domain_copy:
        meta_desc = domain_copy.get("meta_description")
        if meta_desc:
            facts.append(f"Descrição do negócio no site: {_cap(meta_desc, 160)}")
        headings = domain_copy.get("headings")
        if headings:
            facts.append(f"Destaques/Serviços no site: {'; '.join(_cap_items(headings, limit=5, per_item=80))}")
        kw_mech = domain_copy.get("keywords_mechanical")
        if kw_mech:
            facts.append(f"Capacidades/Processos industriais detectados no site: {', '.join(_cap_items(kw_mech, limit=6, per_item=40))}")
        kw_craft = domain_copy.get("keywords_custom_craft")
        if kw_craft:
            facts.append(f"Produtos/Serviços sob medida detectados no site: {', '.join(_cap_items(kw_craft, limit=6, per_item=40))}")
        kw_sys = domain_copy.get("keywords_systems")
        if kw_sys:
            facts.append(f"Termos de sistemas/tecnologia no site: {', '.join(_cap_items(kw_sys, limit=6, per_item=40))}")
        snippet = domain_copy.get("snippet")
        if snippet and len(snippet) > 40:
            facts.append(f"Trecho resumo do site: {_cap(snippet, 200)}")

    return facts


def extract_business_facts(
    company_name: str,
    category: str,
    city: str,
    state: str,
    website: Optional[str],
    google_rating: Optional[float] = None,
    google_rating_count: Optional[int] = None,
    cnae_info: Optional[str] = None,
    company_size_info: Optional[str] = None,
) -> List[str]:
    facts: List[str] = []
    facts.append(f"Empresa: {company_name}")
    if category:
        facts.append(f"Categoria (Google Places): {category}")
    else:
        facts.append("Categoria (Google Places): não informada")
    if cnae_info:
        facts.append(f"Atividade econômica (CNAE/Receita): {cnae_info}")
    if company_size_info:
        facts.append(f"Porte/Estrutura cadastral: {company_size_info}")
    facts.append(f"Localização: {city}, {state}")
    facts.append(f"Tem website: {'sim' if website else 'não'}")
    if website:
        facts.append(f"Website URL: {website}")
    # O segmento-alvo da campanha é CONTEXTO (já vai no prompt como tal) e
    # não é um fato do lead. Injetá-lo aqui como fact cadastral faz a LLM
    # tratar o alvo da prospecção como característica do lead (ex.: portal de
    # notícias sem categoria vira "comércio" e pontua alto errado).
    # Reputação no Google — dor observável: negócio
    # mal avaliado = oportunidade (interpretação do template decide o sinal).
    if google_rating is not None:
        count = f" com {int(google_rating_count)} avaliações" if google_rating_count else ""
        facts.append(f"Reputação Google: {google_rating:.1f}★{count}")
    return facts


class AIScoringService:
    """Serviço de scoring contextual e explicável via Groq (modelo de classificação)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY

    # ---------- normalização da resposta ----------

    def _normalize_response(
        self,
        parsed: Dict[str, Any],
        has_website: Optional[bool] = None,
        target_service: str = "",
    ) -> Dict[str, Any]:
        """Normaliza e valida o JSON devolvido pela LLM.

        Garante defaults e tipos para todos os campos esperados pela camada
        de persistência (orchestrator).

        `has_website` ativa o guard determinístico de presença de site: remove
        evidências que contradizem o fato cadastral (ex.: "sem site próprio"
        quando o lead TEM website, ou "tem site" quando não tem).
        """
        try:
            score = int(parsed.get("qualification_score", 0))
        except (TypeError, ValueError):
            score = 0
        score = max(0, min(100, score))
        parsed["qualification_score"] = score

        parsed["primary_need"] = str(parsed.get("primary_need") or "")[:255]
        parsed["qualification_reason"] = str(parsed.get("qualification_reason") or "")
        parsed["priority"] = str(parsed.get("priority") or "").upper()
        if parsed["priority"] not in ("HOT", "WARM", "COLD"):
            parsed["priority"] = ""
        parsed["priority_reasoning"] = str(parsed.get("priority_reasoning") or "")
        parsed["executive_summary"] = str(parsed.get("executive_summary") or "")
        parsed["pitch_angle"] = str(parsed.get("pitch_angle") or "")
        parsed["suggested_subject"] = str(parsed.get("suggested_subject") or "")

        score_factors = parsed.get("score_factors") or []
        if not isinstance(score_factors, list):
            score_factors = []

        evidence = parsed.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = []

        # Evidência com origem "inferência LLM" não é
        # fact — não deve chegar ao outreach como "facto" (risco de citar
        # alucinação em e-mail frio). Mantém apenas o que é fundamentado em
        # relatório técnico, dados cadastrais ou contexto da campanha.
        GROUNDED_SOURCES = ("relatório técnico", "relatório tecnico",
                            "dados cadastrais", "contexto da campanha")
        clean_evidence = []
        for e in evidence:
            if not isinstance(e, dict):
                continue
            source = str(e.get("source") or "").lower().strip()
            if "inferência" in source or "inferencia" in source:
                continue
            sev = str(e.get("severity") or "INFO").upper()
            if sev not in ("CRITICO", "ALTO", "MEDIO", "BAIXO", "INFO"):
                sev = "INFO"
            clean_evidence.append({
                "type": str(e.get("type") or "")[:40],
                "severity": sev,
                "title": str(e.get("title") or "")[:160],
                "description": str(e.get("description") or ""),
                "source": str(e.get("source") or "")[:60],
            })
        if has_website is not None:
            clean_evidence = [
                e for e in clean_evidence if not _contradicts_site_state(e, has_website)
            ]
        parsed["evidence"] = clean_evidence
        # Grounding do pitch/subject (Frente A): substitui alegações sem
        # suporte nas evidências por versão determinística (sempre factual).
        _ground_pitch_fields(parsed, clean_evidence, target_service)
        # Valida evidence_ref dos fatores: só mantém fatores que apontam para
        # uma evidência que permaneceu (evita referência quebrada na UI).
        kept_titles = {e["title"] for e in clean_evidence if e["title"]}
        clean_factors = []
        for f in score_factors:
            if not isinstance(f, dict):
                continue
            ref = str(f.get("evidence_ref") or "").strip()
            if not ref or ref not in kept_titles:
                continue
            impact = str(f.get("impact") or "").strip()
            if impact not in ("+", "-"):
                impact = "+"
            weight = str(f.get("weight") or "medium").lower()
            if weight not in ("high", "medium", "low"):
                weight = "medium"
            clean_factors.append({
                "label": str(f.get("label") or "")[:120],
                "impact": impact,
                "weight": weight,
                "rationale": str(f.get("rationale") or ""),
                "evidence_ref": ref[:120],
            })
        parsed["score_factors"] = clean_factors

        # Vetor multidimensional (docs/melhorias/02): aceito quando a LLM
        # devolve dimensões; clamp 0-100 e `overall` derivado da média quando
        # ausente. Sem dimensões devolvidas, fica ausente (compatibilidade).
        raw_vector = parsed.get("score_vector")
        if isinstance(raw_vector, dict):
            clean_vector = {
                k: max(0, min(100, int(v)))
                for k, v in raw_vector.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            }
            if clean_vector:
                if "overall" not in clean_vector:
                    clean_vector["overall"] = round(
                        sum(v for k, v in clean_vector.items() if k != "formula_version")
                        / len(clean_vector)
                    )
                clean_vector.setdefault("formula_version", "generic-v1")
                raw_version = raw_vector.get("formula_version")
                if isinstance(raw_version, str) and raw_version.strip():
                    clean_vector["formula_version"] = raw_version.strip()[:60]
                parsed["score_vector"] = clean_vector
            else:
                parsed.pop("score_vector", None)

        return parsed

    # ---------- chamada ao modelo ----------

    async def _call_groq(
        self,
        user_prompt: str,
        has_website: Optional[bool] = None,
        db=None,
        organization_id: Optional[str] = None,
        target_service: str = "",
    ) -> Optional[Dict[str, Any]]:
        from services.provider_client import groq_json_chat

        parsed = await groq_json_chat(
            api_key=self.api_key or "",
            model=GROQ_MODEL,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            url=GROQ_URL,
            temperature=0.2,
            db=db,
            organization_id=organization_id,
        )
        if parsed is None:
            return None
        return self._normalize_response(parsed, has_website=has_website, target_service=target_service)

    # ---------- API pública ----------

    async def score_lead(
        self,
        technical_report: dict,
        target_service: str = "",
        target_segment: str = "",
        template: Optional[Dict[str, Any]] = None,
        company_name: str = "",
        category: str = "",
        city: str = "",
        state: str = "",
        website: Optional[str] = None,
        google_rating: Optional[float] = None,
        google_rating_count: Optional[int] = None,
        cnae_info: Optional[str] = None,
        company_size_info: Optional[str] = None,
        db=None,
        organization_id: Optional[str] = None,
        learned_instructions: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Scoring contextual de um lead com site (web_presence).

        Combina facts técnicos do relatório + facts cadastrais, monta o prompt
        usando o template de critérios (se houver), e devolve a qualificação
        explicável.

        Args:
            technical_report: Relatório de TechnicalEnrichmentService.enrich_website.
            target_service / target_segment: Contexto da campanha.
            template: Optional[dict] — serialização de CampaignScoringTemplate.
                      Se None, a LLM infere os critérios.
            company_name / category / city / state / website: dados cadastrais
                complementares, usados para enriquecer facts de business.
            cnae_info / company_size_info: dados da Receita Federal (CNPJ)
                quando o template pede enriquecimento cadastral.

        Returns:
            Dicionário normalizado com qualification_score, primary_need,
            qualification_reason, priority, priority_reasoning,
            executive_summary, pitch_angle, suggested_subject,
            score_factors[], evidence[], ou None em caso de falha.
        """
        technical_facts = extract_technical_facts(technical_report)
        business_facts = extract_business_facts(
            company_name=company_name,
            category=category,
            city=city,
            state=state,
            website=website,
            google_rating=google_rating,
            google_rating_count=google_rating_count,
            cnae_info=cnae_info,
            company_size_info=company_size_info,
        )
        prompt = build_prompt(
            target_service=target_service,
            target_segment=target_segment,
            template=template,
            technical_facts=technical_facts,
            business_facts=business_facts,
            learned_instructions=learned_instructions,
        )
        return await self._call_groq(
            prompt, has_website=bool(website), db=db,
            organization_id=organization_id, target_service=target_service,
        )

    async def score_business_lead(
        self,
        company_name: str,
        category: str = "",
        city: str = "",
        state: str = "",
        website: Optional[str] = None,
        target_service: str = "",
        target_segment: str = "",
        template: Optional[Dict[str, Any]] = None,
        google_rating: Optional[float] = None,
        google_rating_count: Optional[int] = None,
        cnae_info: Optional[str] = None,
        company_size_info: Optional[str] = None,
        db=None,
        organization_id: Optional[str] = None,
        learned_instructions: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Scoring contextual de um lead sem análise técnica (business_opportunity).

        Mesma resposta que score_lead, mas sem facts técnicos. Usado quando o
        template de categoria define requires_technical_report=False (ex.:
        Engenharia Mecânica, Automação Industrial, Consultoria).
        """
        business_facts = extract_business_facts(
            company_name=company_name,
            category=category,
            city=city,
            state=state,
            website=website,
            google_rating=google_rating,
            google_rating_count=google_rating_count,
            cnae_info=cnae_info,
            company_size_info=company_size_info,
        )
        prompt = build_prompt(
            target_service=target_service,
            target_segment=target_segment,
            template=template,
            technical_facts=[],
            business_facts=business_facts,
            learned_instructions=learned_instructions,
        )
        # Guard determinístico de presença de site: sem site → remove
        # evidências que afirmem que o lead TEM site.
        return await self._call_groq(
            prompt, has_website=bool(website), db=db,
            organization_id=organization_id, target_service=target_service,
        )


async def main_test_scoring():
    """Smoke test: scoring de exemplo para 'Engenharia Mecânica'."""
    service = AIScoringService()
    template = {
        "service_label": "Engenharia Mecânica",
        "positive_signals": [
            {"label": "Indústria/fábrica", "description": "Categoria industrial", "weight_hint": "high"},
        ],
        "negative_signals": [],
        "context_signals": [],
        "extra_instructions": "Ignore qualidade do site.",
    }
    result = await service.score_business_lead(
        company_name="Metalúrgica Brasil SA",
        category="metalúrgica",
        city="São Paulo",
        state="SP",
        website="https://example.com",
        target_service="Projetos de Engenharia Mecânica",
        target_segment="metalomecânica",
        template=template,
    )
    logger.info("%s", json.dumps(result, ensure_ascii=False, indent=2) if result else "None")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_test_scoring())
