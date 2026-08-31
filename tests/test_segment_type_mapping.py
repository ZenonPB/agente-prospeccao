"""Testes do mapeamento segmento → tipo Places."""
from services.segment_type_mapping import map_segment_to_places_types


def test_fisioterapia_resolve_para_physiotherapist():
    assert map_segment_to_places_types("Clínica de Fisioterapia") == "physiotherapist"
    assert map_segment_to_places_types("fisioterapeuta") == "physiotherapist"
    assert map_segment_to_places_types("Quiropraxia") == "physiotherapist"


def test_dentista_resolve_para_dentist():
    assert map_segment_to_places_types("Clínica Odontológica") == "dentist"
    assert map_segment_to_places_types("Dentista em Araraquara") == "dentist"


def test_restaurante_resolve_para_restaurant():
    assert map_segment_to_places_types("Restaurante") == "restaurant"
    assert map_segment_to_places_types("Pizzaria") == "restaurant"
    assert map_segment_to_places_types("Hamburgueria") == "restaurant"


def test_pet_shop_resolve_para_pet_store():
    assert map_segment_to_places_types("Pet Shop") == "pet_store"
    assert map_segment_to_places_types("Petshop") == "pet_store"
    # Veterinária é mais específico que pet shop, e vem antes — vence.
    assert map_segment_to_places_types("Clínica Veterinária") == "veterinary_care"


def test_hotel_resolve_para_lodging():
    assert map_segment_to_places_types("Hotel") == "lodging"
    assert map_segment_to_places_types("Pousada") == "lodging"


def test_segmento_desconhecido_retorna_none():
    assert map_segment_to_places_types("Consultoria de blockchain lunar") is None
    assert map_segment_to_places_types("") is None
    assert map_segment_to_places_types(None) is None


def test_normalizacao_case_e_acento():
    assert map_segment_to_places_types("FISIOTERAPIA") == "physiotherapist"
    assert map_segment_to_places_types("Restaurante") == "restaurant"
    assert map_segment_to_places_types("PADARIA") == "bakery"


def test_match_substring():
    # Match por substring — 'Pilates' deve resolver para academia.
    assert map_segment_to_places_types("Estúdio de Pilates em SP") == "gym"
    assert map_segment_to_places_types("Academia de musculação") == "gym"
