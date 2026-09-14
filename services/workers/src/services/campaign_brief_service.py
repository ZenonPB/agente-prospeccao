"""Interpretação de brief comercial em linguagem natural.

O usuário descreve o que quer vender sem conhecer a arquitetura. O serviço
estrutura somente os campos necessários para a campanha; fontes, queries,
scoring e OfferProfile permanecem detalhes internos e são revisados depois pelo
pipeline determinístico.
"""
import json
import logging
import os
import sys
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.settings import settings  # noqa: E402

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = settings.GROQ_MODEL_GENERATION

SYSTEM_PROMPT = (
    "Você é um especialista brasileiro em pré-vendas B2B. Sua função é entender "
    "a intenção comercial do usuário sem trocar o serviço por outro e sem inventar "
    "dor, localização ou características do público. Diferencie ofertas parecidas: "
    "landing page é conversão/presença digital; sistema web sob medida exige dor "
    "operacional; projeto mecânico exige contexto industrial; troféus podem ser "
    "gerais, esportivos ou ligados ao Movimento Empresa Júnior (MEJ). "
    "Responda SOMENTE com JSON puro, sem markdown."
)

SCHEMA_HINT = """
Retorne EXATAMENTE:
{
  "name": "<nome curto e claro>",
  "target_service": "<serviço que será vendido, preservando a intenção>",
  "target_segment": "<público/segmento que deve ser encontrado>",
  "target_city": "<cidade ou vazio>",
  "target_state": "<UF ou vazio>",
  "analysis_profile": "web_presence|business_opportunity",
  "places_query": "<consulta simples para localizar o público; vazio se Places não fizer sentido>",
  "scoring_template_label": "<rótulo comercial curto para os critérios>",
  "rationale": "<explicação curta, em linguagem não técnica, de por que esse público faz sentido>"
}

Regras de interpretação:
- Landing pages/sites: analysis_profile='web_presence'. Preserve sinais de aquisição/conversão no serviço, mas NÃO afirme que uma empresa tem site ruim antes de pesquisá-la.
- Sistemas web/ERP/software sob medida: analysis_profile='web_presence', mas descreva o objetivo como resolver processos manuais, planilhas, retrabalho, integrações ou complexidade operacional quando ISSO estiver no brief. Não confunda com landing page.
- Engenharia mecânica, desenho técnico, NR-12, fabricação e serviços industriais: analysis_profile='business_opportunity'. Não invente uma necessidade técnica específica.
- Troféus/premiações/eventos: analysis_profile='business_opportunity'. Se o usuário mencionar campeonato/corrida/esporte, preserve isso em target_service/target_segment. Se mencionar MEJ, empresa júnior, núcleo, federação de EJs ou evento do Movimento Empresa Júnior, preserve explicitamente MEJ/empresas juniores.
- places_query é apenas apoio interno. Use a forma como alguém procuraria o público; para eventos/MEJ, pode ficar vazio se busca por evento for mais apropriada.
- Não invente cidade ou UF. target_state só pode ter 2 letras maiúsculas ou vazio.
- Não invente evidências, porte, faturamento, problema, data de evento, quantidade ou decisor.
- Rationale deve explicar a estratégia em termos comerciais, não mencionar modelo de IA, provider, template, OfferProfile ou query.
"""


def build_prompt(brief: str) -> str:
    return "\n".join([
        "== OBJETIVO COMERCIAL DO USUÁRIO ==",
        brief.strip(),
        "",
        "== TAREFA ==",
        "Estruture o objetivo sem aumentar a certeza do que ainda precisa ser descoberto.",
        "Preserve diferenças entre landing page, sistema sob medida, engenharia, troféus esportivos e troféus MEJ.",
        "Se uma informação não foi dada, deixe vazia em vez de inventar.",
        "",
        SCHEMA_HINT,
    ])


def _normalize_response(parsed: Dict[str, Any]) -> Dict[str, Any]:
    profile = str(parsed.get("analysis_profile") or "").strip().lower()
    if profile not in ("web_presence", "business_opportunity"):
        profile = "web_presence"
    state = str(parsed.get("target_state") or "").strip().upper()
    if len(state) != 2 or not state.isalpha():
        state = ""
    return {
        "name": str(parsed.get("name") or "").strip()[:255],
        "target_service": str(parsed.get("target_service") or "").strip()[:255],
        "target_segment": str(parsed.get("target_segment") or "").strip()[:100],
        "target_city": str(parsed.get("target_city") or "").strip()[:100],
        "target_state": state,
        "analysis_profile": profile,
        "places_query": str(parsed.get("places_query") or "").strip()[:255],
        "scoring_template_label": str(parsed.get("scoring_template_label") or "").strip()[:255],
        "rationale": str(parsed.get("rationale") or "").strip()[:1500],
    }


class CampaignBriefService:
    """Interpreta um brief em PT-BR e devolve campos estruturados de campanha."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY

    async def interpret(
        self,
        brief: str,
        db=None,
        organization_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not str(brief or "").strip():
            raise RuntimeError("Descreva o que você quer prospectar")

        from services.provider_client import groq_json_chat

        parsed = await groq_json_chat(
            api_key=self.api_key,
            model=GROQ_MODEL,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_prompt(brief),
            url=GROQ_URL,
            max_tokens=4000,
            temperature=0.2,
            timeout=60.0,
            db=db,
            organization_id=organization_id,
            reasoning_effort="none",
        )
        if parsed is None:
            logger.warning("Falha ao interpretar brief via IA (org=%s).", organization_id)
            raise RuntimeError("Não foi possível interpretar o objetivo agora. Tente novamente.")

        normalized = _normalize_response(parsed)
        if not normalized["target_segment"] and not normalized["target_service"]:
            raise RuntimeError("Não foi possível identificar o serviço ou o público da prospecção")
        if not normalized["name"]:
            service = normalized["target_service"] or "Prospecção"
            segment = normalized["target_segment"] or "novo público"
            normalized["name"] = f"{service} — {segment}"[:255]
        return normalized


async def _main_test():
    svc = CampaignBriefService()
    samples = [
        "quero vender landing pages para clínicas de psicologia em Araraquara",
        "sistemas web para empresas que dependem de planilhas",
        "projetos de engenharia mecânica para metalúrgicas em expansão",
        "troféus para campeonatos e corridas",
        "troféus para eventos do MEJ e empresas juniores",
    ]
    for brief in samples:
        print(f"--- Brief: {brief} ---")
        try:
            out = await svc.interpret(brief)
            print(json.dumps(out, ensure_ascii=False, indent=2))
        except RuntimeError as exc:
            print(f"ERRO: {exc}")


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main_test())
