"""Interpretação de busca em linguagem natural para um contrato estruturado.

A LLM funciona somente como parser semântico: não consulta providers, não lê o
banco e não executa busca. O chamador valida o JSON retornado antes de usá-lo.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from config.settings import settings
from services.provider_client import groq_json_chat


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

_SYSTEM_PROMPT = """Você converte pedidos de prospecção B2B em filtros estruturados.
Retorne SOMENTE JSON. Nunca invente dados da empresa nem chame ferramentas.
O alvo deve ser 'companies' ou 'people'.

Formato:
{
  "target": "companies|people",
  "company_filters": { ... } | null,
  "people_filters": { ... } | null,
  "summary": "resumo curto em pt-BR",
  "assumptions": ["suposições explícitas"],
  "unresolved": ["ambiguidades que o usuário pode refinar"]
}

Filtros de companies permitidos: query, locations, industries, cnaes, sizes,
employee_min, employee_max, revenue_min, revenue_max, age_min, age_max,
technologies, signals, intent, keywords, exclusions, include_unknown, limit,
offset. Não gere expression booleana a menos que seja indispensável.

Filtros de people permitidos: query, company, domain, titles, functions,
seniorities, buyer_roles, locations, email_status, phone_status,
linkedin_status, min_actionable_score, limit, offset.

Vocabulário buyer_roles: ECONOMIC_BUYER, TECHNICAL_BUYER, CHAMPION, END_USER,
INFLUENCER. email_status: any|present|verified|missing. phone_status e
linkedin_status: any|present|missing.

Não transforme ausência de informação em exclusão. Quando o pedido não definir
um filtro, omita-o ou use o default neutro. Limite máximo 100 resultados."""


class SearchIntentInterpreter:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def interpret(
        self,
        query: str,
        *,
        target: str = "auto",
        db=None,
        organization_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        user_prompt = json.dumps(
            {"query": query, "preferred_target": target},
            ensure_ascii=False,
        )
        return await groq_json_chat(
            api_key=self.api_key,
            model=settings.GROQ_MODEL_CLASSIFY,
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            url=GROQ_URL,
            max_tokens=1400,
            temperature=0.0,
            db=db,
            organization_id=organization_id,
            quota_key="GROQ_API_KEY",
            reasoning_effort="none",
        )
