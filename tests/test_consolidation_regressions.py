"""Regressões dos contratos operacionais da consolidação."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))


def test_discovery_executor_applies_global_budget():
    from services.prospecting.discovery_executor import DiscoveryExecutor, DiscoveryProviderRegistry, _StubProvider

    registry = DiscoveryProviderRegistry()
    registry.register(_StubProvider("a", results=[{"name": "A1"}, {"name": "A2"}]))
    registry.register(_StubProvider("b", results=[{"name": "B1"}, {"name": "B2"}]))
    result = asyncio.run(DiscoveryExecutor(registry).execute_async({
        "max_results": 3,
        "providers": [{"type": "a"}, {"type": "b"}],
    }))

    assert result["unique_count"] == 3
    assert sum(result["budget_used"].values()) == 3


def test_event_registry_without_endpoint_does_not_enable_production_provider():
    from services.prospecting.event_discovery import build_default_event_registry

    assert build_default_event_registry("").list_keys() == []