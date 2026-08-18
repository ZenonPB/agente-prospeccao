"""CampaignBriefService — interpreta um brief em linguagem natural e devolve
os campos estruturados para criar uma campanha de prospecção.

O usuário descreve o que quer prospectar em PT-BR ("quero vender
landing pages para clínicas de psicologia em Araraquara") e a IA devolve o
campo a campo:

- `name`, `target_service`, `target_segment`, `target_city`, `target_state`
- `analysis_profile` (web_presence | business_opportunity)
- `places_query` (query otimizada para o Google Places)
- `scoring_template_label` (label do template de critérios a usar/gerar)
- `rationale` (explicação das escolhas)

Este serviço NÃO cria campanha — o endpoint `POST /api/campaigns/from-brief`
retorna a sugestão para o usuário revisar/editar antes de confirmar
(critério de aceite 1.4: "Usuário edita campos antes de confirmar").

Modelo: Groq de geração configurado em `settings.GROQ_MODEL_GENERATION`
(estruturação de brief exige modelo de texto).
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
    "Você é um consultor de pré-vendas B2B brasileiro. O usuário vai descrever, "
    "em linguagem natural, o serviço que ele quer vender e para qual público. "
    "Sua tarefa é estruturar essa intenção nos campos de uma campanha de "
    "prospecção. Responda SOMENTE com JSON puro, sem markdown, sem bloco de código."
)

SCHEMA_HINT = """
Retorne um JSON com EXATAMENTE esta estrutura:
{
  "name": "<nome curto da campanha, ex.: 'Landing pages - Clínicas de psicologia - Araraquara'>",
  "target_service": "<o serviço que será vendido, ex.: 'Landing pages para captação de pacientes'>",
  "target_segment": "<o segmento/público-alvo curto, ex.: 'Clínicas de psicologia'>",
  "target_city": "<cidade-alvo ou vazio se não mencionada>",
  "target_state": "<UF de 2 letras ou vazio>",
  "analysis_profile": "web_presence",
  "places_query": "<query otimizada para Google Places que encontra empresas do segmento, ex.: 'clinica de psicologia em Araraquara'>",
  "scoring_template_label": "<label do template de critérios existente mais próximo, ou uma label nova descritiva do segmento>",
  "rationale": "<2-3 frases explicando as escolhas e o fito do serviço com o segmento>"
}
Regras:
- analysis_profile: use 'web_presence' quando o serviço depender de site/presença digital (sites, apps, landing pages, marketing). Use 'business_opportunity' para serviços industriais/presenciais (engenharia, usinagem, manutenção, consultoria, projetos mecânicos).
- places_query deve ser a forma que um cliente pesquisaria no Google Maps para encontrar o segmento na cidade informada (ou sem cidade se não informada).
- target_state: apenas UF com 2 letras maiúsculas, ou string vazia.
- Não invente cidade/UF que não estejam no brief. Se o brief não mencionar localização, deixe vazio.
"""


def build_prompt(brief: str) -> str:
    lines = [
        "== BRIEF DO USUÁRIO ==",
        brief.strip(),
        "",
        "== INSTRUÇÕES ==",
        "1. Estruture o brief nos campos do schema abaixo.",
        "2. Preserve exatamente o serviço que o usuário quer vender — não troque por outro.",
        "3. Se a localização não for mencionada, deixe cidade/UF vazios.",
        "4. Não invente informações que não estejam no brief.",
        "",
        SCHEMA_HINT,
    ]
    return "\n".join(lines)


def _normalize_response(parsed: Dict[str, Any]) -> Dict[str, Any]:
    profile = str(parsed.get("analysis_profile") or "").strip().lower()
    if profile not in ("web_presence", "business_opportunity"):
        profile = "web_presence"
    state = str(parsed.get("target_state") or "").strip().upper()
    if len(state) > 2:
        state = state[:2]
    return {
        "name": str(parsed.get("name") or "")[:255],
        "target_service": str(parsed.get("target_service") or "")[:255],
        "target_segment": str(parsed.get("target_segment") or "")[:100],
        "target_city": str(parsed.get("target_city") or "")[:100],
        "target_state": state,
        "analysis_profile": profile,
        "places_query": str(parsed.get("places_query") or "")[:255],
        "scoring_template_label": str(parsed.get("scoring_template_label") or "")[:255],
        "rationale": str(parsed.get("rationale") or ""),
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
        """Interpreta o brief e devolve os campos normalizados.

        Em caso de falha da LLM (rede/HTTP/JSON inválido/cota), levanta
        RuntimeError para que o endpoint retorne 502 — melhor do que
        devolver uma campanha inventada que o usuário teria que corrigir
        do zero. O brief é curto e a extração é estruturada (JSON), então
        um fallback determinístico genérico seria pior que o erro claro.

        A chamada passa por `provider_client.groq_json_chat` (pacing global +
        retry em 429/5xx + gate/consumo de cota quando `db`/`organization_id`
        chegam).
        """
        from services.provider_client import groq_json_chat

        prompt = build_prompt(brief)
        parsed = await groq_json_chat(
            api_key=self.api_key,
            model=GROQ_MODEL,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            url=GROQ_URL,
            max_tokens=4000,
            temperature=0.3,
            timeout=60.0,
            db=db,
            organization_id=organization_id,
        )
        if parsed is None:
            logger.warning("Falha ao interpretar brief via IA (org=%s).", organization_id)
            raise RuntimeError("Falha ao interpretar o brief via IA")

        normalized = _normalize_response(parsed)
        if not normalized["target_segment"] and not normalized["target_service"]:
            raise RuntimeError("Não foi possível extrair o alvo da prospecção do brief")
        return normalized


async def _main_test():
    """Smoke test: interpreta dois briefs e imprime o resultado."""
    svc = CampaignBriefService()
    samples = [
        "quero vender landing pages para clínicas de psicologia em Araraquara",
        "projetos de engenharia mecânica para metalúrgicas em São Paulo",
    ]
    for brief in samples:
        print(f"--- Brief: {brief} ---")
        try:
            out = await svc.interpret(brief)
            print(json.dumps(out, ensure_ascii=False, indent=2))
        except RuntimeError as e:
            print(f"ERRO: {e}")


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main_test())
