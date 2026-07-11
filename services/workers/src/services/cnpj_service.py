"""CnpjService — enriquecimento cadastral via Receita Federal.

Provedores (em ordem de precedência, com fallback transparente):
- BrasilAPI (https://brasilapi.com.br/api/cnpj/v1/{cnpj}) — pública, gratuita,
  estável e sem auth. JSON com qsa[], razao_social, porte, CNAE etc.
- CNPJá (https://api.cnpja.com/office/{cnpj}) — comercial, requer
  CNPJA_API_KEY opcional via settings. Usada quando BrasilAPI está instável
  ou para dados adicionais (regime tributário etc).

Não há busca reversa por nome neste sprint — a descoberta do CNPJ a partir
do Google Places é responsabilidade futura (Hunter/Google dorks). Hoje o
vendedor cola o CNPJ manualmente na página do lead.

Transforma a resposta do provedor em um DTO padrão:
{
  "company": {razao_social, nome_fantasia, cnpj, porte, ...},
  "contacts": [{name, role_label, role_enum, document_cpf, ...}, ...]
}
"""
import logging
import os
import sys
from datetime import date
from typing import Any, Dict, List, Optional

import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.settings import settings  # noqa: E402

logger = logging.getLogger(__name__)

BRASIL_API_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
CNPJA_API_URL = "https://api.cnpja.com/office/{cnpj}"

# Qualificações de sócio que sinalizam um decisor relevante (não nominal).
# Lista não exaustiva — baseada na tabela da Receita (código → descrição).
DECISOR_QUALIFICATIONS = {
    "Presidente",
    "Diretor",
    "Sócio-Administrador",
    "Sócio",
    "Conselheiro de Administração",
    "Administrador",
    "Sócio Gerente",
    "Sócio-Comanditado",
    "Sócio-Comanditário",
}


def normalize_cnpj(cnpj: str) -> str:
    """Remove máscara do CNPJ — só dígitos, 14 caracteres."""
    digits = "".join(ch for ch in cnpj if ch.isdigit())
    return digits


def is_valid_cnpj(cnpj: str) -> bool:
    digits = normalize_cnpj(cnpj)
    return len(digits) == 14 and digits.isdigit()


def _map_qualification_to_role(qual: str) -> str:
    """Mapeia a `qualificacao_socio` (texto livre da Receita) para o enum
    ContactRole usado no nosso modelo. Heurística simples — strings
    conhecidas; não sabemos todos os códigos da Receita."""
    q = (qual or "").strip().lower()
    if "presidente" in q:
        return "CEO"
    if "diretor" in q:
        return "DIRETOR"
    if "administrador" in q:
        return "ADMINISTRADOR"
    if "sócio" in q or "socio" in q:
        return "SOCIO"
    return "OUTRO"


def _calculate_confidence(role_enum: str, has_email: bool) -> int:
    """Confiança 0-100 do contato como decisor-atingível."""
    base = 70  # CNPJ da Receita é fonte primária; sócios listados são reais.
    if role_enum in ("CEO", "DIRETOR", "ADMINISTRADOR"):
        base = 90
    if has_email:
        base = min(100, base + 5)
    return base


