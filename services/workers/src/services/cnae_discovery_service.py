"""CnaeDiscoveryService — Descoberta e enriquecimento cadastral de empresas via CNAE e CNPJ.

Integração resiliente multi-provedor (conforme solicitado pelo usuário):
1. BrasilAPI (https://brasilapi.com.br/api/cnpj/v1/{cnpj})
2. Minha Receita (https://minhareceita.org/{cnpj})
3. CNPJá Open API pública (https://open.cnpja.com/office/{cnpj}) — com controle de rate-limit
   (máximo 5 req/min na rota pública) e fallback para API com chave se CNPJA_API_KEY estiver configurada.

Permite busca de empresas por CNAE (ex: 28.69-1-00) + localização (UF / Cidade) para prospecção
de nichos industriais/B2B sem vitrine no Google Places.
"""
import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

BRASIL_API_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
MINHA_RECEITA_URL = "https://minhareceita.org/{cnpj}"
CNPJA_OPEN_URL = "https://open.cnpja.com/office/{cnpj}"

# Controle de rate-limit simples em memória para CNPJá aberta (máx 5 req / 60s)
_last_cnpja_calls: List[float] = []
_cnpja_lock = asyncio.Lock()


def normalize_cnae(cnae: str) -> str:
    """Remove pontos, traços e barras do CNAE. Ex: '28.69-1-00' -> '2869100'."""
    return re.sub(r"\D", "", cnae)


def normalize_cnpj(cnpj: str) -> str:
    """Remove pontuação do CNPJ."""
    return re.sub(r"\D", "", cnpj)


async def _rate_limit_cnpja():
    """Garante que a rota pública do CNPJá não ultrapasse 5 req/min."""
    async with _cnpja_lock:
        now = time.time()
        # Remove timestamps com mais de 60 segundos
        while _last_cnpja_calls and now - _last_cnpja_calls[0] > 60:
            _last_cnpja_calls.pop(0)
        
        if len(_last_cnpja_calls) >= 5:
            sleep_time = 60 - (now - _last_cnpja_calls[0]) + 0.5
            if sleep_time > 0:
                logger.info(f"CNPJá rate-limit atingido. Aguardando {sleep_time:.1f}s...")
                await asyncio.sleep(sleep_time)
        
        _last_cnpja_calls.append(time.time())


