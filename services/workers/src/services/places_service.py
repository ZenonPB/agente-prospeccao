import logging
import httpx
import re
from typing import List, Dict, Optional, Any
from config.settings import settings
from services.domain_utils import is_social_domain, is_instagram_url
from services.geo_utils import city_matches, state_matches

logger = logging.getLogger(__name__)


PLACES_API_URL = "https://places.googleapis.com/v1/places:searchText"

FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.websiteUri",
    "places.nationalPhoneNumber",
    "places.formattedAddress",
    "places.primaryTypeDisplayName",
    # Reputação online: nota e nº de avaliações viram
    # evidência de scoring (negócio mal avaliado = oportunidade p/ serviços).
    "places.rating",
    "places.userRatingCount",
    "places.googleMapsUri",
])


class GooglePlacesService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GOOGLE_API_KEY
        self.headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }

    def _parse_lead(self, place: Dict) -> Optional[Dict]:
        """
        Transforma um item da resposta da Places API no formato de lead
        utilizado pelo sistema.

        Extrai e normaliza os campos relevantes do dicionário retornado
        pela API, incluindo nome, site, telefone, endereço, categoria e
        place_id. Retorna None se o lugar não tiver nome.

        Args:
            place: Dicionário de um lugar conforme retornado pela Places API.

        Returns:
            Dicionário no formato de lead, ou None se o nome estiver ausente.
        """
        name = place.get("displayName", {}).get("text")
        if not name:
            return None

        address = place.get("formattedAddress")
        address_info = self._parse_address(address)

        # Se o website da empresa for uma rede social (sem site próprio),
        # tratamos como SEM site — evita clonar perfil social falso, evitar
        # análise técnica errada (score 0) e o lead não marca "tem site".
        # Se for Instagram especificamente, capturamos como `instagram_url`
        # (sinal de atividade digital para o scoring e o pitch).
        raw_website = place.get("websiteUri")
        instagram_url = None
        if raw_website and is_instagram_url(raw_website):
            from urllib.parse import urlparse
            handle = (urlparse(raw_website).path or "").strip("/").split("/")[0]
            if handle:
                instagram_url = f"https://instagram.com/{handle}"
        website = raw_website if raw_website and not is_social_domain(raw_website) else None

        return {
            "name": name,
            "website": website,
            "phone": place.get("nationalPhoneNumber"),
            "category": place.get("primaryTypeDisplayName", {}).get("text"),
            "full_address": address,
            "city": address_info["city"],
            "state": address_info["state"],
            "place_id_candidate": place.get("id"),
            "rating": place.get("rating"),
            "rating_count": place.get("userRatingCount"),
            "maps_uri": place.get("googleMapsUri"),
            "instagram_url": instagram_url,
        }

    def _parse_address(self, full_address: Optional[str]) -> Dict[str, Optional[str]]:
        """
        Extrai cidade e estado de uma string de endereço formatado.

        A Places API retorna endereços no formato:
        "Rua X, 123 - Bairro, Cidade - SP, Brasil"
        A regex captura o padrão `Cidade - UF` para extrair os dois campos.

        Args:
            full_address: String de endereço completo retornada pela API.

        Returns:
            Dicionário com as chaves 'city', 'state' e 'country'.
        """
        result = {"city": None, "state": None, "country": "Brasil"}
        if not full_address:
            return result

        match = re.search(r'([\w\sà-úÀ-Ú]+)\s*-\s*([A-Z]{2}),', full_address)
        if match:
            result["city"] = match.group(1).strip()
            result["state"] = match.group(2).strip()

        return result

    async def search_places(
        self,
        query: str,
        max_results: int = 10,
        exclude_place_ids: Optional[set] = None,
        db=None,
        organization_id: Optional[str] = None,
        *,
        filter_city: Optional[str] = None,
        filter_state: Optional[str] = None,
        location_bias: Optional[Dict[str, Any]] = None,
        included_type: Optional[str] = None,
    ) -> List[Dict]:
        """
        Busca estabelecimentos na Places API (nova) usando texto livre.

        Realiza uma requisição POST para o endpoint `places:searchText`,
        solicitando apenas os campos definidos no FIELD_MASK para minimizar
        o custo por requisição. Itera pelas páginas de resultado usando
        `nextPageToken` até atingir `max_results` ou esgotar os resultados.

        Se `exclude_place_ids` for fornecido, os lugares cujo `place_id`
        já constam nesse conjunto são ignorados (antes de serem contados
        contra `max_results`) — usado para coleta incremental em campanhas
        que já possuem leads salvos, sem gastar páginas da API com
        resultados já conhecidos.

        Filtros pós-busca (descartar silenciosamente — sem paginação extra
        para compensar):
        - `filter_city` / `filter_state`: comparados (case/accents-insensitive)
          com o `city`/`state` parseado do `formattedAddress` do lead. Se o
          resultado não tiver `formattedAddress` parseável, é descartado.
        - `location_bias`: dict no formato do `locationRestriction.circle`
          (center + radius). Injetado no payload — restringe a busca na API
          ao invés de só filtrar depois (mais barato e semanticamente
          correto).
        - `included_type`: tipo da Places API (ex: "physiotherapist",
          "restaurant") — injetado como `includedType` no payload para que
          a API retorne apenas resultados da categoria correta.

        Cotas: com `db` + `organization_id`, verifica a cota
        diária de `GOOGLE_API_KEY` antes de cada página (fail-closed) e
        contabiliza uma chamada por página bem-sucedida.

        Args:
            query: Texto de busca, ex: "Restaurantes em Campinas, SP".
            max_results: Número máximo de leads novos a retornar.
            exclude_place_ids: Conjunto de place_ids já coletados a ignorar.
            db: Sessão (opcional) para o medidor de cotas.
            organization_id: Org (opcional) dona da chamada.
            filter_city: Cidade alvo (vinda de `Campaign.target_city`).
            filter_state: UF alvo (vinda de `Campaign.target_state`).
            location_bias: `locationRestriction.circle` para a API.
            included_type: `includedType` para a API.

        Returns:
            Lista de dicionários no formato de lead prontos para persistência.
        """
        leads: List[Dict] = []
        # Cópia própria: nunca mutar o set do chamador (`exclude_place_ids`).
        # Antes, `exclude_place_ids or set()` aliás o set quando não-vazio e o
        # `excluded.add` interno contaminava o `existing_ids_set` da org — o
        # `filter_new_batch_items` do pipeline via toda rodada como "já
        # coletada" (0 novos sempre, mesmo em campanha nova com leads de
        # outra campanha na org).
        excluded = set(exclude_place_ids or ())
        page_token = None
        pages = 0
        # Reduzido de 6 → 3: a API degrada a relevância após ~2-3 páginas
        # (preenche com matches fracos de outras regiões). 3 × 20 = 60 é
        # mais que suficiente para campanhas em cidades pequenas/médias;
        # para campanhas grandes, aumentar `max_results` no chamador.
        max_pages = 3

        location_filter_active = bool(filter_city or filter_state)
        if location_filter_active:
            logger.info(
                "Filtro geográfico ativo: city=%r state=%r — resultados fora do alvo serão descartados.",
                filter_city, filter_state,
            )

        logger.info("Buscando na Places API: '%s'", query)

        if db is not None and organization_id is not None:
            from services.quota_service import QuotaService
            if not QuotaService.can_consume(db, organization_id, "GOOGLE_API_KEY"):
                logger.warning(
                    "Cota diária esgotada para GOOGLE_API_KEY (org %s) — coleta bloqueada.",
                    organization_id,
                )
                return []

        async with httpx.AsyncClient(timeout=30) as client:
            while len(leads) < max_results and pages < max_pages:
                if db is not None and organization_id is not None:
                    from services.quota_service import QuotaService
                    if not QuotaService.can_consume(db, organization_id, "GOOGLE_API_KEY"):
                        logger.warning(
                            "Cota diária esgotada para GOOGLE_API_KEY (org %s) — interrompendo coleta.",
                            organization_id,
                        )
                        break
                pages += 1
                payload: Dict = {
                    "textQuery": query,
                    "pageSize": 20,  # máximo permitido pela API por página
                    "languageCode": "pt-BR",
                }
                if page_token:
                    payload["pageToken"] = page_token
                # Filtros no payload da API (raio geográfico + categoria):
                # atacam a causa raiz — a API não devolve lixo de fora.
                if location_bias:
                    payload["locationRestriction"] = location_bias
                if included_type:
                    payload["includedType"] = included_type

                response = await client.post(PLACES_API_URL, headers=self.headers, json=payload)
                response.raise_for_status()
                data = response.json()

                if db is not None and organization_id is not None:
                    from services.quota_service import QuotaService
                    QuotaService.consume(db, organization_id, "GOOGLE_API_KEY")

                places = data.get("places", [])
                if not places:
                    break

                for place in places:
                    # Teto real por rodada DENTRO da página: max_results não é
                    # estourado por uma página cheia (pageSize=20 > max).
                    if len(leads) >= max_results:
                        break
                    place_id = place.get("id")
                    # Filtra já coletados ANTES de gastar a vaga em max_results.
                    if place_id and place_id in excluded:
                        continue
                    lead = self._parse_lead(place)
                    if not lead:
                        continue
                    # Filtro pós-busca por cidade/UF (defesa em profundidade
                    # caso a API ainda devolva algo fora do locationRestriction).
                    if location_filter_active:
                        if not city_matches(lead.get("city"), filter_city):
                            logger.debug(
                                "Descartado por cidade: '%s' (city=%r != %r)",
                                lead.get("name"), lead.get("city"), filter_city,
                            )
                            continue
                        if not state_matches(lead.get("state"), filter_state):
                            logger.debug(
                                "Descartado por UF: '%s' (state=%r != %r)",
                                lead.get("name"), lead.get("state"), filter_state,
                            )
                            continue
                    leads.append(lead)
                    if lead.get("place_id_candidate"):
                        excluded.add(lead["place_id_candidate"])
                    logger.info("%s | site: %s | tel: %s", lead['name'], lead['website'] or 'N/A', lead['phone'] or 'N/A')

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

        logger.info("Total encontrado: %d lugares.", len(leads))
        return leads