def _parse_brasilapi(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Transforma resposta BrasilAPI no DTO padrão."""
    qsa = payload.get("qsa") or []
    contacts: List[Dict[str, Any]] = []
    for s in qsa:
        name = (s.get("nome_socio") or "").strip()
        if not name:
            continue
        qual = s.get("qualificacao_socio") or ""
        role_enum = _map_qualification_to_role(qual)
        contacts.append({
            "name": name,
            "role_enum": role_enum,
            "role_label": qual or role_enum,
            "document_cpf": (s.get("cnpj_cpf_do_socio") or "").strip() or None,
            "data_entrada": s.get("data_entrada_sociedade"),
            "faixa_etaria": s.get("faixa_etaria"),
            "is_primary": False,
            "confidence": _calculate_confidence(role_enum, has_email=False),
            "source": "cnpj_receita:brasilapi",
            "raw": s,
        })

    # Heurística de primary: primeiro 'Presidente'/'CEO', depois qualquer
    # Diretor, depois primeiro Sócio. Receita lista em ordem alfabética —
    # não há ranking de Influência, então é apenas um default.
    primary_idx = None
    for preferred in ("CEO", "DIRETOR", "ADMINISTRADOR", "SOCIO"):
        for i, c in enumerate(contacts):
            if c["role_enum"] == preferred:
                primary_idx = i
                break
        if primary_idx is not None:
            break
    if primary_idx is not None:
        contacts[primary_idx]["is_primary"] = True
        # Reordena pondo primary em [0]
        contacts.insert(0, contacts.pop(primary_idx))

    data_inicio = payload.get("data_inicio_atividade") or payload.get("data_abertura")
    idade_anos: Optional[int] = None
    if data_inicio:
        try:
            year = int(str(data_inicio)[:4])
            idade_anos = max(0, date.today().year - year)
        except (ValueError, TypeError):
            idade_anos = None

    cnaes_sec = payload.get("cnaes_secundarios") or []
    company = {
        "cnpj": payload.get("cnpj"),
        "razao_social": payload.get("razao_social"),
        "nome_fantasia": payload.get("nome_fantasia"),
        "porte": payload.get("porte"),
        "porte_label": payload.get("porte"),
        "natureza_juridica": payload.get("natureza_juridica"),
        "capital_social": payload.get("capital_social"),
        "situacao_cadastral": payload.get("descricao_situacao_cadastral")
        or str(payload.get("situacao_cadastral") or ""),
        "data_abertura": data_inicio,
        "idade_anos": idade_anos,
        "cnae_principal": str(payload.get("cnae_fiscal") or "")[:20] or None,
        "cnae_principal_label": payload.get("cnae_fiscal_descricao"),
        "cnae_secundarios": [
            {"codigo": c.get("codigo"), "descricao": c.get("descricao")}
            for c in cnaes_sec
        ],
        "endereco": {
            "uf": payload.get("uf"),
            "municipio": payload.get("municipio"),
            "logradouro": payload.get("logradouro"),
            "numero": payload.get("numero"),
            "bairro": payload.get("bairro"),
            "cep": payload.get("cep"),
            "complemento": payload.get("complemento"),
        },
        "municipios_ativos": [payload.get("municipio")] if payload.get("municipio") else [],
        "email": payload.get("email"),
        "telefone": (payload.get("ddd_telefone_1") or "").strip() or None,
        "raw": payload,
    }
    return {"company": company, "contacts": contacts, "source": "brasilapi"}


def _parse_cnpja(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Transforma resposta CNPJá no mesmo DTO. Estrutura é diferente da
    BrasilAPI — nomes de campos foram padronizados pela CNPJá."""
    persons = payload.get("company") or {}
    members = payload.get("members") or []
    contacts: List[Dict[str, Any]] = []
    for m in members:
        person = m.get("person") or {}
        name = (person.get("name") or "").strip()
        if not name:
            continue
        qual = (m.get("role") or {}).get("text") or m.get("qualification") or ""
        role_enum = _map_qualification_to_role(qual)
        contacts.append({
            "name": name,
            "role_enum": role_enum,
            "role_label": qual or role_enum,
            "document_cpf": (person.get("taxId") or "").strip() or None,
            "is_primary": False,
            "confidence": _calculate_confidence(role_enum, has_email=False),
            "source": "cnpj_receita:cnpja",
            "raw": m,
        })

    primary_idx = None
    for preferred in ("CEO", "DIRETOR", "ADMINISTRADOR", "SOCIO"):
        for i, c in enumerate(contacts):
            if c["role_enum"] == preferred:
                primary_idx = i
                break
        if primary_idx is not None:
            break
    if primary_idx is not None:
        contacts[primary_idx]["is_primary"] = True
        contacts.insert(0, contacts.pop(primary_idx))

    abertura = payload.get("founded") or ""
    idade_anos: Optional[int] = None
    if abertura:
        try:
            year = int(str(abertura)[:4])
            idade_anos = max(0, date.today().year - year)
        except (ValueError, TypeError):
            idade_anos = None

    addr = payload.get("address") or {}
    company = {
        "cnpj": payload.get("taxId"),
        "razao_social": persons.get("name"),
        "nome_fantasia": persons.get("alias"),
        "porte": (payload.get("size") or {}).get("text"),
        "porte_label": (payload.get("size") or {}).get("text"),
        "natureza_juridica": (payload.get("legalNature") or {}).get("text"),
        "capital_social": payload.get("equity"),
        "situacao_cadastral": (payload.get("status") or {}).get("text"),
        "data_abertura": abertura,
        "idade_anos": idade_anos,
        "cnae_principal": str((payload.get("mainActivity") or {}).get("id") or "")[:20] or None,
        "cnae_principal_label": (payload.get("mainActivity") or {}).get("text"),
        "cnae_secundarios": [
            {"codigo": a.get("id"), "descricao": a.get("text")}
            for a in (payload.get("sideActivities") or [])
        ],
        "endereco": {
            "uf": (addr.get("state") or {}).get("code"),
            "municipio": (addr.get("city") or {}).get("name"),
            "logradouro": addr.get("street"),
            "numero": addr.get("number"),
            "bairro": addr.get("district"),
            "cep": addr.get("zip"),
        },
        "municipios_ativos": [(addr.get("city") or {}).get("name")] if addr.get("city") else [],
        "email": payload.get("email"),
        "telefone": payload.get("phone"),
        "raw": payload,
    }
    return {"company": company, "contacts": contacts, "source": "cnpja"}


class CnpjService:
    """Lookup cadastral de lead via CNPJ, com fallback BrasilAPI→CNPJá."""

    def __init__(self):
        self.cnpja_key: Optional[str] = getattr(settings, "CNPJA_API_KEY", None)

    def _create_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=20.0)

    async def lookup(self, cnpj: str) -> Optional[Dict[str, Any]]:
        """Busca dados cadastrais + sócios (decisores) por CNPJ.

        Tenta BrasilAPI primeiro; se falhar (timeout/5xx/4xx), tenta CNPJá
        quando houver C NPJA_API_KEY configurada. Retorna o DTO padrão ou
        None se nenhum provedor respondêu válido.
        """
        clean = normalize_cnpj(cnpj)
        if not is_valid_cnpj(clean):
            logger.warning("CNPJ inválido recebido: %s", cnpj)
            return None

        async with self._create_client() as client:
            try:
                r = await client.get(BRASIL_API_URL.format(cnpj=clean))
                if r.status_code == 200:
                    payload = r.json()
                    if payload and not payload.get("message"):
                        return _parse_brasilapi(payload)
                logger.warning(
                    "BrasilAPI respondeu HTTP %s para CNPJ %s; tentando fallback.",
                    r.status_code, clean,
                )
            except httpx.RequestError as e:
                logger.warning("Erro de rede BrasilAPI: %s", e)

            if self.cnpja_key:
                try:
                    r2 = await client.get(
                        CNPJA_API_URL.format(cnpj=clean),
                        headers={"Authorization": f"Bearer {self.cnpja_key}"},
                    )
                    if r2.status_code == 200:
                        payload2 = r2.json()
                        if payload2:
                            return _parse_cnpja(payload2)
                    logger.error("CNPJá respondeu HTTP %s: %s",
                                 r2.status_code, r2.text[:200])
                except httpx.RequestError as e:
                    logger.error("Erro de rede CNPJá: %s", e)

        return None


async def _main_test():
    """Smoke test: lookup do CNPJ do Banco do Brasil."""
    svc = CnpjService()
    data = await svc.lookup("00.000.000/0001-91")
    if not data:
        logger.error("Falha no lookup.")
        return
    logger.info(" fonte=%s companhia=%s contatos=%d",
                data["source"], data["company"]["razao_social"], len(data["contacts"]))
    if data["contacts"]:
        logger.info(" primary: %s (%s)",
                    data["contacts"][0]["name"], data["contacts"][0]["role_label"])


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main_test())
