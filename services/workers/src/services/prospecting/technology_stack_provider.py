"""Provider passivo de technographics sobre HTML/headers/metadados já coletados."""
from __future__ import annotations

from typing import Any

from services.prospecting.intent_engine import detect_technologies


class TechnologyStackProvider:
    name = "passive_technographics"

    def detect(self, *payloads: Any) -> dict[str, Any]:
        technologies = detect_technologies(*payloads)
        return {
            "provider": self.name,
            "status": "success" if technologies else "empty",
            "technologies": technologies,
            "result_count": len(technologies),
            "cost_units": 0,
        }
