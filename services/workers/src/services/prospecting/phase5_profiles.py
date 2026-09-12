"""Compatibility seam para a configuração declarativa da Fase 5.

A configuração com nomes de ofertas vive fora do core genérico de prospecting.
"""
from services.offer_profiles_phase5 import register_phase5_profiles

__all__ = ["register_phase5_profiles"]
