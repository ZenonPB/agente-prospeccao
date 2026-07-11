"""OutreachService — gera sequência de mensagens de prospecção B2B.

 Modelo: Groq Llama 3.3 70B Versatile (qualidade de escrita superior ao
 8B usado em scoring — mensagens de outreach são texto client-facing, não
 classificação JSON).

Diferente do `scoring_service` (que pontua), aqui a IA PRODUZ conteúdo
comercial: subject + body de e-mail de abertura, mais 2 follow-ups (dias 3
e 7) e o encerramento (dia 14). Cadência completa conforme
`docs/business-rules.md`.

Entrada: lead (com score, evidências, decisor) + contexto da campanha.
Saída: dict com 4 mensagens prontas para revisão.

Princípios de produto (de `product-vision.md`):
- Nunca genéricas — sempre referenciam evidências/dor real do lead.
- Endereçado ao decisor pelo nome quando disponível.
- Opt-out em toda mensagem (rodapé) — LGPD.
- Não automatiza envio em LinkedIn (apenas EMAIL e WHATSAPP aqui).
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
    "Você é um ghost writer comercial B2B especializado em prospecção fria "
    "para PMEs brasileiras. Escreve e-mails curtos, diretos, com provas "
    "específicas — sem jargão corporativo vazio. Sempre referencia um fato "
    "real sobre o alvo, endereça a pessoa pelo nome e propõe uma conversa de "
    "15-20 minutos. Em português do Brasil, formal mas humano. "
    "Responda SOMENTE com JSON puro, sem markdown, sem bloco de código."
)

SCHEMA_HINT = """
Retorne um JSON com EXATAMENTE esta estrutura:
{
  "subject": "<assunto de e-mail. Máx 60 chars. Sem clickbait. Personalizado para o lead.>",
  "body_opening": "<corpo da mensagem de abertura, em texto plano com \\n. Máx 200 palavras. Cumprimenta o decisor pelo nome. Cita 1 evidência concreta. Propõe 1 conversa de 15-20 min. Inclui rodapé LGPD.>",
  "followup_1": "<reforço leve, máx 100 palavras. Outra perspectiva/ângulo. Dia 3 sem resposta.>",
  "followup_2": "<última tentativa, máx 100 palavras. Valor direto ou caso similar. Dia 7 sem resposta.>",
  "closing": "<encerramento respeitoso, máx 60 palavras. Dia 14 sem resposta.>",
  "whatsapp_short": "<versão curta para WhatsApp Business, 2-3 frases, tom mais informal. Pode conter emoji.>",
  "rationale": "<1-2 frases em pt-BR explicando as escolhes: qual gancho principal, por que este ângulo.>"
}
"""


def _extract_facts_for_prompt(lead: Dict[str, Any]) -> List[str]:
    """Reúne fatos reais do lead — extraídos do JSONB de evidências e do
    enriquecimento, mais dados cadastrais. A LLM só pode referenciar fatos
    desta lista (não inventar)."""
    facts: List[str] = []
    if lead.get("company_name"):
        facts.append(f"Empresa: {lead['company_name']}")
    if lead.get("category"):
        facts.append(f"Categoria (Google Places): {lead['category']}")
    if lead.get("city"):
        facts.append(f"Localização: {lead['city']}, {lead.get('state') or ''}")
    if lead.get("website"):
        facts.append(f"Site: {lead['website']}")

    for ev in (lead.get("evidence") or [])[:8]:
        title = ev.get("title") or ""
        desc = ev.get("description") or ""
        if title or desc:
            facts.append(f"Evidência: {title} — {desc}")

    if lead.get("primary_need"):
        facts.append(f"Necessidade provável: {lead['primary_need']}")
    if lead.get("pitch_angle"):
        facts.append(f"Gancho já sugerido pelo scoring: {lead['pitch_angle']}")
    if lead.get("qualification_reason"):
        facts.append(f"Justificativa do scoring: {lead['qualification_reason']}")

    cr = lead.get("company_record") or {}
    if cr:
        if cr.get("porte_label"):
            facts.append(f"Porte (Receita): {cr['porte_label']}")
        if cr.get("cnae_principal_label"):
            facts.append(f"CNAE principal: {cr['cnae_principal_label']}")
        if cr.get("idade_anos") is not None:
            facts.append(f"Idade do negócio: {cr['idade_anos']} anos")

    prim = (lead.get("contacts") or [None])[0] if lead.get("contacts") else None
    if prim:
        facts.append(f"Decisor: {prim.get('name')} ({prim.get('role_label') or ''})")
        if prim.get("email"):
            facts.append(f"Email do decisor: {prim['email']}")
    elif lead.get("email"):
        facts.append(f"Email genérico: {lead['email']}")

    return facts


def build_prompt(
    lead: Dict[str, Any],
    context_service: str = "",
    context_segment: str = "",
) -> str:
    lines: List[str] = []

    lines.append("== CONTEXTO DA EMPRESA QUE PROSPECTA ==")
    lines.append(f"Serviço que vendemos: {context_service or '(não informado)'}")
    lines.append(f"Segmento prospectado: {context_segment or '(não informado)'}")
    lines.append("")

    lines.append("== FATOS REAIS SOBRE O LEAD (use SOMENTE estes; não invente) ==")
    for f in _extract_facts_for_prompt(lead):
        lines.append(f"  - {f}")
    lines.append("")

    lines.append("== INSTRUÇÕES ==")
    lines.append("1. Enderece o decisor pelo primeiro nome quando houver. Se não houver, use 'Olá' na abertura.")
    lines.append("2. A primeira frase precisa de um gancho baseado em evidência concreta, não elogio genérico.")
    lines.append("3. Body de abertura: máximo 200 palavras, parágrafos curtos.")
    lines.append("4. Cada mensagem tem rodapé LGPD: 'Responda STOP para ser removido. E-mail B2B conforme LGPD.'")
    lines.append("5. Não prometa resultado mágico ('vai dobrar suas vendas').")
    lines.append("6. Não invente números, cargos ou produtos que não estejam nos fatos acima.")
    lines.append("7. Tom: aconselhador, não vendedor agressivo.")
    lines.append("")
    lines.append(SCHEMA_HINT)
    return "\n".join(lines)


def _normalize_response(parsed: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "subject": str(parsed.get("subject") or "")[:120],
        "body_opening": str(parsed.get("body_opening") or ""),
        "followup_1": str(parsed.get("followup_1") or ""),
        "followup_2": str(parsed.get("followup_2") or ""),
        "closing": str(parsed.get("closing") or ""),
        "whatsapp_short": str(parsed.get("whatsapp_short") or ""),
        "rationale": str(parsed.get("rationale") or ""),
    }
    # Garante rodapé LGPD se a LLM esqueceu.
    if "STOP" not in out["body_opening"]:
        out["body_opening"] = (
            out["body_opening"].rstrip()
            + "\n\n—\nResponda STOP para ser removido. E-mail B2P conforme LGPD."
        )
    return out


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
        logger.error("JSON inválido no outreach: %s", e)
        return None


class OutreachService:
    """Gera sequência de cadência de outreach usando Llama 3.3 70B."""

    def __init__(self):
        self.api_key = settings.GROQ_API_KEY

    def _create_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=90.0,  # 70B é mais lento que o 8B.
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    async def generate_sequence(
        self,
        lead: Dict[str, Any],
        context_service: str = "",
        context_segment: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Gera subject + 4 mensagens + variação WhatsApp + rationale.

        Args:
            lead: dict com company_name, category, city, state, website,
              evidence[], primary_need, pitch_angle, qualification_reason,
              company_record (dict), contacts[] (com primary em [0]), email.
            context_service / context_segment: contexto da campanha.

        Returns:
            Dict normalizado ou None em caso de falha.
        """
        prompt = build_prompt(lead, context_service, context_segment)
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
        }
        try:
            async with self._create_client() as client:
                r = await client.post(GROQ_URL, json=payload)
        except httpx.RequestError as e:
            logger.error("Erro de rede Groq outreach: %s", e)
            return None

        if r.status_code != 200:
            logger.error("Groq outreach HTTP %s: %s", r.status_code, r.text[:300])
            return None

        try:
            data = r.json()
        except json.JSONDecodeError as e:
            logger.error("Resposta Groq não é JSON: %s", e)
            return None
        choices = data.get("choices") or []
        if not choices:
            return None
        content = choices[0].get("message", {}).get("content", "")
        parsed = _parse_json(content)
        if parsed is None:
            return None
        return _normalize_response(parsed)


async def _main_test():
    """Smoke test: gera mensagem para um lead fictício."""
    svc = OutreachService()
    lead = {
        "company_name": "Habitus Academia Baldan",
        "category": "Academia",
        "city": "Matão",
        "state": "SP",
        "website": "https://habitusbaldan.com.br",
        "primary_need": "Captar mais alunos via site",
        "pitch_angle": "Site sem CTA de matrícula impede captação digital de alunos",
        "qualification_reason": "Academia bem avaliada no Maps mas site sem fluxo de conversão.",
        "evidence": [
            {"title": "Sem CTA de matrícula", "description": "Homepage sem botão 'Matricule-se' nem formulário curto."},
            {"title": "WordPress 5.4", "description": "Versão desatualizada detectada."},
        ],
        "company_record": {
            "porte_label": "ME",
            "cnae_principal_label": "Atividades de condicionamento físico",
            "idade_anos": 8,
        },
        "contacts": [
            {"name": "João Baldan", "role_label": "Sócio-Proprietário", "email": "joao@habitusbaldan.com.br"}
        ],
    }
    out = await svc.generate_sequence(lead, "Marketing Digital para Academias", "academias")
    if out:
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main_test())
