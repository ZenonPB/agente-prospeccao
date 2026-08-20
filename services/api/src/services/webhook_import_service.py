"""Serviço de importação de leads via webhook (para automações n8n, Make, Zapier, Apps Script).

Recebe um JSON-array de leads já estruturado, valida, deduplica por organização
e cria os leads no banco. Protegido por segredo compartilhado (X-Webhook-Secret).
"""
import hashlib
import logging
import os
import sys
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_

# Garante que `services.*` dos workers resolva independente da ordem de import
_workers_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "workers", "src")
if _workers_path not in sys.path:
    sys.path.insert(0, _workers_path)

from src.db.models import Lead, LeadStatus, Campaign, Contact, ContactRole
from services.domain_utils import normalize_domain, is_social_domain

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ["name"]
OPTIONAL_FIELDS = [
    "website", "phone", "whatsapp", "email", "city", "state",
    "address", "cnpj", "category", "contact_name", "linkedin", "instagram"
]

# Aliases de cabeçalho compatíveis com CSV import
HEADER_ALIASES = {
    "name": ["name", "nome", "empresa", "company_name", "razao_social", "nome_fantasia"],
    "website": ["website", "site", "url", "web_site", "domain", "dominio"],
    "phone": ["phone", "telefone", "tel", "celular", "phone_number"],
    "whatsapp": ["whatsapp", "wpp", "zap", "whats"],
    "email": ["email", "e-mail", "mail", "email_contato", "email_principal"],
    "city": ["city", "cidade", "municipio"],
    "state": ["state", "uf", "estado"],
    "address": ["address", "endereco", "logradouro", "rua"],
    "cnpj": ["cnpj", "documento", "tax_id"],
    "category": ["category", "categoria", "ramo", "segmento", "nicho"],
    "contact_name": ["contact_name", "contato", "nome_contato", "decisor", "responsavel"],
    "linkedin": ["linkedin", "perfil_linkedin", "linkedin_url"],
    "instagram": ["instagram", "instagram_url", "perfil_instagram", "ig"],
}


def normalize_header(header: str) -> str:
    cleaned = header.strip().lower().replace(" ", "_").replace("-", "_")
    for field, aliases in HEADER_ALIASES.items():
        if cleaned in aliases:
            return field
    for field, aliases in HEADER_ALIASES.items():
        if any(alias in cleaned for alias in aliases):
            return field
    return cleaned


def clean_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url
    return url


def normalize_import_website(url: Optional[str]) -> Optional[str]:
    """Limpa a URL e a anula se apontar para rede social/ferramenta/marketplace."""
    website = clean_url(url)
    if is_social_domain(website):
        return None
    return website


def clean_cnpj(cnpj: Optional[str]) -> Optional[str]:
    if not cnpj:
        return None
    digits = "".join(c for c in cnpj if c.isdigit())
    return digits if len(digits) == 14 else None


def generate_place_id(name: str, website: Optional[str], cnpj: Optional[str]) -> str:
    """Gera place_id sintético determinístico para deduplicação."""
    base = f"{name.lower()}|{website or ''}|{cnpj or ''}"
    return f"webhook_{hashlib.sha256(base.encode()).hexdigest()[:24]}"


def import_leads_from_webhook(
    db: Session,
    campaign_id: str,
    leads_data: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Importa empresas a partir de um array de dicionários.

    A campanha é resolvida pelo ID e o destino é a organização dona da
    campanha (o webhook é autenticado por segredo compartilhado, não por
    usuário). Retorna relatório estruturado com contagens e detalhes.
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise ValueError("Campanha não encontrada")

    organization_id = str(campaign.organization_id)

    total_rows = len(leads_data)
    imported_count = 0
    duplicate_count = 0
    error_count = 0
    errors: List[Dict[str, Any]] = []

    for idx, raw_lead in enumerate(leads_data):
        try:
            # Normaliza chaves
            normalized = {}
            for k, v in raw_lead.items():
                normalized[normalize_header(k)] = v

            # Validação mínima
            name = (normalized.get("name") or "").strip()
            if not name:
                error_count += 1
                errors.append({
                    "row": idx + 1,
                    "field": "name",
                    "message": "Informe o nome da empresa",
                })
                continue

            website = normalize_import_website(normalized.get("website"))
            phone = normalized.get("phone")
            whatsapp = normalized.get("whatsapp")
            email = normalized.get("email")
            city = normalized.get("city") or campaign.target_city
            state = normalized.get("state") or campaign.target_state
            address = normalized.get("address")
            cnpj = clean_cnpj(normalized.get("cnpj"))
            category = normalized.get("category")
            contact_name = normalized.get("contact_name")
            linkedin = normalized.get("linkedin")
            instagram = normalized.get("instagram")
            normalized_domain = normalize_domain(website)
            place_id = generate_place_id(name, website, cnpj)

            # Deduplicação por (organization_id, place_id/website/cnpj) — cada
            # condição só é aplicada quando o valor existe (CNPJ/site nulo é
            # comum em importação e não deve excluir a checagem por place_id).
            dedup_conditions = [Lead.place_id == place_id]
            if website:
                dedup_conditions.append(Lead.website == website)
            if cnpj:
                dedup_conditions.append(Lead.cnpj == cnpj)
            existing = db.query(Lead).filter(
                Lead.organization_id == organization_id,
                or_(*dedup_conditions),
            ).first()

            if existing:
                duplicate_count += 1
                errors.append({
                    "row": idx + 1,
                    "field": "duplicate",
                    "message": f"Empresa já cadastrada: {existing.company_name or existing.name}",
                    "existing_lead_id": str(existing.id),
                })
                continue

            lead = Lead(
                organization_id=organization_id,
                campaign_id=campaign_id,
                name=name,
                company_name=name,
                place_id=place_id,
                website=website,
                normalized_domain=normalized_domain,
                phone=phone,
                whatsapp=whatsapp,
                email=email,
                city=city,
                state=state,
                address=address,
                cnpj=cnpj,
                category=category,
                instagram_url=instagram,
                status=LeadStatus.NOVO,
            )
            db.add(lead)
            db.flush()

            # Sincroniza o modelo de 3 entidades (Company/Person) como o CSV
            # import faz — falha de sincronização nunca derruba a importação.
            try:
                from services.company_person_service import CompanyPersonService
                CompanyPersonService.sync_lead_entities(db, lead)
            except Exception:  # noqa: BLE001 — sync é best-effort
                logger.warning(
                    "Webhook: falha ao sincronizar 3 entidades do lead %s (%s)",
                    lead.id, name,
                )

            # Cria o contato apenas com nome válido (`contacts.name` é NOT
            # NULL) — e-mail/telefone sem decisor não vira contato fantasma.
            if contact_name:
                contact = Contact(
                    lead_id=lead.id,
                    name=contact_name,
                    email=email,
                    phone=phone or whatsapp,
                    linkedin_url=linkedin,
                    role=ContactRole.OUTRO,
                    confidence=50 if (email or phone) else 20,
                    source="webhook",
                )
                db.add(contact)

            imported_count += 1

        except Exception as e:
            error_count += 1
            logger.exception("Erro ao importar linha %d", idx + 1)
            errors.append({
                "row": idx + 1,
                "field": "unknown",
                "message": str(e),
            })

    db.commit()

    return {
        "total_rows": total_rows,
        "imported_count": imported_count,
        "duplicate_count": duplicate_count,
        "error_count": error_count,
        "errors": errors[:50],  # limita retorno
    }