"""Smoke test do roteamento de playbooks.

A API real de playbooks é simples CRUD que valida contra o `Organization`.
Aqui garantimos só que o módulo importa e expõe a forma esperada (sem DB)."""

from src.routes import playbooks as playbooks_module


def test_playbooks_router_exposes_endpoints():
    paths = {route.path for route in playbooks_module.router.routes}
    assert "/playbooks" in paths
    # PATCH/DELETE devem usar path param {playbook_id}.
    assert any(p.endswith("{playbook_id}") for p in paths)


def test_playbook_dict_formata_autor_e_tags():
    """Smoke: _playbook_dict lida com autor None e tags vazias."""
    class FakeAuthor:
        name = "Ana"
        email = "ana@x.com"

    class FakePlaybook:
        id = "pb-1"
        organization_id = "org-1"
        author_id = "user-1"
        author = FakeAuthor()
        vertical = "academias"
        subject = "S"
        body = "B"
        tags = ["a", "b"]
        created_at = None
        updated_at = None

    out = playbooks_module._playbook_dict(FakePlaybook())
    assert out["author_name"] == "Ana"
    assert out["tags"] == ["a", "b"]
    assert out["subject"] == "S"
