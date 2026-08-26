"""Smoke test de importação — a API e os workers sobem sem erro (boot check).

Sem banco: apenas valida que todos os módulos importam e que as rotas estão
registradas. Requer as dependências instaladas (requirements-dev.txt).

O `main.py` da API é carregado por caminho explícito (services/api/main.py)
porque `services/workers/src/main.py` existe e criaria colisão de nome em
`import main`.
"""
import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
API_MAIN = REPO_ROOT / "services" / "api" / "main.py"


def _all_paths(app) -> set[str]:
    """Coleta paths de rotas, descendo em `_IncludedRouter.original_router`."""
    paths: set[str] = set()
    stack = list(getattr(app, "routes", []))
    while stack:
        route = stack.pop()
        if hasattr(route, "path"):
            paths.add(route.path)
        inner = getattr(route, "original_router", None)
        if inner is not None:
            stack.extend(getattr(inner, "routes", []))
        stack.extend(getattr(route, "routes", []) or [])
    return paths


def test_api_app_importa():
    sys.path.insert(0, str(REPO_ROOT / "services" / "api"))
    spec = importlib.util.spec_from_file_location("api_main", str(API_MAIN))
    main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main)

    app = main.app
    assert app.title == "Prospect.ai API"
    paths = _all_paths(app)
    # Rotas internas dos routers incluídos vêm sem o prefixo `/api`.
    assert "/api/leads" in paths or "/leads" in paths
    assert "/api/campaigns" in paths or "/campaigns" in paths
    assert "/api/pipeline/start" in paths or "/pipeline/start" in paths
    assert "/api/analytics/overview" in paths or "/analytics/overview" in paths
    assert "/api/analytics/consultants/{user_id}" in paths or "/analytics/consultants/{user_id}" in paths
    assert "/api/analytics/consultants/{user_id}/activity" in paths or "/analytics/consultants/{user_id}/activity" in paths
    assert "/api/webhooks/email/inbound" in paths or "/webhooks/email/inbound" in paths
    assert "/health" in paths


def test_workers_services_importam():
    importlib.import_module("services.scoring_service")
    importlib.import_module("services.places_service")
    importlib.import_module("services.enrichment_orchestrator")
    importlib.import_module("services.contact_enrichment_service")
    importlib.import_module("services.domain_utils")
