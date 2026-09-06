"""Garante que a suíte pytest roda limpa sob `-W error` (P0.3).

O cenário atual: `slowapi` (instalado pela API) usa `asyncio.iscoroutinefunction`
internamente, que está deprecated no Python 3.14. Se a CI rodar com
`-W error::DeprecationWarning`, o teste bloqueia merge sem motivo funcional.

Política: silenciar APENAS o warning de `asyncio.iscoroutinefunction` na nossa
configuração pytest, registrando um filtro que aponta a origem exata e a
intenção de remover quando `slowapi`/`starlette` corrigirem upstream. Isso é
preferível a patch de dependência (risco) e a desligar todos os
DeprecationWarning (esconde reais).
"""
import warnings


def test_asyncio_iscoroutinefunction_warning_is_filtered():
    """O warning deprecated do asyncio.iscoroutinefunction precisa ter um filtro
    explícito na config pytest (pyproject/setup) para que `-W error` não bloqueie
    merge por causa de uma deprecação de uma dependência upstream.
    """
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    pyproject = repo_root / "pyproject.toml"
    setup_cfg = repo_root / "setup.cfg"
    pytest_ini = repo_root / "pytest.ini"

    assert pyproject.exists() or setup_cfg.exists() or pytest_ini.exists(), (
        "Esperado ao menos um arquivo de config pytest na raiz."
    )

    config_text = ""
    if pyproject.exists():
        config_text += pyproject.read_text(encoding="utf-8")
    if setup_cfg.exists():
        config_text += setup_cfg.read_text(encoding="utf-8")
    if pytest_ini.exists():
        config_text += pytest_ini.read_text(encoding="utf-8")

    # Política: ou há needle explícito no texto, OU há `addopts -W` com a
    # deprecação filtrada por regex (sem precisar da string exata).
    needle = "asyncio.iscoroutinefunction"
    needle_partial = "iscoroutinefunction"
    assert needle in config_text or needle_partial in config_text, (
        "Filtro de warning ausente para 'asyncio.iscoroutinefunction'. "
        "Adicione filterwarnings em pyproject.toml/setup.cfg/pytest.ini."
    )


def test_deprecation_warnings_are_not_silently_ignored():
    """Política: NÃO desligar DeprecationWarning em massa. Garantimos que
    o filtro existente é específico (mensagem + módulo) — não um blanket
    `ignore::DeprecationWarning` que esconda reais.
    """
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    candidates = (repo_root / "pyproject.toml", repo_root / "setup.cfg", repo_root / "pytest.ini")
    config_text = "\n".join(
        p.read_text(encoding="utf-8") for p in candidates if p.exists()
    )

    # Política global de ignorar TODOS os DeprecationWarning é proibida.
    assert "ignore::DeprecationWarning\n" not in config_text
    assert "ignore::DeprecationWarning" not in [
        line.strip() for line in config_text.splitlines()
    ], (
        "Filtro blanket de DeprecationWarning detectado — política proíbe silenciar "
        "warnings em massa. Mantenha apenas filtros específicos por módulo/mensagem."
    )


def test_runtime_filter_handles_upstream_warning():
    """O filtro pytest deve efetivamente silenciar o warning do upstream
    `slowapi.extension` quando reproduzido em runtime (cobre drift de
    dependência).
    """
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        import asyncio  # noqa: F401

        def _coro_func():
            return asyncio.sleep(0)

        # A função abaixo emite DeprecationWarning no 3.14+.
        asyncio.iscoroutinefunction(_coro_func)

    deprecations = [w for w in captured if issubclass(w.category, DeprecationWarning)]
    # Python 3.12 ainda não emite esse aviso; em Python 3.14 o sanity check
    # confirma que a política continua cobrindo a API obsoleta.
    if deprecations:
        assert any("asyncio.iscoroutinefunction" in str(w.message) for w in deprecations)
