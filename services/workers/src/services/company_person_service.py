"""Serviço para gestão do Modelo de 3 Entidades (Company, Person, Lead/Oportunidade).

Garante que empresas e pessoas sejam unificadas por organização, reutilizando
registros entre campanhas e oportunidades sem duplicação.
"""
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from database.models import Company, Person, Lead, Contact
from services.domain_utils import normalize_domain

logger = logging.getLogger(__name__)


class CompanyPersonService:
    @staticmethod
    def get_or_create_company(
        db: Session,
        organization_id: Any,
        data: Dict[str, Any],
    ) -> Optional[Company]:
        """Busca ou cria uma empresa (Company) dentro da organização.

        Match via CNPJ ou domínio normalizado ou nome da empresa.
        """
        if not organization_id:
            return None

        cnpj = data.get("cnpj")
        website = data.get("website")
        domain = normalize_domain(website) if website else data.get("normalized_domain")
        company_name = data.get("company_name") or data.get("name")

        if not company_name and not cnpj and not domain:
            return None

        query = db.query(Company).filter(Company.organization_id == organization_id)
        existing: Optional[Company] = None

        if cnpj:
            existing = query.filter(Company.cnpj == cnpj).first()
        if not existing and domain:
            existing = query.filter(Company.normalized_domain == domain).first()
        if not existing and company_name:
            existing = query.filter(Company.company_name == company_name).first()

        if existing:
            # Atualiza campos que vieram com novidades
            updated = False
            if cnpj and not existing.cnpj:
                existing.cnpj = cnpj
                updated = True
            if website and not existing.website:
                existing.website = website
                existing.normalized_domain = domain
                updated = True
            if data.get("phone") and not existing.phone:
                existing.phone = data.get("phone")
                updated = True
            if data.get("address") and not existing.address:
                existing.address = data.get("address")
                updated = True
            if data.get("company_linkedin_url") and not existing.company_linkedin_url:
                existing.company_linkedin_url = data.get("company_linkedin_url")
                updated = True
            if data.get("instagram_url") and not existing.instagram_url:
                existing.instagram_url = data.get("instagram_url")
                updated = True
            if data.get("google_rating") and not existing.google_rating:
                existing.google_rating = data.get("google_rating")
                existing.google_rating_count = data.get("google_rating_count")
                existing.google_maps_uri = data.get("google_maps_uri")
                updated = True

            if updated:
                db.flush()
            return existing

        # Cria nova empresa
        company = Company(
            organization_id=organization_id,
            company_name=company_name or "Empresa sem nome",
            name=data.get("name") or company_name,
            cnpj=cnpj,
            website=website,
            normalized_domain=domain,
            phone=data.get("phone"),
            address=data.get("address"),
            city=data.get("city"),
            state=data.get("state"),
            country=data.get("country", "Brasil"),
            category=data.get("category"),
            google_rating=data.get("google_rating"),
            google_rating_count=data.get("google_rating_count"),
            google_maps_uri=data.get("google_maps_uri"),
            company_linkedin_url=data.get("company_linkedin_url"),
            instagram_url=data.get("instagram_url"),
            raw_data=data.get("raw_data"),
        )
        db.add(company)
        db.flush()
        logger.info("Nova Company criada no modelo 3 Entidades: %s (org=%s)", company.company_name, organization_id)
        return company

    @staticmethod
    def get_or_create_person(
        db: Session,
        organization_id: Any,
        company_id: Optional[Any],
        contact_data: Dict[str, Any],
    ) -> Optional[Person]:
        """Busca ou cria um decisor/pessoa (Person) associado à empresa/org."""
        if not organization_id:
            return None

        name = contact_data.get("name")
        email = contact_data.get("email")
        cpf = contact_data.get("document_cpf")

        if not name and not email and not cpf:
            return None

        query = db.query(Person).filter(Person.organization_id == organization_id)
        if company_id:
            query = query.filter(Person.company_id == company_id)

        existing: Optional[Person] = None
        if cpf:
            existing = query.filter(Person.document_cpf == cpf).first()
        if not existing and email:
            existing = query.filter(Person.email == email).first()
        if not existing and name:
            existing = query.filter(Person.name == name).first()

        if existing:
            # Atualiza dados novos
            updated = False
            if email and not existing.email:
                existing.email = email
                updated = True
            if contact_data.get("phone") and not existing.phone:
                existing.phone = contact_data.get("phone")
                updated = True
            if contact_data.get("linkedin_url") and not existing.linkedin_url:
                existing.linkedin_url = contact_data.get("linkedin_url")
                existing.linkedin_confidence = contact_data.get("linkedin_confidence", 0)
                updated = True
            if contact_data.get("email_verified") and not existing.email_verified:
                existing.email_verified = True
                existing.email_verified_at = contact_data.get("email_verified_at")
                updated = True
            if updated:
                db.flush()
            return existing

        person = Person(
            organization_id=organization_id,
            company_id=company_id,
            name=name or "Decisor",
            role=contact_data.get("role"),
            role_label=contact_data.get("role_label"),
            email=email,
            phone=contact_data.get("phone"),
            document_cpf=cpf,
            confidence=contact_data.get("confidence", 0),
            email_verified=contact_data.get("email_verified", False),
            email_verified_at=contact_data.get("email_verified_at"),
            linkedin_url=contact_data.get("linkedin_url"),
            linkedin_confidence=contact_data.get("linkedin_confidence", 0),
            source=contact_data.get("source", "contact_enrichment"),
            raw_data=contact_data.get("raw_data"),
        )
        db.add(person)
        db.flush()
        logger.info("Nova Person criada no modelo 3 Entidades: %s (org=%s)", person.name, organization_id)
        return person

    @staticmethod
    def sync_lead_entities(db: Session, lead: Lead) -> None:
        """Sincroniza e vincula os registros de Company e Person para um Lead."""
        if not lead or not lead.organization_id:
            return

        # Sincroniza a empresa
        lead_data = {
            "name": lead.name,
            "company_name": lead.company_name,
            "cnpj": lead.cnpj,
            "website": lead.website,
            "normalized_domain": lead.normalized_domain,
            "phone": lead.phone,
            "address": lead.address,
            "city": lead.city,
            "state": lead.state,
            "country": lead.country,
            "category": lead.category,
            "google_rating": lead.google_rating,
            "google_rating_count": lead.google_rating_count,
            "google_maps_uri": lead.google_maps_uri,
            "company_linkedin_url": lead.company_linkedin_url,
            "instagram_url": lead.instagram_url,
        }
        company = CompanyPersonService.get_or_create_company(db, lead.organization_id, lead_data)
        if company:
            lead.company_id = company.id

        # Sincroniza as pessoas (contacts)
        primary_person_id = None
        for contact in lead.contacts:
            c_data = {
                "name": contact.name,
                "role": contact.role,
                "role_label": contact.role_label,
                "email": contact.email,
                "phone": contact.phone,
                "document_cpf": contact.document_cpf,
                "confidence": contact.confidence,
                "email_verified": contact.email_verified,
                "email_verified_at": contact.email_verified_at,
                "linkedin_url": contact.linkedin_url,
                "linkedin_confidence": contact.linkedin_confidence,
                "source": contact.source,
                "raw_data": contact.raw_data,
            }
            person = CompanyPersonService.get_or_create_person(
                db, lead.organization_id, company.id if company else None, c_data
            )
            if person and (contact.is_primary or not primary_person_id):
                primary_person_id = person.id

        if primary_person_id:
            lead.primary_person_id = primary_person_id

        db.flush()