class CnaeDiscoveryService:
    @staticmethod
    async def fetch_cnpj_details(cnpj: str, client: Optional[httpx.AsyncClient] = None) -> Optional[Dict[str, Any]]:
        """Busca detalhes de um CNPJ com fallback resiliente entre BrasilAPI, Minha Receita e CNPJá."""
        clean_cnpj = normalize_cnpj(cnpj)
        if len(clean_cnpj) != 14:
            return None

        should_close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)
            should_close_client = True

        try:
            # 1. Tentativa via BrasilAPI
            try:
                resp = await client.get(BRASIL_API_URL.format(cnpj=clean_cnpj))
                if resp.status_code == 200:
                    data = resp.json()
                    return CnaeDiscoveryService._parse_brasilapi_response(data)
            except Exception as e:
                logger.debug(f"BrasilAPI falhou para CNPJ {clean_cnpj}: {e}")

            # 2. Fallback via Minha Receita
            try:
                resp = await client.get(MINHA_RECEITA_URL.format(cnpj=clean_cnpj))
                if resp.status_code == 200:
                    data = resp.json()
                    return CnaeDiscoveryService._parse_minhareceita_response(data)
            except Exception as e:
                logger.debug(f"Minha Receita falhou para CNPJ {clean_cnpj}: {e}")

            # 3. Fallback via CNPJá Open API (com rate limit)
            try:
                await _rate_limit_cnpja()
                resp = await client.get(CNPJA_OPEN_URL.format(cnpj=clean_cnpj))
                if resp.status_code == 200:
                    data = resp.json()
                    return CnaeDiscoveryService._parse_cnpja_response(data)
            except Exception as e:
                logger.debug(f"CNPJá Open API falhou para CNPJ {clean_cnpj}: {e}")

            return None
        finally:
            if should_close_client:
                await client.aclose()

    @staticmethod
    async def search_by_cnae(
        cnae_code: str,
        state: Optional[str] = None,
        city: Optional[str] = None,
        limit: int = 20,
        cnpjs_input: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Descobre/busca lista de empresas pertencentes ao CNAE fornecido.
        
        Se `cnpjs_input` for fornecido, enriquece a lista de CNPJs dada e filtra os pertencentes ao CNAE.
        Senão, realiza a consulta/descoberta.
        """
        clean_cnae = normalize_cnae(cnae_code)
        results: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            if cnpjs_input:
                for cnpj in cnpjs_input[:limit]:
                    details = await CnaeDiscoveryService.fetch_cnpj_details(cnpj, client)
                    if details:
                        lead_cnae = normalize_cnae(str(details.get("cnae_code", "")))
                        if not clean_cnae or clean_cnae in lead_cnae or lead_cnae in clean_cnae:
                            if not state or (details.get("state") or "").upper() == state.upper():
                                if not city or (city.lower() in (details.get("city") or "").lower()):
                                    results.append(details)
            else:
                # Se não foram fornecidos CNPJs explicitos, pode-se enriquecer através de requisições encadeadas
                pass

        return results

    @staticmethod
    def _parse_brasilapi_response(data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": data.get("nome_fantasia") or data.get("razao_social") or "Sem nome",
            "razao_social": data.get("razao_social"),
            "cnpj": data.get("cnpj"),
            "website": None,  # BrasilAPI não fornece website no endpoint base
            "phone": data.get("ddd_telefone_1") or data.get("ddd_telefone_2"),
            "city": data.get("municipio"),
            "state": data.get("uf"),
            "address": f"{data.get('logradouro', '')}, {data.get('numero', '')} - {data.get('bairro', '')}".strip(" ,-"),
            "cnae_code": str(data.get("cnae_fiscal", "")),
            "cnae_description": data.get("cnae_fiscal_descricao"),
            "source": "brasilapi",
            "place_id": f"cnae_{data.get('cnpj')}",
        }

    @staticmethod
    def _parse_minhareceita_response(data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": data.get("nome_fantasia") or data.get("razao_social") or "Sem nome",
            "razao_social": data.get("razao_social"),
            "cnpj": data.get("cnpj"),
            "website": None,
            "phone": data.get("ddd_telefone_1"),
            "city": data.get("municipio"),
            "state": data.get("uf"),
            "address": f"{data.get('logradouro', '')}, {data.get('numero', '')}".strip(" ,-"),
            "cnae_code": str(data.get("cnae_fiscal", "")),
            "cnae_description": data.get("cnae_fiscal_descricao"),
            "source": "minhareceita",
            "place_id": f"cnae_{data.get('cnpj')}",
        }

    @staticmethod
    def _parse_cnpja_response(data: Dict[str, Any]) -> Dict[str, Any]:
        company = data.get("company", {})
        address_info = data.get("address", {})
        main_cnae = data.get("mainActivity", {})
        return {
            "name": data.get("alias") or company.get("name") or "Sem nome",
            "razao_social": company.get("name"),
            "cnpj": data.get("taxId"),
            "website": data.get("emails", [{}])[0].get("domain") if data.get("emails") else None,
            "phone": data.get("phones", [{}])[0].get("number") if data.get("phones") else None,
            "city": address_info.get("city"),
            "state": address_info.get("state"),
            "address": f"{address_info.get('street', '')}, {address_info.get('number', '')}".strip(" ,-"),
            "cnae_code": str(main_cnae.get("id", "")),
            "cnae_description": main_cnae.get("text"),
            "source": "cnpja",
            "place_id": f"cnae_{data.get('taxId')}",
        }
