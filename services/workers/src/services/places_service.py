# services/workers/src/services/places_service.py
import httpx
import re
from typing import List, Dict, Optional
from config.settings import settings


PLACES_API_URL = "https://places.googleapis.com/v1/places:searchText"

FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.websiteUri",
    "places.nationalPhoneNumber",
    "places.formattedAddress",
    "places.primaryTypeDisplayName",
])


class GooglePlacesService:
    def __init__(self):
        self.api_key = settings.GOOGLE_API_KEY
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

        return {
            "name": name,
            "website": place.get("websiteUri"),
            "phone": place.get("nationalPhoneNumber"),
            "category": place.get("primaryTypeDisplayName", {}).get("text"),
            "full_address": address,
            "city": address_info["city"],
            "state": address_info["state"],
            "place_id_candidate": place.get("id"),
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

    async def search_places(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        Busca estabelecimentos na Places API (nova) usando texto livre.

        Realiza uma requisição POST para o endpoint `places:searchText`,
        solicitando apenas os campos definidos no FIELD_MASK para minimizar
        o custo por requisição. Itera pelas páginas de resultado usando
        `nextPageToken` até atingir `max_results` ou esgotar os resultados.

        Args:
            query: Texto de busca, ex: "Restaurantes em Campinas, SP".
            max_results: Número máximo de leads a retornar.

        Returns:
            Lista de dicionários no formato de lead prontos para persistência.
        """
        leads = []
        page_token = None

        print(f"Buscando na Places API: '{query}'")

        async with httpx.AsyncClient(timeout=30) as client:
            while len(leads) < max_results:
                payload: Dict = {
                    "textQuery": query,
                    "pageSize": min(20, max_results - len(leads)),  # máximo permitido pela API é 20
                    "languageCode": "pt-BR",
                }
                if page_token:
                    payload["pageToken"] = page_token

                response = await client.post(PLACES_API_URL, headers=self.headers, json=payload)
                response.raise_for_status()
                data = response.json()

                places = data.get("places", [])
                if not places:
                    break

                for place in places:
                    lead = self._parse_lead(place)
                    if lead:
                        leads.append(lead)
                        print(f"  ✅ {lead['name']} | site: {lead['website'] or 'N/A'} | tel: {lead['phone'] or 'N/A'}")

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

        print(f"Total encontrado: {len(leads)} lugares.")
        return leads