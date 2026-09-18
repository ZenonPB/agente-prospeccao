"""Overlays de workspace sobre o catálogo de ofertas (genérico).

Clona um OfferProfile base, aplica overrides declarativos de ICP/descoberta
e valida. Nenhum conhecimento de vertical mora aqui: recortes específicos
(pilotos, territórios) vivem nos chamadores, nunca neste módulo.
"""
from __future__ import annotations

from typing import Any, Mapping


def build_workspace_overlay(
    base_profile: Any, *, version: str,
    icp_overrides: Mapping[str, Any] | None = None,
    discovery_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Clona a Vertente base com overrides (sem mutar a base).

    Erro de validação (não-aviso) levanta ValueError: overlay inválido
    nunca chega ao banco.
    """
    from services.prospecting.offer_profile import OfferProfile
    from services.prospecting.offer_profile_validator import validate_profile

    snapshot = dict(base_profile.to_dict())
    if icp_overrides:
        icp = dict(snapshot.get("icp") or {})
        icp.update(dict(icp_overrides))
        snapshot["icp"] = icp
    if discovery_overrides:
        discovery = dict(snapshot.get("discovery") or {})
        discovery.update(dict(discovery_overrides))
        snapshot["discovery"] = discovery
    snapshot["version"] = version

    profile = OfferProfile.from_dict(snapshot)
    errors = [p for p in validate_profile(profile) if not str(p).startswith("aviso:")]
    if errors:
        raise ValueError(f"overlay inválido: {'; '.join(errors)}")
    return profile.to_dict()
