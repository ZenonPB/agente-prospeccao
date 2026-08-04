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
import sys
from typing import Any, Dict, List, Optional

import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.settings import settings  # noqa: E402

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = (
    "Você é um consultor comercial B2B especializado em prospecção qualificada. "
    "Avalia empresas com base no CONTEXTO da campanha (serviço que se quer vender + "
    "segmento prospectado) e nos critérios orientadores fornecidos. "
    "Toda conclusão deve ser JUSTIFICADA por evidências explícitas — nunca retorne "
    "apenas uma pontuação. "
    "Responda SOMENTE com JSON puro, sem markdown, sem bloco de código, "
    "sem texto antes ou depois do JSON."
)

# Esquema JSON esperado na resposta — compartilhado entre perfis.
RESPONSE_SCHEMA_HINT = """
Retorne um JSON com EXATAMENTE esta estrutura:
{
  "qualification_score": <inteiro 0-100>,
  "primary_need": "<necessidade provável do lead neste contexto — string livre em pt-BR, máx 80 chars>",
  "qualification_reason": "<2-4 frases em pt-BR explicando o raciocínio que justifica o score, conectando evidências ao serviço que queremos vender>",
  "priority": "HOT" | "WARM" | "COLD",
  "priority_reasoning": "<1-3 frases em pt-BR justificando a prioridade. Não use simplesmente a faixa do score — explique o que torna o lead hot/warm/cold (urgência, fito, sinais de compra, etc.)>",
  "executive_summary": "<2-4 frases em pt-BR com o resumo consultor comercial: principal oportunidade + principal risco + recomendação de abordagem>",
  "pitch_angle": "<1-2 frases: gancho principal de abordagem, baseado nas evidências e no serviço que queremos vender>",
  "suggested_subject": "<sugestão de assunto de e-mail de prospecção personalizada>",
  "score_factors": [
    {
      "label": "<nome curto do fator>",
      "impact": "+" | "-",
      "weight": "high" | "medium" | "low",
      "rationale": "<1 frase: por que este fator impacta o score neste contexto>",
      "evidence_ref": "<referência à entrada correspondente em evidence[], pelo title>"
    }
  ],
  "evidence": [
    {
      "type": "<categoria: 'technical' | 'business' | 'context'>",
      "severity": "CRITICO" | "ALTO" | "MEDIO" | "BAIXO" | "INFO",
      "title": "<título curto da evidência>",
      "description": "<descrição em pt-BR EMBUTINDO o valor concreto (ex.: 'WordPress 5.8 detectado', 'Load time 4800ms', 'Setor: metalomecânica')>",
      "source": "<origem: 'relatório técnico' | 'dados cadastrais' | 'contexto da campanha' | 'inferência LLM'>"
    }
  ]
}
"""


def _format_signals(signals: List[Dict[str, Any]], header: str) -> str:
    """Formata uma lista de sinais (positive/negative/context) em texto para o prompt."""
    if not signals:
        return f"{header}:\n  (nenhum)\n"
    lines = [f"{header}:"]
    for s in signals:
        label = s.get("label", "")
        desc = s.get("description", "")
        weight = s.get("weight_hint", "medium")
        lines.append(f"  - [{weight}] {label}: {desc}")
    return "\n".join(lines) + "\n"


