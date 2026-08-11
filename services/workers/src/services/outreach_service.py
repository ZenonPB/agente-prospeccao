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
- Opt-out em toda mensagem (rodapé com STOP).
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
    "Você é um copywriter comercial sênior brasileiro, especializado em cold "
    "email B2B para PMEs. Você escreve como um consultor que entende o negócio "
    "do lead — não como um vendedor. O lead precisa sentir que você analisou "
    "a empresa dele antes de escrever.\n\n"
    "ABERTURA (a primeira frase decide se o email é lido):\n"
    "- A primeira frase NUNCA é um cumprimento (\"Espero que esteja bem\") "
    "nem elogio genérico (\"Parabéns pela empresa\") nem \"notei que\" / "
    "\"percebi que\" / \"observamos que\" / \"nós analisamos seu site e\". "
    "Comece DIRETO com a observação factual como uma declaração: \"O site da "
    "Habitus não tem um botão de matrícula na homepage.\" A saudação (\"João,\") "
    "vai em linha separada antes, faz parte do ritual, não se mistura com a "
    "observação.\n"
    "- A observação precisa ser tão específica que o leitor pense \"esse cara "
    "realmente entrou no meu site\".\n\n"
    "TOM E IDIOMA:\n"
    "- Português brasileiro, formal mas humano. Trata o decisor como par "
    "(você, nunca \"o senhor\").\n"
    "- ZERO jargão corporativo/de marketing: nunca \"soluções\", \"sinergia\", "
    "\"jornada\", \"ecossistema\", \"imperdível\", \"inovador\".\n"
    "- ZERO frases com cara de IA: nunca \"Neste cenário\", \"No mundo atual\", "
    "\"Em tempos de\", \"Diante disso\", \"É importante ressaltar\", "
    "\"Vale destacar\", \"Sabemos que\", \"No decorrer\", \"Cabe destacar\", "
    "\"Diante do exposto\".\n"
    "- ZERO abertura narrando o processo de vocês: nunca \"Ao analisar\", "
    "\"Após verificar\", \"Navegando pelo seu site\". A observação abre como "
    "afirmação, sem motivo narrado.\n"
    "- Sem reticências poéticas, sem \"!\" exclamando, sem emojis no email. "
    "WhatsApp pode ter 1 emoji.\n\n"
    "CONTEÚDO E PROVA:\n"
    "- Demonstra diagnóstico, não pitch. Descreve o problema em termos do "
    "impacto no negócio do lead (alunos perdidos, orçamento desperdiçado, "
    "oportunidades deixadas na mesa) com concretude visual.\n"
    "- Cita UM fato específico do lead por mensagem, só do contexto fornecido. "
    "JAMAIS invente números, datas, percentuais ou nomes de empresas reais. "
    "Cases no follow-up 2 são genéricos (\"uma academia de porte similar\", "
    "sem nome inventado).\n"
    "- Não promete resultado mágico (\"vai dobrar suas vendas\", "
    "\"garantido\"). Fala em hipóteses com boas-vindas honestas.\n\n"
    "CTA:\n"
    "- Um único CTA por mensagem, específico e de baixo atrito. Nunca "
    "\"vamos marcar uma call para apresentar nossas soluções\". Propõe algo "
    "concreto: \"15 minutos para discutir o CTA de matrícula — terça às 10h "
    "ou quarta às 14h?\" Oferece 1-2 horários, não pergunta \"quando você "
    "pode\".\n\n"
    "ESTRUTURA E TAMANHOS:\n"
    "- Subject curto, máx 55 chars, sem prefixo (\"Proposta:\", \"Convite:\"), "
    "sem clickbait. Observação factual que desperta curiosidade sobre o "
    "negócio dele.\n"
    "- Body de abertura: 200-280 palavras, 4 parágrafos curtos: (1) saudação "
    "isolada + observação factual direta; (2) o impacto no negócio dele em "
    "termos dele; (3) o que pode ser feito, sem prometer o mundo; (4) CTA "
    "com horário proposto.\n"
    "- Followup 1: 120-160 palavras, NOVO ÂNGULO — não repete a abertura. "
    "Pode ser pergunta provocativa, dado do contexto, ou consequência não "
    "óbvia.\n"
    "- Followup 2: 140-180 palavras, VALOR DIRETO — insight curto + caso "
    "genérico do mesmo segmento.\n"
    "- Closing: 70-100 palavras, breve, respeitoso, sem culpar o decisor, "
    "oferece reaproche em 90 dias.\n"
    "- Varie a estrutura entre follow-ups — nunca use o mesmo template da "
    "primeira.\n"
    "- WhatsApp: 2-3 frases, informal, até 1 emoji. Sem rodapé de opt-out aqui.\n"
    "- rationale: 2-3 frases em pt-BR explicando o gancho principal e o "
    "porquê deste ângulo.\n\n"
    "Opt-out:\n"
    "- Em toda mensagem de EMAIL (body_opening, followup_1, followup_2, "
    "closing), adicionar ao final em linhas separadas:\n"
    "-\n"
    "Responda STOP para não receber mais mensagens.\n\n"
    "As contagens mínimas são obrigatórias. Não produza uma mensagem de "
    "body com menos de 200 palavras nem follow-up com menos de 120 palavras. "
    "Se estiver curto, acrescente concretude.\n\n"
    "Responda SOMENTE com JSON puro, sem markdown, sem bloco de código."
)

