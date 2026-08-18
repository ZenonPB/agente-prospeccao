"""Testes da dedupe de lote da coleta (erro de UniqueViolation no commit).

Cobre o caminho de Places: quando o Google devolve duas lojas da MESMA rede
com o mesmo `normalized_domain` numa única rodada, a segunda não pode entrar
no lote (violaria `uq_leads_org_normalized_domain` no commit em lote — e com
`autoflush=False` a query de dedupe dentro do loop não enxerga a irmã).
"""
from src.pipeline_worker import _prepare_batch_items, filter_new_batch_items  # noqa: E402


def test_prepare_batch_items_anota_normalized_domain():
    items = [{"name": "Loja A", "website": "https://site.rede.com.br/"}]
    prepared = _prepare_batch_items(items)
    assert prepared[0]["normalized_domain"] == "site.rede.com.br"
    # Domínio social (sem site próprio) não vira chave de dedupe.
    social = _prepare_batch_items([{"name": "X", "website": "https://instagram.com/x"}])
    assert social[0]["normalized_domain"] is None


def test_segunda_loja_mesma_rede_e_filtrada_do_lote():
    """Duas filiais com o MESMO site no mesmo lote = só a primeira entra."""
    items = [
        {"name": "Supermercados 14", "website": "https://site.supermercado14.com.br"},
        {"name": "Supermercados 14 - Loja 02", "website": "https://site.supermercado14.com.br"},
    ]
    kept = filter_new_batch_items(_prepare_batch_items(items), set(), set())
    assert len(kept) == 1
    assert kept[0]["name"] == "Supermercados 14"


def test_place_id_ja_conhecido_e_filtrado():
    items = [
        {"place_id_candidate": "P1", "name": "Nova", "website": "https://nova.com.br"},
        {"place_id_candidate": "P2", "name": "Antiga", "website": "https://antiga.com.br"},
    ]
    kept = filter_new_batch_items(_prepare_batch_items(items), {"P1"}, set())
    assert len(kept) == 1
    assert kept[0]["name"] == "Antiga"


def test_place_id_repetido_no_proprio_lote_e_filtrado():
    items = [
        {"place_id_candidate": "P1", "name": "A", "website": "https://a.com.br"},
        {"place_id_candidate": "P1", "name": "B", "website": "https://b.com.br"},
    ]
    kept = filter_new_batch_items(_prepare_batch_items(items), set(), set())
    assert len(kept) == 1
    assert kept[0]["name"] == "A"


def test_dominio_ja_cadastrado_na_org_e_filtrado():
    items = [{"name": "Rede 14", "website": "https://site.supermercado14.com.br"}]
    kept = filter_new_batch_items(_prepare_batch_items(items), set(), {"site.supermercado14.com.br"})
    assert kept == []


def test_lotes_distintos_nao_se_filtram_entre_si():
    """Cha estado limpo: os ids/domínios vistos NÃO vazam entre chamadas."""
    items_a = [{"name": "A", "website": "https://a.com.br"}]
    items_b = [{"name": "A", "website": "https://a.com.br"}]
    filter_new_batch_items(_prepare_batch_items(items_a), set(), set())
    kept_b = filter_new_batch_items(_prepare_batch_items(items_b), set(), set())
    assert len(kept_b) == 1