def build_prompt(
    target_service: str,
    target_segment: str,
    template: Optional[Dict[str, Any]],
    technical_facts: List[Dict[str, Any]],
    business_facts: List[Dict[str, Any]],
) -> str:
    """Monta o prompt do usuário final, contextualizado para a campanha.

    Args:
        target_service: Serviço que queremos vender.
        target_segment: Segmento prospectado.
        template: Template de critérios (dict-like com positive_signals etc.).
                  Pode ser None — nesse caso pede-se à LLM que infera critérios.
        technical_facts: Facts técnicos determinísticos (lista de strings curtas).
        business_facts: Facts cadastrais (lista de strings curtas).
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
    lines.append("2. Se um fact técnico conflitar com a categoria (ex.: analysis técnica de site para 'Engenharia Mecânica'),")
    lines.append("   trate-o como evidência secundária e pondere-o baixo no score_factors.")
    lines.append("3. Cada score_factors PRECISA referenciar uma entrada de evidence[] pelo title.")
    lines.append("4. Cada evidence[] deve EMBUTIR o valor concreto do fact (não dizer apenas 'lento', dizer '4800ms').")
    lines.append("5. priority é decisão LLM: HOT = urgência + fito + sinais de compra; COLD = poucos sinais.")
    lines.append("   Não derive priority matematicamente do score — justifique em priority_reasoning.")
    lines.append("6. qualification_score 0-100, guideline geral:")
    lines.append("   - 80-100: várias evidências positivas fortes para ESTA campanha")
    lines.append("   - 60-79: fito razoável, alguns sinais positivos")
    lines.append("   - 40-59: fito parcial / sinais mistos")
    lines.append("   - 20-39: poucos sinais relevantes para a campanha")
    lines.append("   - 0-19:  não se encaixa ou sinais contrários")
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
        facts.append(f"Headers de segurança ausentes: {', '.join(missing)}")
    else:
        facts.append("Headers de segurança presentes")

    cms = report.get("cms_detection")
    if cms:
        facts.append(f"CMS/tecnologia detectada: {cms}")
    else:
        facts.append("Nenhum CMS/tecnologia identificado")

    perf = report.get("performance") or {}
    if perf.get("rating"):
        facts.append(f"Performance rating: {perf.get('rating')} ({lt}ms)" if lt is not None else f"Performance rating: {perf.get('rating')}")

    seo = report.get("seo") or {}
    if seo:
        issues = seo.get("issues") or []
        if issues:
            facts.append(f"SEO/LGPD issues: {', '.join(issues)}")
        else:
            facts.append("SEO e menção a LGPD OK")

    exposed = report.get("exposed_paths") or []
    if exposed:
        facts.append(f"Caminhos sensíveis expostos: {', '.join(exposed)}")
    else:
        facts.append("Nenhum caminho sensível exposto")

    warnings = report.get("warnings") or []
    if warnings:
        facts.append(f"Avisos gerais: {', '.join(warnings[:5])}")
    errors = report.get("errors") or []
    if errors:
        facts.append(f"Erros gerais: {', '.join(errors[:5])}")

    return facts


def extract_business_facts(
    company_name: str,
    category: str,
    city: str,
    state: str,
    website: Optional[str],
    segment_hint: str,
) -> List[str]:
    facts: List[str] = []
    facts.append(f"Empresa: {company_name}")
    if category:
        facts.append(f"Categoria (Google Places): {category}")
    facts.append(f"Localização: {city}, {state}")
    facts.append(f"Tem website: {'sim' if website else 'não'}")
    if website:
        facts.append(f"Website URL: {website}")
    if segment_hint:
        facts.append(f"Segmento declarado na campanha: {segment_hint}")
    return facts


class AIScoringService:
    """Serviço de scoring contextual e explicável via Groq (llama-3.1-8b-instant)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY

    def _create_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=60.0,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    # ---------- normalização da resposta ----------

    def _normalize_response(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Normaliza e valida o JSON devolvido pela LLM.

        Garante defaults e tipos para todos os campos esperados pela camada
        de persistência (orchestrator).
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
        clean_factors = []
        for f in score_factors:
            if not isinstance(f, dict):
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
                "evidence_ref": str(f.get("evidence_ref") or "")[:120],
            })
        parsed["score_factors"] = clean_factors

        evidence = parsed.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = []
        clean_evidence = []
        for e in evidence:
            if not isinstance(e, dict):
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
        parsed["evidence"] = clean_evidence

        return parsed

    def _parse_response(self, content: str) -> Optional[Dict[str, Any]]:
        if not content:
            logger.warning("Resposta vazia do Groq.")
            return None

        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("Falha ao decodificar JSON do Groq: %s", e)
            return None

    # ---------- chamada ao modelo ----------

    async def _call_groq(self, user_prompt: str) -> Optional[Dict[str, Any]]:
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        try:
            async with self._create_client() as client:
                response = await client.post(GROQ_URL, json=payload)
        except httpx.RequestError as e:
            logger.error("Erro de rede ao chamar Groq: %s", e)
            return None

        if response.status_code != 200:
            logger.error("Groq respondeu HTTP %s: %s", response.status_code, response.text[:500])
            return None

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            logger.error("Resposta do Groq não é JSON: %s", e)
            return None

        choices = data.get("choices") or []
        if not choices:
            logger.error("Resposta do Groq sem choices: %s", data)
            return None

        content = choices[0].get("message", {}).get("content", "")
        parsed = self._parse_response(content)
        if parsed is None:
            return None
        return self._normalize_response(parsed)

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
            segment_hint=target_segment,
        )
        prompt = build_prompt(
            target_service=target_service,
            target_segment=target_segment,
            template=template,
            technical_facts=technical_facts,
            business_facts=business_facts,
        )
        return await self._call_groq(prompt)

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
            segment_hint=target_segment,
        )
        prompt = build_prompt(
            target_service=target_service,
            target_segment=target_segment,
            template=template,
            technical_facts=[],
            business_facts=business_facts,
        )
        return await self._call_groq(prompt)


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
