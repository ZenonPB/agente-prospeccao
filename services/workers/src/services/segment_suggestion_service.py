"""SegmentSuggestionService — sugere um segmento/nicho para prospecção.

Usado no wizard de criação de campanha ("Me sugira segmentos"): quando o
usuário está sem ideias de qual nicho prospectar, pede à IA um segmento
aleatório contextualizado pelo perfil da prospecção selecionado:

- `web_presence`        → tecnologia/serviços digitais (sites, apps, ERPs...)
- `business_opportunity` → engenharia/serviços industriais/presenciais

Modelo: Groq Llama 3.3 70B Versatile (mesma escolha do outreach_service —
a resposta é texto client-facing, não classificação JSON; 8B é fraco para
criatividade controlada em pt-BR).

Resposta: JSON com segmento + rationale + exemplos de subnichos + gancho
de abordagem. Não leva dados do lead (não existe lead ainda) — só usa o
perfil e, opcionalmente, um segmento já informado para variar em torno.
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
GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = (
    "Você é um consultor de pré-vendas B2B focado em PMEs brasileiras. "
    "Sugere segmentos de mercado para prospecção de SAÍDA — ou seja, "
    "nichos que o usuário VAI prospectar para vender o serviço dele. "
    "As sugestões devem ser concretas, viáveis no Brasil, com densidade "
    "suficiente de empresas, e alinhadas ao perfil de prospecção informado. "
    "Varie entre chamadas — evite repetir sempre o mesmo segmento. "
    "Responda SOMENTE com JSON puro, sem markdown, sem bloco de código."
)

SCHEMA_HINT = """
Retorne um JSON com EXATAMENTE esta estrutura:
{
  "segment": "<nome curto do segmento em pt-BR, máx 40 chars. Ex.: 'Clínicas odontológicas'>",
  "rationale": "<2-3 frases em pt-BR explicando POR QUE este segmento faz sentido para o perfil informado — dor típica, potencial, fito com o serviço>",
  "subniches": ["<subnicho 1>", "<subnicho 2>", "<subnicho 3>"],
  "hook": "<1 frase com um gancho de abordagem típica para este segmento>",
  "cities_hint": ["<2-3 cidades brasileiras com densidade deste segmento>"]
}
"""


def build_prompt(
    profile: str,
    current_segment: str = "",
    exclude: Optional[List[str]] = None,
) -> str:
    """Monta o prompt do usuário.

    Args:
        profile: 'web_presence' ou 'business_opportunity'.
        current_segment: Segmento já informado (opcional) — usado como
            sinal para variar em torno, não repetir.
        exclude: Lista de segmentos já sugeridos nesta sessão para evitar
            repetição imediata.
    """
    profile_label = {
        "web_presence": "Serviços digitais (sites, apps, ERPs, landing pages, sistemas)",
        "business_opportunity": "Serviços industriais/presenciais (usinagem, manutenção, consultoria, projetos mecânicos)",
    }.get(profile, "Serviços B2B genéricos")

    lines: List[str] = []
    lines.append("== PERFIL DA PROSPECÇÃO ==")
    lines.append(f"Perfil: {profile}")
    lines.append(f"Descrição: {profile_label}")
    lines.append("")

    if current_segment:
        lines.append("== CONTEXTO ADICIONAL ==")
        lines.append(f"Segmento já informado pelo usuário: {current_segment}")
        lines.append("Sugira um segmento DIFERENTE deste, ou um subnicho não óbvio dele.")
        lines.append("")

    if exclude:
        lines.append("== SEGMENTOS JÁ SUGERIDOS NESSA SESSÃO (evite repetir) ==")
        for s in exclude[:8]:
            lines.append(f"  - {s}")
        lines.append("")

    lines.append("== INSTRUÇÕES ==")
    lines.append("1. Sugira UM segmento aleatório, alinhado ao perfil informado.")
    lines.append("2. Para 'web_presence' prefira nichos cuja presença digital seja dor real (ex.: clínicas, restaurantes, prestadores de serviço local).")
    lines.append("3. Para 'business_opportunity' prefira nichos industriais/presenciais (ex.: metalúrgicas, offshores, indústria alimentícia, fazendas).")
    lines.append("4. rationale deve justificar o fito com o serviço, não elogiar o segmento.")
    lines.append("5. cities_hint: cidades where este segmento tem densidade real no Brasil.")
    lines.append("6. Varie a sugestão a cada chamada — não retorne sempre 'Restaurantes'.")
    lines.append("")
    lines.append(SCHEMA_HINT)
    return "\n".join(lines)


def _parse_json(content: str) -> Optional[Dict[str, Any]]:
    text = (content or "").strip()
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
        logger.error("JSON inválido no segment_suggestion: %s", e)
        return None


def _normalize_response(parsed: Dict[str, Any]) -> Dict[str, Any]:
    subniches = parsed.get("subniches") or []
    if not isinstance(subniches, list):
        subniches = []
    cities = parsed.get("cities_hint") or []
    if not isinstance(cities, list):
        cities = []
    return {
        "segment": str(parsed.get("segment") or "")[:80],
        "rationale": str(parsed.get("rationale") or ""),
        "subniches": [str(s) for s in subniches][:5],
        "hook": str(parsed.get("hook") or ""),
        "cities_hint": [str(c) for c in cities][:5],
    }


FALLBACKS = {
    "web_presence": [
        {
            "segment": "Clínicas odontológicas",
            "rationale": "Clínicas dependem de captação local por site/Maps. Muitas têm site desatualizado sem agendamento online.",
            "subniches": ["Implantodontia", "Ortodontia", "Dentística"],
            "hook": "Sua clínica perde pacientes que não conseguem agendar online?",
            "cities_hint": ["São Paulo", "Belo Horizonte", "Curitiba"],
        },
        {
            "segment": "Restaurantes de bairro",
            "rationale": "Restaurantes locais têm site fraco ou inexistente, dependendo só de iFood. Cardápio online próprio é diferencial.",
            "subniches": ["Pizzarias", "Hamburguerias artesanais", "Restaurantes por quilo"],
            "hook": "Você está entregando 30% da margem ao delivery — que tal um site próprio?",
            "cities_hint": ["São Paulo", "Porto Alegre", "Florianópolis"],
        },
    ],
    "business_opportunity": [
        {
            "segment": "Metalúrgicas de precisão",
            "rationale": "Indústria com expansão e necessidade de projetos mecânicos sob encomenda. Porte médio, decisores técnicos.",
            "subniches": ["Usinagem CNC", "Caldeiraria", "Fundição"],
            "hook": "Posso ajudar a estruturar seus projetos mecânicos para aumento de capacidade.",
            "cities_hint": ["Joinville", "São Bernardo do Campo", "Caxias do Sul"],
        },
        {
            "segment": "Indústria alimentícia regional",
            "rationale": "Agroindústrias em expansão precisam de automação e layout de fábrica. Decisores são donos/engenheiros.",
            "subniches": "Laticínios, Doceria artesanal, Cafeterias torradoras".split(", "),
            "hook": "Produção cresceu mas o layout da fábrica não acompanhou?",
            "cities_hint": ["Londrina", "Caxias do Sul", "Viçosa"],
        },
    ],
}


class SegmentSuggestionService:
    """Sugere segmento/nicho de prospecção via Groq (llama-3.3-70b-versatile)."""

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

    async def suggest(
        self,
        profile: str = "web_presence",
        current_segment: str = "",
        exclude: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Sugere um segmento alinhado ao perfil.

        Args:
            profile: 'web_presence' ou 'business_opportunity'.
            current_segment: segmento já informado (para variar em torno).
            exclude: lista de segmentos já sugeridos para não repetir.

        Returns:
            Dict normalizado com segment, rationale, subniches, hook,
            cities_hint. Em caso de falha da LLM, retorna um fallback
            determinístico (offline-friendly).
        """
        prompt = build_prompt(profile, current_segment, exclude)
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.9,  # alta temperatura → mais variação entre chamadas
            "response_format": {"type": "json_object"},
        }
        try:
            async with self._create_client() as client:
                r = await client.post(GROQ_URL, json=payload)
        except httpx.RequestError as e:
            logger.error("Erro de rede Groq segment_suggestion: %s", e)
            return self._fallback(profile, exclude)

        if r.status_code != 200:
            logger.error("Groq segment_suggestion HTTP %s: %s", r.status_code, r.text[:300])
            return self._fallback(profile, exclude)

        try:
            data = r.json()
        except json.JSONDecodeError as e:
            logger.error("Resposta Groq não é JSON: %s", e)
            return self._fallback(profile, exclude)

        choices = data.get("choices") or []
        if not choices:
            return self._fallback(profile, exclude)

        content = choices[0].get("message", {}).get("content", "")
        parsed = _parse_json(content)
        if parsed is None:
            return self._fallback(profile, exclude)
        return _normalize_response(parsed)

    def _fallback(
        self,
        profile: str,
        exclude: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Retorna uma sugestão offline quando o Groq falha.

        Escolhe do pool de fallbacks do perfil, pulando os já sugeridos.
        """
        pool = FALLBACKS.get(profile, FALLBACKS["web_presence"])
        exclude_set = set(exclude or [])
        for item in pool:
            if item["segment"] not in exclude_set:
                return dict(item)
        # Se todos já foram sugeridos, recomeça o ciclo.
        return dict(pool[0])


async def _main_test():
    """Smoke test: sugere 3 segmentos variados para web_presence."""
    svc = SegmentSuggestionService()
    exclude: List[str] = []
    for i in range(3):
        out = await svc.suggest(profile="web_presence", exclude=exclude)
        print(f"--- Sugestão {i+1} ---")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        if out.get("segment"):
            exclude.append(out["segment"])


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main_test())
