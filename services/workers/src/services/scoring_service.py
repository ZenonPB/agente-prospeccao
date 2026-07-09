import os
import sys
import json
import logging
from typing import Dict, Any, Optional

import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.settings import settings

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = (
    "Você é um especialista em auditoria técnica de sites de empresas. "
    "Recebe um relatório técnico passivo de um website e devolve uma qualificação "
    "para prospecção B2B. Responda SOMENTE com JSON puro, sem markdown, sem "
    "bloco de código. Nenhum texto antes ou depois do JSON."
)

USER_PROMPT_TEMPLATE = (
    "Analise o relatório técnico abaixo e gere a qualificação do lead.\n\n"
    "{context_block}"
    "Regras de scoring (0-100):\n"
    "- 80-100: crítico (.env exposto, .git exposto, sem HTTPS)\n"
    "- 60-79: múltiplos problemas de segurança ou performance\n"
    "- 40-59: headers ausentes, WordPress detectado, ausência de LGPD\n"
    "- 20-39: site funcional com melhorias possíveis\n"
    "- 0-19: site bem configurado, baixa oportunidade\n\n"
    "Retorne um JSON com exatamente esta estrutura:\n"
    "{{\n"
    '  "qualification_score": <inteiro 0-100>,\n'
    '  "primary_need": "SECURITY_FIX" | "PERFORMANCE" | "MODERN_WEBSITE" | "SEO" | "LGPD" | "NONE",\n'
    '  "qualification_reason": "<2-4 frases em pt-BR como argumento de venda, citando problemas reais e conectando ao serviço que queremos vender>",\n'
    '  "pitch_angle": "<1-2 frases: qual é o gancho principal para abordar este lead, baseado nos problemas encontrados e no serviço que queremos vender>",\n'
    '  "suggested_subject": "<sugestão de assunto para o e-mail de prospecção, personalizado para esta empresa e segmento>",\n'
    '  "issues_found": [\n'
    "    {{\n"
    '  "severity": "CRITICO" | "ALTO" | "MEDIO" | "BAIXO",\n'
    '  "title": "<título curto>",\n'
    '  "description": "<descrição em pt-BR>",\n'
    '  "recommendation": "<recomendação em pt-BR>"\n'
    "    }}\n"
    "  ]\n"
    "}}\n\n"
    "Relatório técnico:\n"
    "{report}"
)

BUSINESS_PROMPT_TEMPLATE = (
    "Você é um analista de prospecção B2B. Avalie uma empresa brasileira "
    "com base nos dados disponíveis e determine se ela é um bom alvo comercial "
    "para uma empresa que vende serviços de tecnologia e consultoria.\n\n"
    "{context_block}"
    "Dados disponíveis:\n"
    "{lead_data}\n\n"
    "Regras de scoring (0-100):\n"
    "- 80-100: empresa ativa, porte médio/grande, com contato disponível, setor promissor\n"
    "- 60-79: empresa ativa, setor relevante, sem contato direto\n"
    "- 40-59: empresa pequena ou dados insuficientes\n"
    "- 20-39: setor de baixo potencial ou dados muito escassos\n"
    "- 0-19: empresa parece inativa ou irrelevante\n\n"
    "Retorne um JSON com exatamente esta estrutura:\n"
    "{{\n"
    '  "qualification_score": <inteiro 0-100>,\n'
    '  "primary_need": "SECURITY_FIX" | "PERFORMANCE" | "MODERN_WEBSITE" | "SEO" | "LGPD" | "NONE",\n'
    '  "qualification_reason": "<2-4 frases em pt-BR como argumento de venda, não análise genérica — mencione o potencial e como nosso serviço resolve>",\n'
    '  "pitch_angle": "<1-2 frases com o gancho principal de abordagem>",\n'
    '  "suggested_subject": "<sugestão de assunto para e-mail de prospecção>",\n'
    '  "issues_found": [\n'
    "    {{\n"
    '  "severity": "CRITICO" | "ALTO" | "MEDIO" | "BAIXO",\n'
    '  "title": "<aspecto avaliado>",\n'
    '  "description": "<descrição em pt-BR>",\n'
    '  "recommendation": "<recomendação em pt-BR>"\n'
    "    }}\n"
    "  ]\n"
    "}}\n\n"
    "Avaliação baseada apenas nos dados fornecidos — sem visitar o site da empresa."
)


