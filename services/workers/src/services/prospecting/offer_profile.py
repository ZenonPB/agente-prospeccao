"""OfferProfile — entidade central de inteligência comercial (consolidação §3).

Camadas:
- Archetype: fallback genérico (web_presence, business_opportunity, industrial).
- Vertical: contexto de mercado (digital, industrial, custom_products).
- OfferProfile: unidade principal — versão declarativa com ICP, discovery,
  prescoring, signals, intent, decision_makers, channels, qualification, outreach.

Cascata de resolução:
    explicit offer_profile
       ↓ fallback
    vertical
       ↓ fallback
    archetype
       ↓ fallback
    generic
"""
from dataclasses import MISSING, dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class OfferProfile:
    """Entidade declarativa versionada de uma oferta comercial.

    Todas as seções são opcionais com default vazio — só o que a oferta
    declara importa (consolidação §27: "Não duplicar inteligência comercial").
    """
    key: str
    archetype: str
    vertical: str
    version: str = "1.0"
    offer: Dict[str, Any] = field(default_factory=dict)
    icp: Dict[str, Any] = field(default_factory=dict)
    discovery: Dict[str, Any] = field(default_factory=dict)
    prescoring: Dict[str, Any] = field(default_factory=dict)
    enrichment: Dict[str, Any] = field(default_factory=dict)
    signals: Dict[str, Any] = field(default_factory=dict)
    intent: Dict[str, Any] = field(default_factory=dict)
    decision_makers: Dict[str, Any] = field(default_factory=dict)
    channels: Dict[str, Any] = field(default_factory=dict)
    qualification: Dict[str, Any] = field(default_factory=dict)
    outreach: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OfferProfile":
        """Reconstrói a partir de dict (ex.: persistência/seed)."""
        values: Dict[str, Any] = {}
        for name, definition in cls.__dataclass_fields__.items():
            if name in d:
                values[name] = d[name]
            elif definition.default is not MISSING:
                values[name] = definition.default
            elif definition.default_factory is not MISSING:
                values[name] = definition.default_factory()
        return cls(**values)


class OfferProfileRegistry:
    """Registry de OfferProfiles indexado por key, archetype e vertical."""

    def __init__(self):
        self._by_key: Dict[str, OfferProfile] = {}
        self._by_archetype: Dict[str, List[OfferProfile]] = {}
        self._by_vertical: Dict[str, List[OfferProfile]] = {}

    def register(self, profile: OfferProfile) -> None:
        previous = self._by_key.get(profile.key)
        if previous is not None:
            # Uma chave representa uma versão ativa do profile. Remova a
            # versão anterior dos índices secundários para que a resolução
            # não retorne dados obsoletos depois de um upsert.
            for index, value in (
                (self._by_archetype, previous.archetype),
                (self._by_vertical, previous.vertical),
            ):
                profiles = index.get(value, [])
                index[value] = [p for p in profiles if p.key != profile.key]
                if not index[value]:
                    index.pop(value, None)
        self._by_key[profile.key] = profile
        self._by_archetype.setdefault(profile.archetype, []).append(profile)
        self._by_vertical.setdefault(profile.vertical, []).append(profile)

    def get(self, key: str) -> Optional[OfferProfile]:
        return self._by_key.get(key)

    def list(self) -> List[OfferProfile]:
        return list(self._by_key.values())

    def by_archetype(self, archetype: str) -> List[OfferProfile]:
        return self._by_archetype.get(archetype, [])

    def by_vertical(self, vertical: str) -> List[OfferProfile]:
        return self._by_vertical.get(vertical, [])


@dataclass
class _ResolvedOffer:
    """Wrapper do OfferProfile + flag de qual nível da cascata foi usado."""
    profile: OfferProfile
    resolved_from: str  # "explicit" | "vertical" | "archetype" | "generic"

    def __getattr__(self, name):
        # Proxy transparente: ResolvedOffer.archetype == ResolvedOffer.profile.archetype
        return getattr(self.profile, name)


class OfferProfileResolver:
    """Resolve um OfferProfile com fallback em cascata (consolidação §3.5)."""

    GENERIC_KEY = "__generic__"

    def __init__(self, registry: OfferProfileRegistry):
        self.registry = registry

    def resolve(
        self,
        offer_profile_key: Optional[str] = None,
        vertical_key: Optional[str] = None,
        archetype_key: Optional[str] = None,
    ) -> _ResolvedOffer:
        # 1. Explicit offer_profile_key
        if offer_profile_key:
            p = self.registry.get(offer_profile_key)
            if p is not None:
                return _ResolvedOffer(p, "explicit")

        # 2. Vertical → primeiro OfferProfile com esse vertical
        if vertical_key:
            matches = self.registry.by_vertical(vertical_key)
            if matches:
                return _ResolvedOffer(matches[0], "vertical")

        # 3. Archetype → primeiro OfferProfile com esse archetype
        if archetype_key:
            matches = self.registry.by_archetype(archetype_key)
            if matches:
                return _ResolvedOffer(matches[0], "archetype")

        # 4. Generic — perfil vazio
        generic = OfferProfile(
            key=self.GENERIC_KEY,
            archetype="generic",
            vertical="generic",
        )
        return _ResolvedOffer(generic, "generic")
