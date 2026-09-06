"""Pytest conftest — prepara sys.path e variáveis de ambiente mínimas.

Os testes são unitários (funções puras, sem banco). Algumas funções vivem em
módulos que instanciam Settings no import — por isso setamos variáveis dummy
antes de qualquer import do app.

Mapeamento de imports (igual ao runtime):
- `services.*`, `database.*`, `config.*` → workers (services/workers/src)
- `src.*` → API (services/api, parent de services/api/src)
"""
import os
import sys
import warnings
from pathlib import Path

# Starlette 1.3 tenta importar o pacote futuro `httpx2` apenas para emitir um
# aviso ao usar httpx 0.28. A aplicação declara httpx 0.28; este alias de teste
# mantém o TestClient funcional sem instalar uma dependência não declarada.
try:
    import httpx

    sys.modules.setdefault("httpx2", httpx)
except ImportError:
    pass


def pytest_configure(config):
    """Mantém compatibilidade transitória com o TestClient do Starlette.

    O ambiente suportado ainda usa httpx 0.28; versões novas do Starlette
    sinalizam essa combinação durante a coleta. O filtro é específico para a
    categoria e módulo upstream, sem esconder depreciações da aplicação.
    """
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        message=r".*asyncio\.iscoroutinefunction.*",
        module=r"asyncio\.coroutines",
    )
    try:
        from starlette.exceptions import StarletteDeprecationWarning
    except ImportError:
        return
    warnings.filterwarnings(
        "ignore",
        category=StarletteDeprecationWarning,
        module=r"starlette\.testclient",
    )

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKERS_SRC = REPO_ROOT / "services" / "workers" / "src"
API_PARENT = REPO_ROOT / "services" / "api"

# Ambiente mínimo para os Settings (workers e api) não quebrarem no import.
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/test")
os.environ.setdefault("POSTGRES_USER", "user")
os.environ.setdefault("POSTGRES_PASSWORD", "pass")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("PGADMIN_EMAIL", "admin@test.local")
os.environ.setdefault("PGADMIN_PASSWORD", "admin")
os.environ.setdefault("GROQ_API_KEY", "test")
os.environ.setdefault("GOOGLE_API_KEY", "test")
os.environ.setdefault("HUNTER_API_KEY", "")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("SECRETS_ENCRYPTION_KEY", "")
os.environ.setdefault("ENVIRONMENT", "test")

# API_PARENT primeiro (sys.path[0]): `import main` e `import src.*` resolvem a
# API. `services.*`/`database.*`/`config.*` continuam resolvendo os workers
# (pacote regular `services` em workers/src tem precedência sobre o namespace
# package da API).
for p in (WORKERS_SRC, API_PARENT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