def _build_context_block(target_service: str, target_segment: str) -> str:
    """Monta o bloco de contexto da campanha para o prompt da LLM, ou vazio se faltarem ambos."""
    if not target_service and not target_segment:
        return ""
    lines = ["Contexto da prospecção:"]
    if target_service:
        lines.append(f"- Serviço que queremos vender: {target_service}")
    if target_segment:
        lines.append(f"- Segmento-alvo: {target_segment}")
    lines.append("")
    lines.append("Use este contexto para:")
    lines.append("1. Avaliar se os problemas encontrados são relevantes para este segmento")
    lines.append("2. Gerar o qualification_reason como um argumento de venda direto,")
    lines.append("   mencionando o problema específico E como nosso serviço resolve")
    lines.append("3. Sugerir o ângulo de abordagem mais efetivo")
    lines.append("")
    return "\n".join(lines)


class AIScoringService:
    """Serviço de scoring de leads via Groq (llama-3.1-8b-instant)."""

    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
    
    def _create_client(self) -> httpx.AsyncClient:
        """Cria um novo AsyncClient para cada operação."""
        return httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    def _build_payload(
        self,
        technical_report: Dict[str, Any],
        target_service: str = "",
        target_segment: str = "",
    ) -> Dict[str, Any]:
        """Monta o payload para a API de chat completions do Groq."""
        report_str = json.dumps(technical_report, ensure_ascii=False, indent=2)
        context_block = _build_context_block(target_service, target_segment)
        user_prompt = USER_PROMPT_TEMPLATE.format(
            report=report_str, context_block=context_block
        )
        return {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

    def _parse_response(self, content: str) -> Optional[Dict[str, Any]]:
        """Extrai o JSON devolvido pelo modelo, tolerando cercas de markdown.

        Args:
            content: Texto bruto retornado pelo Groq.

        Returns:
            Dicionário parseado, ou None se o conteúdo não for JSON válido.
        """
        if not content:
            logger.warning("Resposta vazia do Groq.")
            return None

        text = content.strip()
        # Tolerar cercas de markdown apesar da instrução no prompt.
        if text.startswith("```"):
            # remove primeira linha (```json ou ```)
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("Falha ao decodificar JSON do Groq: %s", e)
            return None

    def _build_business_payload(
        self,
        company_name: str,
        category: str,
        city: str,
        state: str,
        website: str | None,
        target_service: str = "",
        target_segment: str = "",
    ) -> Dict[str, Any]:
        """Monta payload para scoring de oportunidade de negócio."""
        lead_data = (
            f"Empresa: {company_name}\n"
            f"Categoria: {category}\n"
            f"Localização: {city}, {state}\n"
            f"Website: {website or 'Não informado'}"
        )
        context_block = _build_context_block(target_service, target_segment)
        user_prompt = BUSINESS_PROMPT_TEMPLATE.format(
            lead_data=lead_data, context_block=context_block
        )
        return {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": (
                    "Você é um analista de prospecção B2B. "
                    "Responda SOMENTE com JSON puro, sem markdown, sem "
                    "bloco de código. Nenhum texto antes ou depois do JSON."
                )},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

    async def score_business_lead(
        self,
        company_name: str,
        category: str = "",
        city: str = "",
        state: str = "",
        website: str | None = None,
        target_service: str = "",
        target_segment: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Avalia o potencial de negócio de um lead sem análise técnica de site.

        Usa dados cadastrais da empresa para determinar se é um bom alvo
        comercial. Ideal para campanhas com perfil business_opportunity
        (ex: usinagem, manutenção industrial, consultoria).

        Args:
            company_name: Nome da empresa
            category: Categoria/segmento da empresa
            city: Cidade
            state: Estado
            website: URL do site (pode ser None)
            target_service: Serviço que a campanha quer vender (opcional).
            target_segment: Segmento-alvo da campanha (opcional).

        Returns:
            Dicionário com qualification_score (int 0-100), primary_need (str),
            qualification_reason (str), pitch_angle (str), suggested_subject (str)
            e issues_found (lista); ou None em caso de falha.
        """
        payload = self._build_business_payload(
            company_name, category, city, state, website,
            target_service, target_segment,
        )

        try:
            async with self._create_client() as client:
                response = await client.post(GROQ_URL, json=payload)
        except httpx.RequestError as e:
            logger.error("Erro de rede ao chamar Groq (business): %s", e)
            return None

        if response.status_code != 200:
            logger.error("Groq respondeu HTTP %s (business): %s", response.status_code, response.text[:500])
            return None

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            logger.error("Resposta do Groq não é JSON (business): %s", e)
            return None

        choices = data.get("choices") or []
        if not choices:
            logger.error("Resposta do Groq sem choices (business): %s", data)
            return None

        content = choices[0].get("message", {}).get("content", "")
        parsed = self._parse_response(content)
        if parsed is None:
            return None

        try:
            score = int(parsed.get("qualification_score", 0))
        except (TypeError, ValueError):
            logger.warning("qualification_score inválido (%r); usando 0.", parsed.get("qualification_score"))
            score = 0
        parsed["qualification_score"] = max(0, min(100, score))

        if not isinstance(parsed.get("issues_found"), list):
            parsed["issues_found"] = []

        return parsed

    async def score_lead(
        self,
        technical_report: dict,
        target_service: str = "",
        target_segment: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Gera o scoring de um lead a partir do relatório técnico do site.

        Envia o relatório técnico passivo para o Groq (llama-3.1-8b-instant) e
        devolve a qualificação estruturada como JSON. A análise é apenas sobre
        dados já coletados passivamente — nenhuma ação não-passiva é feita.

        Args:
            technical_report: Dicionário do relatório retornado por
                TechnicalEnrichmentService.enrich_website, contendo ssl,
                http_headers, cms_detection, exposed_paths, errors e warnings.
            target_service: Serviço que a campanha quer vender (opcional).
                Quando fornecido, a LLM gera o qualification_reason como
                argumento de venda conectando os problemas ao serviço.
            target_segment: Segmento-alvo da campanha (opcional).

        Returns:
            Dicionário com qualification_score (int 0-100), primary_need (str),
            qualification_reason (str), pitch_angle (str), suggested_subject (str)
            e issues_found (lista); ou None em caso de falha (API indisponível,
            JSON inválido, etc.).
        """
        if not technical_report:
            logger.warning("Relatório técnico vazio; scoring abortado.")
            return None

        payload = self._build_payload(technical_report, target_service, target_segment)

        try:
            async with self._create_client() as client:
                response = await client.post(GROQ_URL, json=payload)
        except httpx.RequestError as e:
            logger.error("Erro de rede ao chamar Groq: %s", e)
            return None

        if response.status_code != 200:
            logger.error(
                "Groq respondeu HTTP %s: %s",
                response.status_code,
                response.text[:500],
            )
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

        # Normalização mínima do escore para int 0-100.
        try:
            score = int(parsed.get("qualification_score", 0))
        except (TypeError, ValueError):
            logger.warning(
                "qualification_score inválido (%r); usando 0.",
                parsed.get("qualification_score"),
            )
            score = 0
        parsed["qualification_score"] = max(0, min(100, score))

        if not isinstance(parsed.get("issues_found"), list):
            parsed["issues_found"] = []

        return parsed


async def main_test_scoring():
    """Teste standalone contra um relatório de exemplo (.google.com)."""
    sample_report = {
        "target_url": "https://www.google.com",
        "overall_status": "OK",
        "errors": [],
        "warnings": [],
        "ssl": {"ssl_ok": True, "https_redirect_ok": True},
        "http_headers": {"status_code": 200, "load_time_ms": 120},
        "cms_detection": None,
        "exposed_paths": [],
    }
    service = AIScoringService()
    result = await service.score_lead(sample_report)
    logger.info("%s", json.dumps(result, ensure_ascii=False, indent=2) if result else "None")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main_test_scoring())
