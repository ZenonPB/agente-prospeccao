"""Orquestra technographics, intent e Opportunity Vector em dados já persistidos."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.db.models import Enrichment, EventOpportunityRow, Lead, LeadOpportunityRow, Person
from services.prospecting.intent_engine import build_opportunity_vector, extract_intent_signals, intent_score
from services.prospecting.intent_provider_registry import IntentProviderRegistry
from services.prospecting.phone_verification_service import verify_phone
from services.prospecting.technology_stack_provider import TechnologyStackProvider


class DataIntelligenceService:
    def __init__(self, db: Session, organization_id: Any):
        self.db = db
        self.organization_id = organization_id

    def analyze_lead(self, lead: Lead, *, persist: bool = False) -> dict[str, Any]:
        if str(lead.organization_id) != str(self.organization_id):
            raise ValueError("lead fora do workspace ativo")

        enrichment = (
            self.db.query(Enrichment)
            .filter(Enrichment.lead_id == lead.id)
            .order_by(Enrichment.created_at.desc())
            .first()
        )
        person = None
        if lead.primary_person_id:
            person = (
                self.db.query(Person)
                .filter(Person.organization_id == self.organization_id, Person.id == lead.primary_person_id)
                .first()
            )

        evidence: list[dict[str, Any]] = []
        if isinstance(lead.evidence, list):
            evidence.extend(item for item in lead.evidence if isinstance(item, dict))
        if isinstance(lead.discovery_provenance, list):
            evidence.extend(item for item in lead.discovery_provenance if isinstance(item, dict))
        elif isinstance(lead.discovery_provenance, dict):
            evidence.append({"source": "discovery", **lead.discovery_provenance})

        events = (
            self.db.query(EventOpportunityRow)
            .filter(
                EventOpportunityRow.organization_id == self.organization_id,
                EventOpportunityRow.lead_id == lead.id,
            )
            .order_by(EventOpportunityRow.event_date.asc())
            .limit(10)
            .all()
        )
        for event in events:
            evidence.append({
                "source": "event",
                "title": event.name,
                "event_type": event.event_type,
                "event_date": event.event_date.isoformat() if event.event_date else None,
                "confidence": 0.85,
                "observed_at": event.created_at.isoformat() if event.created_at else None,
            })

        technical_payloads = [
            enrichment.raw_technical_data if enrichment else None,
            lead.evidence,
            lead.discovery_provenance,
            lead.website,
            lead.company_linkedin_url,
            lead.instagram_url,
        ]
        tech_result = TechnologyStackProvider().detect(*technical_payloads)
        technologies = tech_result["technologies"]

        # O registry oferece telemetria por família/provider e o agregador geral
        # continua lendo toda evidência conhecida. Assim uma fonte legada com
        # `source=discovery` não perde sinais por não pertencer a uma família.
        intent_provider_result = IntentProviderRegistry().run(evidence)
        signals = extract_intent_signals(evidence)
        calculated_intent = intent_score(signals)

        existing_vector = lead.score_vector if isinstance(lead.score_vector, dict) else {}
        qualification = float(lead.qualification_score or 0)
        opportunities = (
            self.db.query(LeadOpportunityRow)
            .filter(
                LeadOpportunityRow.organization_id == self.organization_id,
                LeadOpportunityRow.lead_id == lead.id,
            )
            .all()
        )
        best_opportunity = max((float(row.score or 0) for row in opportunities), default=qualification)
        phone = verify_phone(person.phone if person else (lead.phone or lead.whatsapp))

        reachability = None
        if person:
            if person.routable:
                reachability = max(70.0, float(person.contact_confidence or 0))
            elif person.email or person.phone or person.linkedin_url:
                reachability = max(35.0, float(person.contact_confidence or 0))
        elif lead.email or lead.phone or lead.whatsapp:
            reachability = 35.0

        buying_power = existing_vector.get("buying_power")
        if buying_power is None:
            raw_business = enrichment.raw_business_data if enrichment and isinstance(enrichment.raw_business_data, dict) else {}
            capital = raw_business.get("capital_social") or raw_business.get("capital")
            try:
                capital_value = float(capital)
            except (TypeError, ValueError):
                capital_value = 0.0
            if capital_value > 0:
                buying_power = min(100, 35 + (capital_value ** 0.25) * 4)

        timing = existing_vector.get("timing")
        if timing is None and signals:
            timing = min(100, 45 + calculated_intent * 0.55)

        vector = build_opportunity_vector(
            icp_fit=existing_vector.get("icp_fit", best_opportunity),
            need=existing_vector.get("need", qualification),
            intent=calculated_intent if signals else existing_vector.get("intent"),
            buying_power=buying_power,
            reachability=reachability,
            timing=timing,
            commercial_fit=existing_vector.get("commercial_fit", best_opportunity),
        )

        result = {
            "lead_id": str(lead.id),
            "technologies": technologies,
            "technographics_provider": {
                "provider": tech_result["provider"],
                "status": tech_result["status"],
                "result_count": tech_result["result_count"],
                "cost_units": tech_result["cost_units"],
            },
            "intent_signals": signals,
            "intent_score": calculated_intent if signals else None,
            "intent_providers": intent_provider_result["providers"],
            "phone_verification": phone,
            "opportunity_vector": vector,
            "evidence_count": len(evidence),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        if persist:
            current_evidence_score = lead.evidence_score if isinstance(lead.evidence_score, dict) else {}
            lead.evidence_score = {
                **current_evidence_score,
                "phase4": {
                    "technologies": technologies,
                    "technographics_provider": result["technographics_provider"],
                    "intent_signals": signals,
                    "intent_score": result["intent_score"],
                    "intent_providers": result["intent_providers"],
                    "phone_verification": phone,
                    "formula_version": "intent-v2",
                    "generated_at": result["generated_at"],
                },
            }
            lead.score_vector = {**existing_vector, **vector}
            timestamps = lead.enrichment_timestamps if isinstance(lead.enrichment_timestamps, dict) else {}
            now_iso = result["generated_at"]
            lead.enrichment_timestamps = {
                **timestamps,
                "technographics": now_iso,
                "intent": now_iso,
            }
            self.db.add(lead)
            self.db.commit()
            self.db.refresh(lead)

        return result