SCHEMA_HINT = """
Retorne um JSON com EXATAMENTE esta estrutura:
{
  "subject": "<assunto do email, sem prefixo, sem clickbait, máx 55 chars, observação factual que desperta curiosidade>",
  "body_opening": "<corpo da mensagem de abertura, 200-280 palavras, texto plano com \\n entre parágrafos, com rodapé de opt-out em linhas finais>",
  "followup_1": "<reforço com NOVO ângulo, 120-160 palavras, com rodapé de opt-out>",
  "followup_2": "<valor direto + insight + breve caso do segmento (sem nome inventado), 140-180 palavras, com rodapé de opt-out>",
  "closing": "<encerramento respeitoso, 70-100 palavras, com rodapé de opt-out>",
  "whatsapp_short": "<versão curta WhatsApp Business, 2-3 frases, até 1 emoji, sem rodapé de opt-out>",
  "rationale": "<2-3 frases em pt-BR explicando o gancho principal e o porquê deste ângulo>"
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
        if prim.get("linkedin_url"):
            facts.append(
                f"Perfil LinkedIn do decisor: {prim['linkedin_url']} "
                "(canal alternativo de contato para o consultor usar, se preferir)"
            )
    elif lead.get("email"):
        facts.append(f"Email genérico: {lead['email']}")

    return facts


def build_prompt(
    lead: Dict[str, Any],
    context_service: str = "",
    context_segment: str = "",
    playbook: Optional[Dict[str, Any]] = None,
) -> str:
    lines: List[str] = []

    lines.append("== CONTEXTO DA EMPRESA QUE PROSPECTA ==")
    lines.append(f"Serviço que vendemos: {context_service or '(não informado)'}")
    lines.append(f"Segmento prospectado: {context_segment or '(não informado)'}")
    lines.append("")

    if playbook:
        lines.append("== PLAYBOOK DA VERTICAL (hooks, assuntos e objeções reais) ==")
        hooks = playbook.get("hooks") or []
        if hooks:
            lines.append("Hooks de abordagem que funcionam nesta vertical:")
            for h in hooks:
                lines.append(f"  - {h}")
        subjects = playbook.get("subject_ideas") or []
        if subjects:
            lines.append("Ideias de assunto (subject) com bom resultado nesta vertical:")
            for s in subjects:
                lines.append(f"  - {s}")
        objections = playbook.get("objections") or []
        if objections:
            lines.append("Objeções comuns do decisor e como endereçá-las (só para follow-ups/argumentação):")
            for o in objections:
                if isinstance(o, dict):
                    lines.append(f"  - Objeção: {o.get('objection', '')} → abordagem: {o.get('approach', '')}")
                else:
                    lines.append(f"  - {o}")
        lines.append("Use estes hooks/objeções como referência REAL da vertical — cite-os com naturalidade, nunca como lista.")
        lines.append("")

    lines.append("== FATOS REAIS SOBRE O LEAD (use SOMENTE estes; não invente) ==")
    for f in _extract_facts_for_prompt(lead):
        lines.append(f"  - {f}")
    lines.append("")

    lines.append("== INSTRUÇÕES ==")
    lines.append("1. Enderece o decisor pelo primeiro nome em LINHA SEPARADA antes da primeira observação (ex.: \"João,\\n<observação>\"). Se não houver nome, use \"Olá,\" em linha separada.")
    lines.append("2. A primeira frase NÃO pode ser cumprimento, elogio genérico, nem narrar o seu processo (\"notei que\", \"ao analisar\", \"observamos que\"). Comece DIRETO com a observação factual como uma declaração de quem estudou o site dele.")
    lines.append("3. A observação precisa ser tão específica que o leitor pense \"esse cara realmente entrou no meu site\".")
    lines.append("4. Demonstra diagnóstico, não pitch. Descreve o impacto no negócio dele em termos dele (alunos perdidos, orçamento desperdiçado, oportunidades deixadas na mesa) — concretude visual, não clichê.")
    lines.append("5. Cita UM fato específico do lead por mensagem, só dos fatos acima. JAMAIS invente números, datas, percentuais ou nomes de empresas reais. Casos no follow-up 2 são genéricos (\"uma academia de porte similar\").")
    lines.append("6. Um único CTA por mensagem, específico e de baixo atrito. Nunca \"vamos marcar uma call para apresentar nossas soluções\". Propõe algo concreto: \"15 minutos para discutir <tópico> — terça às 10h ou quarta às 14h?\"")
    lines.append("7. Body de abertura: 200-280 palavras, 4 parágrafos curtos. Followup 1: 120-160 palavras (novo ângulo). Followup 2: 140-180 palavras (insight + caso genérico). Closing: 70-100 palavras. WhatsApp: 2-3 frases, até 1 emoji, sem rodapé de opt-out.")
    lines.append("8. Contagens mínimas são OBRIGATÓRIAS. Se estiver curto, acrescente concretude, não repita.")
    lines.append("9. Sem jargão (\"soluções\", \"sinergia\", \"jornada\") e sem frases com cara de IA (\"Neste cenário\", \"Diante disso\", \"Vale destacar\").")
    lines.append("10. Rodapé de opt-out em toda mensagem de email (body_opening, followup_1, followup_2, closing), em linhas finais separadas: \"-\\nResponda STOP para não receber mais mensagens.\"")
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
    # Garante rodapé de opt-out se a LLM esqueceu.
    if "STOP" not in out["body_opening"]:
        out["body_opening"] = (
            out["body_opening"].rstrip()
            + "\n-\nResponda STOP para não receber mais mensagens."
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

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY

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
        playbook: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Gera subject + 4 mensagens + variação WhatsApp + rationale.

        Args:
            lead: dict com company_name, category, city, state, website,
              evidence[], primary_need, pitch_angle, qualification_reason,
              company_record (dict), contacts[] (com primary em [0]), email.
            context_service / context_segment: contexto da campanha.
            playbook: dict opcional com hooks/subject_ideas/objections por
              vertical (item 3.8) — injetado no prompt para mensagens
              variarem conforme o serviço/segmento.

        Returns:
            Dict normalizado ou None em caso de falha.
        """
        prompt = build_prompt(lead, context_service, context_segment, playbook)
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 3200,
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
