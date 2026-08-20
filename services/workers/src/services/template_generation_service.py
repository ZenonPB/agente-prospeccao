"""TemplateGenerationService — gera critérios de scoring sob demanda.

Quando o `template_router` retorna `GENERATE_NEW` (vertical sem template
existente), este serviço pede à LLM que defina os critérios de qualificação
relevantes para o serviço/segmento informado e os persiste em
`campaign_scoring_templates` com `is_generated=True` e `organization_id`.

Nada hardcoded: cada vertical nova gera os seus próprios sinais. O template
gerado é reutilizado em campanhas seguintes da mesma org (match por label).

Modelo: Groq de geração configurado em `settings.GROQ_MODEL_GENERATION`
(geração de critérios precisa de modelo de texto).
Fallback: se a LLM falhar ou retornar JSON inválido, devolve o template
'Genérico' (não quebra o pipeline).
"""
import logging
import os
import sys
from typing import Any, Dict, Optional

from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.settings import settings  # noqa: E402
from database.models import CampaignScoringTemplate  # noqa: E402

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = settings.GROQ_MODEL_GENERATION

SYSTEM_PROMPT = (
    "Você é um consultor de pré-vendas B2B especializado em prospecção "
    "qualificada para o mercado brasileiro. Você define CRITÉRIOS DE "
    "QUALIFICAÇÃO (sinais de compra/aptidão) para um serviço/segmento que "
    "alguém quer vender. Os sinais devem ser concretos, observáveis a partir "
    "de dados públicos (site, texto de serviços, dados cadastrais CNPJ, "
    "palavras-chave de atuação, categoria, porte, segmento) e relevantes PARA ESTE "
    "serviço específico — não genéricos. "
    "Responda SOMENTE com JSON puro, sem markdown, sem bloco de código. "
    "\n\nDIRETRIZES POR ARQUÉTIPO DE SERVIÇO:\n"
    "1. SERVIÇOS DIGITAIS (Landing Pages, Sites, SEO): ausência ou fraqueza do site AUMENTA o score.\n"
    "2. SISTEMAS / ERPs / WEB APPS: operação em crescimento + ausência de área logada/portal AUMENTA o score. Ignore SEO.\n"
    "3. ENGENHARIA / PROJETOS CAD / AUTOMAÇÃO: setor industrial/manufatura + necessidade de modelagem 3D, projetos mecânicos ou peças AUMENTA o score. Ignore totalmente métricas de SEO/SSL.\n"
    "4. FABRICAÇÃO E PRODUTOS PERSONALIZADOS (MDF, Troféus, Chaveiros, Corte Laser, Brindes): fito com eventos, RH, premiações, comunicação visual ou brindes corporativos sob medida AUMENTA o score. Ignore SEO/SSL.\n"
    "5. SERVIÇOS GERAIS: porte cadastral + maturidade organizacional."
)

SCHEMA_HINT = """
Retorne um JSON com EXATAMENTE esta estrutura:
{
  "service_label": "<nome curto do serviço, máx 80 chars, ex.: 'Landing Pages para Clínicas de Saúde'>",
  "requires_technical_report": true,
  "requires_business_data": true,
  "positive_signals": [
    {"label": "<nome curto do sinal>", "description": "<como identificar/por que importa>", "weight_hint": "high"}
  ],
  "negative_signals": [
    {"label": "<nome curto>", "description": "<por que reduz o score>", "weight_hint": "medium"}
  ],
  "context_signals": [
    {"label": "Segmento", "description": "<fito do segmento com este serviço>"},
    {"label": "Região", "description": "<relevância regional>"}
  ],
  "extra_instructions": "<2-4 frases orientando o avaliador sobre o que priorizar e o que ignorar neste serviço>"
}

Regras:
- positive_signals: 4-7 sinais; weight_hint em "high" | "medium" | "low".
- negative_signals: 2-4 sinais.
- requires_technical_report: true apenas se análise do site for relevante
  (ex.: landing pages/web = true; engenharia mecânica/consultoria = false).
- requires_business_data: true se dados cadastrais/porte/segmento importam.
- As descrições devem ser verificáveis a partir de dados públicos.
"""


