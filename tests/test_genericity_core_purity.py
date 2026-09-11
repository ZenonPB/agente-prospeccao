"""Pureza do core: nenhuma capability genérica conhece uma vertical pelo nome.

Este é o lado estático do Genericity Test Harness (Task 2). Ele funciona como
ratchet: as violações existentes estão registradas com a Task do roadmap que as
remove, o número não pode subir e a lista não pode ficar obsoleta.
"""
import ast

import pytest

from genericity.core_purity import (
    FORBIDDEN_IDENTITIES,
    KIND_BRANCH,
    KIND_LITERAL,
    KNOWN_VIOLATIONS,
    allowed_counts,
    core_modules,
    counts_by_module_kind,
    new_violations,
    scan_core,
    scan_module,
    stale_baseline,
)


def test_core_modules_encontrados():
    modules = core_modules()
    names = {path.name for path in modules}
    # Sanidade: o scan precisa realmente estar olhando o core.
    assert "offer_matcher.py" in names
    assert "discovery_executor.py" in names
    assert "discovery_planner_service.py" in names
    # A camada de configuração declara chaves por função — não é core.
    assert "default_profiles.py" not in names


def test_nenhuma_violacao_nova_no_core():
    """Falha quando uma capability nova acopla o core a uma vertical."""
    novos = new_violations(counts_by_module_kind(scan_core()), allowed_counts())
    assert not novos, (
        "Acoplamento a vertical introduzido no core "
        f"(além do baseline conhecido): {novos}. "
        "Mova a decisão para o OfferProfile em vez de ramificar por domínio."
    )


def test_baseline_de_violacoes_nao_esta_obsoleto():
    """Falha quando uma violação do baseline foi corrigida sem atualizar a lista.

    Garante que ``KNOWN_VIOLATIONS`` encolhe junto com as Tasks 5 e 6, em vez
    de virar uma lista permanente de desculpas.
    """
    obsoletos = stale_baseline(counts_by_module_kind(scan_core()), allowed_counts())
    assert not obsoletos, (
        "Baseline desatualizado (declarado, encontrado): "
        f"{obsoletos}. Reduza o valor em KNOWN_VIOLATIONS."
    )


def test_baseline_documenta_a_task_que_remove_cada_violacao():
    for key, (count, task) in KNOWN_VIOLATIONS.items():
        assert count > 0, f"entrada sem contagem: {key}"
        assert task.startswith("Task "), (
            f"violação {key} sem Task do roadmap associada: {task!r}"
        )


@pytest.mark.parametrize("module_path", core_modules(), ids=lambda p: p.name)
def test_modulo_do_core_sem_violacao_fora_do_baseline(module_path):
    """Visão por módulo — aponta o arquivo exato ao falhar."""
    found = counts_by_module_kind(scan_module(module_path))
    allowed = allowed_counts()
    for key, count in found.items():
        assert count <= allowed.get(key, 0), (
            f"{key[0]} tem {count} violação(ões) de {key[1]}, "
            f"baseline permite {allowed.get(key, 0)}"
        )


# --- Testes do próprio detector (um harness que não detecta nada é inútil) ---

def _violations_from_source(tmp_path, source: str):
    path = tmp_path / "fake_core.py"
    path.write_text(source, encoding="utf-8")
    # scan_module usa caminho relativo a WORKERS_SRC; testamos o AST direto.
    tree = ast.parse(source)
    assert tree is not None
    return path


def test_detector_pega_branch_por_identidade(tmp_path, monkeypatch):
    import genericity.core_purity as purity

    source = (
        '"""doc."""\n'
        "def plan(profile):\n"
        "    profile_key = profile['profile_key']\n"
        "    if profile_key == 'trophies':\n"
        "        return 1\n"
        "    return 0\n"
    )
    path = tmp_path / "fake.py"
    path.write_text(source, encoding="utf-8")
    monkeypatch.setattr(purity, "WORKERS_SRC", tmp_path)

    kinds = {v.kind for v in purity.scan_module(path)}
    assert KIND_BRANCH in kinds
    assert KIND_LITERAL in kinds


def test_detector_ignora_docstring_e_nome_de_campo(tmp_path, monkeypatch):
    import genericity.core_purity as purity

    source = (
        '"""Serviço genérico; exemplo histórico: trophies e web_erp."""\n'
        "def filtra(rows, offer_key):\n"
        "    return [r for r in rows if r['offer_key'] == offer_key]\n"
    )
    path = tmp_path / "fake.py"
    path.write_text(source, encoding="utf-8")
    monkeypatch.setattr(purity, "WORKERS_SRC", tmp_path)

    assert purity.scan_module(path) == []


def test_detector_ignora_core_generico(tmp_path, monkeypatch):
    import genericity.core_purity as purity

    source = (
        "def plan(profile):\n"
        "    providers = (profile.discovery or {}).get('providers') or []\n"
        "    return [{'type': name} for name in providers]\n"
    )
    path = tmp_path / "fake.py"
    path.write_text(source, encoding="utf-8")
    monkeypatch.setattr(purity, "WORKERS_SRC", tmp_path)

    assert purity.scan_module(path) == []


def test_identidades_proibidas_cobrem_as_tres_verticais():
    assert {"trophies", "web_erp", "mechanical_project"} <= FORBIDDEN_IDENTITIES


# --- Testes do ratchet em si ---

def test_ratchet_acusa_violacao_nova():
    found = {("a.py", KIND_LITERAL): 2}
    assert new_violations(found, {("a.py", KIND_LITERAL): 1}) == {("a.py", KIND_LITERAL): 2}
    assert new_violations(found, {("a.py", KIND_LITERAL): 2}) == {}


def test_ratchet_acusa_modulo_sem_baseline():
    assert new_violations({("novo.py", KIND_BRANCH): 1}, {}) == {("novo.py", KIND_BRANCH): 1}


def test_ratchet_acusa_baseline_obsoleto_quando_violacao_e_corrigida():
    allowed = {("a.py", KIND_LITERAL): 4}
    # Corrigiu 2 das 4 -> a lista precisa cair para 2.
    assert stale_baseline({("a.py", KIND_LITERAL): 2}, allowed) == {("a.py", KIND_LITERAL): (4, 2)}
    # Corrigiu todas -> entrada deve sair da lista.
    assert stale_baseline({}, allowed) == {("a.py", KIND_LITERAL): (4, 0)}
    # Em dia -> nada obsoleto.
    assert stale_baseline({("a.py", KIND_LITERAL): 4}, allowed) == {}


def test_allowed_counts_espelha_o_baseline():
    assert allowed_counts() == {key: count for key, (count, _) in KNOWN_VIOLATIONS.items()}
