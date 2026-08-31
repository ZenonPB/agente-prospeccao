"""Mapeamento de `Campaign.target_segment` → tipos da Places API (New).

A `searchText` (Places API New) aceita `includedType` para limitar resultados
a categorias específicas. Isso elimina o ruído de "empresa que menciona o termo
em qualquer lugar" e devolve apenas lugares cuja **categoria primária** bate.

Os tipos aqui seguem a taxonomia oficial do Google:
https://developers.google.com/maps/documentation/places/web-service/supported_types
"""
from __future__ import annotations

import logging
import unicodedata
from typing import List, Optional

logger = logging.getLogger(__name__)


# Ordem = prioridade. O primeiro match vence.
_SEGMENT_TO_TYPES: List[tuple] = [
    # Saúde
    (["fisioterapia", "fisioterapeuta", "quiropraxia"], ["physiotherapist"]),
    (["dentista", "odontologia", "odontologico", "odontologica"], ["dentist"]),
    (["psicolog", "psicanalis"], ["doctor"]),
    (["veterinaria", "veterinario"], ["veterinary_care"]),
    (["pet shop", "petshop"], ["pet_store"]),
    (["farmacia", "drogaria"], ["pharmacy"]),
    (["hospital"], ["hospital"]),
    (["clinica medica", "medico", "medica", "consultorio"], ["doctor"]),
    (["academia", "musculacao", "crossfit", "pilates", "estudio de pilates"], ["gym", "fitness_center"]),
    (["estetica", "salao", "salao de beleza", "barbearia", "manicure"], ["beauty_salon", "hair_care"]),
    (["clinica"], ["doctor", "health"]),

    # Alimentação
    (["restaurante", "pizzaria", "lanchonete", "hamburgueria", "doceria"], ["restaurant"]),
    (["cafeteria", "café", "cafe"], ["cafe"]),
    (["bar", "pub", "cervejaria"], ["bar"]),

    # Comércio e serviços
    (["loja de roupa", "lojas de roupa", "boutique", "moda"], ["clothing_store"]),
    (["mercado", "supermercado", "mercearia"], ["supermarket", "grocery_store"]),
    (["padaria"], ["bakery"]),
    (["floricultura"], ["florist"]),
    (["livraria"], ["book_store"]),
    (["autopeças", "autopecas", "oficina mecanica", "oficina"], ["car_repair"]),
    (["concessionaria", "concessionária"], ["car_dealer"]),

    # Hospedagem e turismo
    (["hotel", "pousada", "hostel"], ["lodging"]),

    # Educação
    (["escola", "colegio", "creche", "faculdade", "universidade"], ["school", "university"]),

    # Advocacia / contábil
    (["escritorio de advocacia", "advocacia", "advogado"], ["lawyer"]),
    (["escritorio de contabilidade", "contabilidade", "contador"], ["accounting"]),

    # Imobiliário
    (["imobiliaria", "imobiliária"], ["real_estate_agency"]),

    # Tecnologia
    (["startup", "empresa de tecnologia", "empresa de ti", "consultoria de ti"], []),
]


def _norm(text: str) -> str:
    nfkd = unicodedata.normalize("NFD", text)
    return " ".join(
        "".join(c for c in chunk if unicodedata.category(c) != "Mn")
        for chunk in nfkd.lower().split()
    )


def _matches_keyword(segment_norm: str, keyword: str) -> bool:
    """Word-boundary match (não substring).

    "clinica" deve casar em "clinica de fisioterapia" mas NÃO em
    "clinica veterinaria" se "veterinaria" for palavra-chave mais específica
    listada antes. Usamos word-boundary para evitar que 'fisio' case em
    'fisioterapia' (não, 'fisio' é prefixo de 'fisioterapia', mas word
    boundary trata como palavra separada — 'fisio' em 'fisioterapia' não
    é palavra completa). Para esses casos excepcionais, a keyword mais
    longa vence naturalmente.
    """
    if " " in keyword or "-" in keyword:
        return keyword in segment_norm
    # palavra única: word-boundary
    return f" {keyword} " in f" {segment_norm} " or segment_norm == keyword


def map_segment_to_places_types(segment: Optional[str]) -> Optional[str]:
    """Devolve o tipo da Places API a usar como `includedType` para o segmento.

    Estratégia: primeiro segmento que casar (palavra completa, com
    "clinica" caindo por último — é genérico demais). Retorna o **primeiro**
    tipo da lista (mais específico). Se nada casar, retorna None — o caller
    NÃO aplica `includedType` (fail-open: continuar sem `includedType` é
    melhor que filtrar tudo errado).
    """
    if not segment:
        return None
    norm = _norm(segment)
    for keywords, types in _SEGMENT_TO_TYPES:
        for kw in keywords:
            if _matches_keyword(norm, _norm(kw)):
                return types[0] if types else None
    logger.debug("Segmento '%s' sem mapeamento para Places types.", segment)
    return None