def build_prompt(target_service: str, target_segment: str = "", description: str = "") -> str:
    """Monta o prompt do usuário com a oferta a ser qualificada.

    `description` é um contexto livre em linguagem natural (ex.: público-alvo,
    diferencial, dor a resolver) usado pelo criador visual de vertentes.
    """
    lines: list[str] = []
    lines.append("== OFERTA A SER QUALIFICADA ==")
    lines.append(f"Serviço que queremos vender: {target_service or '(não informado)'}")
    lines.append(f"Segmento prospectado: {target_segment or '(não informado)'}")
    if description:
        lines.append(f"Contexto adicional: {description}")
    lines.append("")
    lines.append("Defina os critérios de qualificação mais relevantes para esta oferta.")
    lines.append("Lembre-se: sinais devem ser observáveis passivamente (site, CNPJ, porte, categoria).")
    lines.append("")
    lines.append(SCHEMA_HINT)
    return "\n".join(lines)


def _validate(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Valida e normaliza o JSON gerado para o schema do seed."""
    label = str(data.get("service_label", "")).strip()
    if not label:
        return None

    positive = data.get("positive_signals") or []
    negative = data.get("negative_signals") or []
    context = data.get("context_signals") or []
    if not isinstance(positive, list) or not positive:
        return None

    def _norm(signals: list) -> list:
        out = []
        for s in signals:
            if not isinstance(s, dict):
                continue
            lbl = str(s.get("label", "")).strip()
            if not lbl:
                continue
            weight = str(s.get("weight_hint", "medium")).lower()
            if weight not in ("high", "medium", "low"):
                weight = "medium"
            out.append({
                "label": lbl,
                "description": str(s.get("description", "")).strip(),
                "weight_hint": weight,
            })
        return out

    # Fontes de informação coerentes com os flags gerados pela LLM.
    steps: list = []
    if data.get("requires_technical_report", True):
        steps.append("technical_site")
    if data.get("requires_business_data", True):
        steps.append("cnpj_receita")
    if not steps:
        steps.append("technical_site")
    steps.append("business_social")

    return {
        "service_label": label[:80],
        "requires_technical_report": bool(data.get("requires_technical_report", True)),
        "requires_business_data": bool(data.get("requires_business_data", True)),
        "enrichment_steps": list(dict.fromkeys(steps)),
        # Ciclos longos (engenharia/indústria) não mudam o calendário padrão
        # aqui — o template gerado assume o padrão 0/3/7/14; o dono ajusta na UI.
        "cadence_schedule": None,
        "positive_signals": _norm(positive),
        "negative_signals": _norm(negative),
        "context_signals": _norm(context),
        "extra_instructions": str(data.get("extra_instructions", "")).strip() or None,
    }


def _serialize(tmpl: CampaignScoringTemplate) -> Dict[str, Any]:
    return {
        "service_label": tmpl.service_label,
        "positive_signals": tmpl.positive_signals or [],
        "negative_signals": tmpl.negative_signals or [],
        "context_signals": tmpl.context_signals or [],
        "requires_technical_report": bool(tmpl.requires_technical_report),
        "requires_business_data": bool(tmpl.requires_business_data),
        "enrichment_steps": tmpl.enrichment_steps or None,
        "cadence_schedule": tmpl.cadence_schedule or None,
        "extra_instructions": tmpl.extra_instructions,
        "is_generated": bool(tmpl.is_generated),
    }


class TemplateGenerationService:
    """Gera e persiste um template de scoring sob demanda."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or settings.GROQ_API_KEY

    def _load_generic(self, db: Session) -> Optional[CampaignScoringTemplate]:
        return (
            db.query(CampaignScoringTemplate)
            .filter(
                sqlfunc.lower(CampaignScoringTemplate.service_label) == "genérico",
                CampaignScoringTemplate.is_active.is_(True),
            )
            .first()
        )

    def _find_existing(self, db: Session, label: str, organization_id: Optional[str]) -> Optional[CampaignScoringTemplate]:
        q = db.query(CampaignScoringTemplate).filter(
            sqlfunc.lower(CampaignScoringTemplate.service_label) == label.lower().strip(),
            CampaignScoringTemplate.is_active.is_(True),
        )
        if organization_id:
            q = q.filter(
                (CampaignScoringTemplate.organization_id == organization_id)
                | (CampaignScoringTemplate.organization_id.is_(None))
            )
        return q.order_by(CampaignScoringTemplate.created_at.asc()).first()

    async def generate(
        self,
        db: Session,
        target_service: str,
        target_segment: str = "",
        organization_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Gera, valida e persiste um template para a oferta.

        Retorna o template serializado (mesmo formato do router). Se falhar,
        cai no template 'Genérico' sem quebrar o pipeline.
        """
        generic = self._load_generic(db)

        from services.provider_client import quota_ok
        if not quota_ok(db, organization_id, "GROQ_API_KEY"):
            logger.warning("Cota de IA esgotada — caindo no template Genérico (org=%s).", organization_id)
            return _serialize(generic) if generic else {}

        generated = await self._call_llm(
            target_service, target_segment, db=db, organization_id=organization_id,
        )

        if generated is None:
            return _serialize(generic) if generic else {}

        # Reutiliza se já existir template gerado com o mesmo label (mesma org ou global).
        existing = self._find_existing(db, generated["service_label"], organization_id)
        if existing:
            return _serialize(existing)

        tmpl = CampaignScoringTemplate(
            service_label=generated["service_label"],
            positive_signals=generated["positive_signals"],
            negative_signals=generated["negative_signals"],
            context_signals=generated["context_signals"],
            requires_technical_report=generated["requires_technical_report"],
            requires_business_data=generated["requires_business_data"],
            enrichment_steps=generated.get("enrichment_steps"),
            cadence_schedule=generated.get("cadence_schedule"),
            extra_instructions=generated["extra_instructions"],
            is_generated=True,
            organization_id=organization_id,
            is_active=True,
        )
        db.add(tmpl)
        db.flush()
        logger.info("Template gerado sob demanda: %s (org=%s)", tmpl.service_label, organization_id)
        return _serialize(tmpl)

    async def _call_llm(
        self,
        target_service: str,
        target_segment: str,
        description: str = "",
        db=None,
        organization_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        from services.provider_client import groq_json_chat

        try:
            parsed = await groq_json_chat(
                api_key=self.api_key,
                model=GROQ_MODEL,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=build_prompt(target_service, target_segment, description),
                url=GROQ_URL,
                max_tokens=2000,
                temperature=0.3,
                db=db,
                organization_id=organization_id,
                reasoning_effort="none",
            )
        except Exception as e:
            logger.warning("Template generation LLM failed: %s", e)
            return None
        if parsed is None:
            return None
        return _validate(parsed)

    async def build_draft(
        self,
        db: Session,
        target_service: str,
        target_segment: str = "",
        description: str = "",
        organization_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Gera um rascunho de template validado SEM persistir.

        Usado pelo criador visual de vertentes (`POST /scoring-templates/
        generate`): o rascunho é persistido pela rota como `is_generated=True`
        e `is_active=False`, para o usuário revisar/refinar antes de ativar.
        Retorna `None` se a LLM falhar ou o JSON sair inválido.
        """
        generated = await self._call_llm(
            target_service, target_segment, description=description,
            db=db, organization_id=organization_id,
        )
        if generated is None:
            return None
        return generated
