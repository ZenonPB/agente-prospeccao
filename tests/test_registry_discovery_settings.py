"""Settings do Registry discovery + shadow (parte 1: workers)."""
import os

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/test")
os.environ.setdefault("GROQ_API_KEY", "test")
os.environ.setdefault("GOOGLE_API_KEY", "test")


def test_workers_settings_tem_flags_do_registry_discovery():
    from config.settings import settings

    assert settings.REGISTRY_DISCOVERY_ENABLED is False
    assert settings.REGISTRY_SHADOW_MODE is False


def test_api_settings_tem_flags_do_registry_discovery():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path("services/api/src")))
    from src.config.settings import settings as api_settings  # noqa: E402

    assert api_settings.REGISTRY_DISCOVERY_ENABLED is False
    assert api_settings.REGISTRY_SHADOW_MODE is False
