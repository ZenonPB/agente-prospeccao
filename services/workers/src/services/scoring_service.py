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
    "Regras de scoring (0-100):\n"
    "- 80-100: crítico (.env exposto, .git exposto, sem HTTPS)\n"
    "- 60-79: múltiplos problemas de segurança ou performance\n"
    "- 40-59: headers ausentes, WordPress detectado\n"
    "- 20-39: site funcional com melhorias possíveis\n"
    "- 0-19: site bem configurado, baixa oportunidade\n\n"
    "Retorne um JSON com exatamente esta estrutura:\n"
    "{{\n"
    '  "qualification_score": <inteiro 0-100>,\n'
    '  "primary_need": "SECURITY_FIX" | "PERFORMANCE" | "MODERN_WEBSITE" | "SEO" | "NONE",\n'
    '  "qualification_reason": "<2-4 frases em pt-BR, para o dono da empresa>",\n'
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

    def _build_payload(self, technical_report: Dict[str, Any]) -> Dict[str, Any]:
        """Monta o payload para a API de chat completions do Groq."""
        report_str = json.dumps(technical_report, ensure_ascii=False, indent=2)
        user_prompt = USER_PROMPT_TEMPLATE.format(report=report_str)
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

    async def score_lead(self, technical_report: dict) -> Optional[Dict[str, Any]]:
        """Gera o scoring de um lead a partir do relatório técnico do site.

        Envia o relatório técnico passivo para o Groq (llama-3.1-8b-instant) e
        devolve a qualificação estruturada como JSON. A análise é apenas sobre
        dados já coletados passivamente — nenhuma ação não-passiva é feita.

        Args:
            technical_report: Dicionário do relatório retornado por
                TechnicalEnrichmentService.enrich_website, contendo ssl,
                http_headers, cms_detection, exposed_paths, errors e warnings.

        Returns:
            Dicionário com qualification_score (int 0-100), primary_need (str),
            qualification_reason (str) e issues_found (lista); ou None em caso
            de falha (API indisponível, JSON inválido, etc.).
        """
        if not technical_report:
            logger.warning("Relatório técnico vazio; scoring abortado.")
            return None

        payload = self._build_payload(technical_report)

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
    print(json.dumps(result, ensure_ascii=False, indent=2) if result else "None")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main_test_scoring())
