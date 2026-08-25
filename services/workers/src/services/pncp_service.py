"""PncpService — coleta de fornecedores de contratos públicos via PNCP.

Consulta a API pública de consulta do PNCP (https://pncp.gov.br/api/consulta/v1,
sem autenticação e sem custo) em busca de CONTRATOS publicados numa janela de
datas. Cada contrato expõe o fornecedor vencedor (CNPJ + razão social) —
empresas com porte e setor comprovados, sinal comercial forte para prospecção
B2B industrial.

Leitura de dados abertos oficiais (Lei 14.133/2021) — passiva por natureza.
"""
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

PNCP_CONSULTA_BASE = "https://pncp.gov.br/api/consulta/v1"
MAX_PAGES_PER_SEARCH = 10
OBJETO_NOTE_MAX = 140


def format_pncp_date(value: date) -> str:
    """Datas da API de consulta são compactas: YYYYMMDD."""
    return value.strftime("%Y%m%d")


def default_date_window(days_back: int = 30, today: Optional[date] = None):
    """Janela padrão de publicação: últimos N dias (início inclusivo)."""
    today = today or date.today()
    start = today - timedelta(days=max(days_back - 1, 0))
    return format_pncp_date(start), format_pncp_date(today)


def unique_suppliers(parsed_contracts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Agrupa contratos por CNPJ do fornecedor.

    Devolve um fornecedor por CNPJ com `contracts` (lista), `total_value`
    (soma dos valores globais conhecidos) e ordenado pelo contrato mais
    recente primeiro — o fornecedor mais quente lidera a lista.
    """
    by_cnpj: Dict[str, Dict[str, Any]] = {}

    def _sort_key(contract: Dict[str, Any]) -> str:
        return contract.get("data_assinatura") or ""

    for parsed in parsed_contracts:
        cnpj = parsed["cnpj"]
        entry = by_cnpj.get(cnpj)
        if entry is None:
            entry = {
                "cnpj": cnpj,
                "supplier_name": parsed.get("supplier_name"),
                "place_id_candidate": parsed.get("place_id_candidate"),
                "contracts": [],
                "total_value": 0.0,
            }
            by_cnpj[cnpj] = entry
        entry["contracts"].append(parsed.get("contract") or {})
        if parsed.get("contract", {}).get("valor_global"):
            entry["total_value"] += float(parsed["contract"]["valor_global"])

    suppliers = sorted(
        by_cnpj.values(),
        key=lambda s: max((_sort_key(c) for c in s["contracts"]), default=""),
        reverse=True,
    )
    return suppliers


def format_contract_note(supplier: Dict[str, Any]) -> str:
    """Resumo legível do histórico PNCP para as notas do lead."""
    contracts = supplier.get("contracts", [])
    count = len(contracts)
    total = supplier.get("total_value") or 0.0
    head = f"{count} contrato(s) público(s) no período"
    if total:
        total_txt = f"{total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        head += f" — R$ {total_txt}"
    if not contracts:
        return head
    latest = contracts[0]
    objeto = (latest.get("objeto") or "").strip()
    if len(objeto) > OBJETO_NOTE_MAX:
        objeto = objeto[:OBJETO_NOTE_MAX].rstrip() + "…"
    orgao = (latest.get("orgao") or "").strip()
    parts = [head]
    if objeto:
        parts.append(f"último: {objeto}")
    if orgao:
        parts.append(f"órgão: {orgao}")
    return " · ".join(parts)


class PncpService:
    @staticmethod
    def parse_contract(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normaliza um contrato do PNCP; só interessam fornecedores PJ (CNPJ).

        Pessoa física não é lead B2B; CNPJ inválido não cruza com a Receita.
        """
        if str(item.get("tipoPessoa") or "").upper() != "PJ":
            return None
        cnpj = "".join(c for c in str(item.get("niFornecedor") or "") if c.isdigit())
        if len(cnpj) != 14:
            return None
        orgao = item.get("orgaoEntidade") or {}
        unidade = item.get("unidadeOrgao") or {}
        return {
            "cnpj": cnpj,
            "supplier_name": item.get("nomeRazaoSocialFornecedor"),
            "place_id_candidate": f"pncp_{cnpj}",
            "contract": {
                "numero_controle": item.get("numeroControlePNCP"),
                "objeto": item.get("objetoContrato"),
                "orgao": orgao.get("razaoSocial"),
                "uf": (str(unidade.get("ufSigla") or "").upper() or None),
                "valor_global": item.get("valorGlobal"),
                "data_assinatura": item.get("dataAssinatura"),
            },
        }

    @staticmethod
    async def search_supplier_contracts(
        data_inicial: str,
        data_final: str,
        uf: Optional[str] = None,
        keyword: Optional[str] = None,
        max_suppliers: int = 20,
        client: Optional[httpx.AsyncClient] = None,
    ) -> List[Dict[str, Any]]:
        """Busca contratos publicados na janela e devolve fornecedores únicos.

        Para cedo quando atinge `max_suppliers` ou esgota as páginas. Falhas
        pontuais de página encerram a busca com o que já foi coletado — nunca
        estouram exceção para o chamador (mesma postura resiliente do CNAE).
        """
        owns_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

        try:
            term = (keyword or "").strip().lower()
            uf_filter = (uf or "").strip().upper()
            all_parsed: List[Dict[str, Any]] = []

            for page in range(1, MAX_PAGES_PER_SEARCH + 1):
                try:
                    resp = await client.get(
                        f"{PNCP_CONSULTA_BASE}/contratos",
                        params={
                            "dataInicial": data_inicial,
                            "dataFinal": data_final,
                            "pagina": page,
                        },
                    )
                    if resp.status_code != 200:
                        logger.warning(
                            "PNCP /contratos retornou %s na página %s", resp.status_code, page
                        )
                        break
                    payload = resp.json()
                except Exception as exc:
                    logger.warning("Falha consultando PNCP (página %s): %s", page, exc)
                    break

                items = payload.get("data") or []
                for raw in items:
                    parsed = PncpService.parse_contract(raw)
                    if not parsed:
                        continue
                    contract = parsed.get("contract") or {}
                    if uf_filter and (contract.get("uf") or "") != uf_filter:
                        continue
                    if term and term not in str(contract.get("objeto") or "").lower():
                        continue
                    all_parsed.append(parsed)

                unique_so_far = {p["cnpj"] for p in all_parsed}
                if len(unique_so_far) >= max_suppliers:
                    break
                total_pages = payload.get("totalPaginas") or 0
                if not items or page >= total_pages:
                    break

            return unique_suppliers(all_parsed)[:max_suppliers]
        finally:
            if owns_client:
                await client.aclose()

    @staticmethod
    async def enrich_supplier(supplier: Dict[str, Any]) -> Dict[str, Any]:
        """Cruza o fornecedor com os dados cadastrais da Receita (CNAE/porte).

        Se a Receita falhar, mantém os dados mínimos do próprio contrato —
        o lead ainda nasce com razão social e CNPJ válidos.
        """
        # Import lazy evita ciclo de import entre serviços irmãos.
        from services.cnae_discovery_service import CnaeDiscoveryService

        details = await CnaeDiscoveryService.fetch_cnpj_details(supplier["cnpj"])
        if details:
            supplier["details"] = details
        return supplier
