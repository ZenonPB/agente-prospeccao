"""Resolução segura de identidade de empresas entre providers."""
from dataclasses import asdict, dataclass, field
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional

from services.domain_utils import normalize_domain


@dataclass(frozen=True)
class CompanyIdentityResult:
    """Resultado auditável de comparação entre entidades de empresas."""

    status: str
    matched_by: Optional[str]
    confidence: float
    auto_merge: bool
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa o resultado para JSONB/logs."""
        return asdict(self)


class CompanyIdentityResolver:
    """Compara candidatos sem realizar merge fuzzy automático."""

    def resolve(
        self,
        reference: Dict[str, Any],
        candidates: Iterable[Dict[str, Any]],
    ) -> CompanyIdentityResult:
        """Resolve a melhor identidade usando chaves fortes e candidato fuzzy."""
        candidates = list(candidates)
        reference_keys = self._keys(reference)
        provenance = self._provenance(reference, candidates)
        for candidate in candidates:
            candidate_keys = self._keys(candidate)
            for key_name, confidence in (
                ("cnpj", 1.0),
                ("normalized_domain", 0.95),
                ("place_id", 0.90),
            ):
                if reference_keys.get(key_name) and reference_keys[key_name] == candidate_keys.get(key_name):
                    return CompanyIdentityResult(
                        status="confirmed",
                        matched_by=key_name,
                        confidence=confidence,
                        auto_merge=True,
                        provenance=provenance,
                    )
        for candidate in candidates:
            candidate_keys = self._keys(candidate)
            if self._same_name_location(reference_keys, candidate_keys):
                return CompanyIdentityResult(
                    status="candidate",
                    matched_by="name_location_candidate",
                    confidence=0.65,
                    auto_merge=False,
                    provenance=provenance,
                )
        return CompanyIdentityResult(
            status="new",
            matched_by=None,
            confidence=0.0,
            auto_merge=False,
            provenance=provenance,
        )

    @classmethod
    def _keys(cls, item: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """Extrai chaves canônicas sem modificar o candidato original."""
        cnpj = cls._digits(item.get("cnpj"))
        domain = item.get("normalized_domain") or normalize_domain(item.get("website"))
        place_id = item.get("place_id") or item.get("place_id_candidate")
        return {
            "cnpj": cnpj or None,
            "normalized_domain": str(domain).strip().lower() if domain else None,
            "place_id": str(place_id).strip() if place_id else None,
            "name": cls._text(item.get("company_name") or item.get("name")),
            "city": cls._text(item.get("city")),
            "state": cls._text(item.get("state") or item.get("uf")),
        }

    @staticmethod
    def _digits(value: Any) -> str:
        """Remove máscara de CNPJ e retorna apenas dígitos."""
        return re.sub(r"\D", "", str(value or ""))

    @staticmethod
    def _text(value: Any) -> str:
        """Normaliza texto para comparações conservadoras."""
        normalized = unicodedata.normalize("NFKD", str(value or ""))
        plain = "".join(char for char in normalized if not unicodedata.combining(char))
        return re.sub(r"[^a-z0-9]+", " ", plain.lower()).strip()

    @staticmethod
    def _same_name_location(reference: Dict[str, Optional[str]], candidate: Dict[str, Optional[str]]) -> bool:
        """Identifica possível merge por nome e local, sem confirmá-lo."""
        if not reference.get("name") or not candidate.get("name"):
            return False
        if not (
            (reference.get("city") and candidate.get("city"))
            or (reference.get("state") and candidate.get("state"))
        ):
            return False
        if reference.get("city") and candidate.get("city") and reference["city"] != candidate["city"]:
            return False
        if reference.get("state") and candidate.get("state") and reference["state"] != candidate["state"]:
            return False
        reference_tokens = set(reference["name"].split())
        candidate_tokens = set(candidate["name"].split())
        overlap = len(reference_tokens & candidate_tokens)
        return overlap >= 2 or reference["name"] in candidate["name"] or candidate["name"] in reference["name"]

    @classmethod
    def _provenance(cls, reference: Dict[str, Any], candidates: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        """Agrega providers, consultas e identificadores sem dados sensíveis."""
        items = [reference, *list(candidates)]
        providers = list(dict.fromkeys(
            str(item["provider"]).strip()
            for item in items
            if item.get("provider")
        ))
        queries = list(dict.fromkeys(
            str(item["provider_query"]).strip()
            for item in items
            if item.get("provider_query")
        ))
        identifiers = list(dict.fromkeys(
            str(item.get("provider_candidate_id") or item.get("id")).strip()
            for item in items
            if item.get("provider_candidate_id") or item.get("id")
        ))
        return {
            "providers": providers,
            "provider_queries": queries,
            "provider_candidate_ids": identifiers,
        }