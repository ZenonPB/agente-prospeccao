import csv
import io
import hashlib
import os
import sys
from typing import List, Dict, Any, Optional, Tuple

# Garante que `services.*` dos workers resolva independente da ordem de import
# dos routers (padrão do repo; ver routes/campaigns.py).
_workers_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "workers", "src")
if _workers_path not in sys.path:
    sys.path.insert(0, _workers_path)

from sqlalchemy.orm import Session
from sqlalchemy import or_

from src.db.models import Lead, LeadStatus, Campaign, Contact, ContactRole
from services.domain_utils import normalize_domain, is_social_domain, is_instagram_url, extract_instagram_url


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
    # Checagem secundária por contaminação / palavras contidas
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
    """Limpa a URL e a anula se apontar para rede social/ferramenta/marketplace.

    Site que aponta p/ rede social (Instagram), ferramenta (Canva/WhatsApp) ou
    marketplace NÃO é site próprio. Anular mantém o lead como "sem site" (score
    business em campanhas web) e evita enriquecimento técnico errado — mesmo
    comportamento de places_service.search_places (coleta).
    """
    website = clean_url(url)
    if is_social_domain(website):
        return None
    return website


def clean_cnpj(cnpj: Optional[str]) -> Optional[str]:
    if not cnpj:
        return None
    digits = "".join(c for c in cnpj if c.isdigit())
    return digits if len(digits) == 14 else None


def generate_csv_place_id(name: str, city: Optional[str], website: Optional[str]) -> str:
    """Place_id determinístico baseado em nome+cidade+domínio (não usa linha do
    arquivo, para re-importação de arquivos reordenados gerar o mesmo id)."""
    raw = f"{name.lower().strip()}|{(city or '').lower().strip()}|{(website or '').lower().strip()}"
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]
    return f"csv_{digest}"


class CsvImportService:
    @staticmethod
    def parse_and_import(
        db: Session,
        campaign: Campaign,
        file_content: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Parseia o conteúdo textual de um CSV e cria os leads correspondentes na campanha."""
        # Detecta delimitador (vírgula ou ponto-e-vírgula)
        sample = file_content[:2048]
        delimiter = ";" if sample.count(";") > sample.count(",") else ","

        reader = csv.reader(io.StringIO(file_content), delimiter=delimiter)
        try:
            raw_headers = next(reader)
        except StopIteration:
            return {
                "total_rows": 0,
                "imported_count": 0,
                "duplicate_count": 0,
                "error_count": 1,
                "errors": [{"line": 0, "reason": "Arquivo CSV vazio ou sem cabeçalho."}],
            }

        headers = [normalize_header(h) for h in raw_headers]
        
        if "name" not in headers:
            return {
                "total_rows": 0,
                "imported_count": 0,
                "duplicate_count": 0,
                "error_count": 1,
                "errors": [{"line": 1, "reason": "Cabeçalho obrigatório 'nome' ou 'empresa' (name) não encontrado."}],
            }

        # Busca websites, domínios e CNPJs existentes na organização para deduplicação rápida
        existing_leads = db.query(Lead.website, Lead.normalized_domain, Lead.cnpj, Lead.place_id).filter(
            Lead.organization_id == campaign.organization_id
        ).all()

        existing_websites = {l.website.strip().lower() for l in existing_leads if l.website}
        existing_domains = {l.normalized_domain for l in existing_leads if l.normalized_domain}
        existing_cnpjs = {l.cnpj for l in existing_leads if l.cnpj}
        existing_place_ids = {l.place_id for l in existing_leads if l.place_id}

        imported_leads: List[Lead] = []
        imported_contacts: List[Contact] = []
        errors: List[Dict[str, Any]] = []
        duplicate_count = 0
        line_num = 1

        for row in reader:
            line_num += 1
            if not row or not any(field.strip() for field in row):
                continue  # Pula linhas vazias

            row_data = {}
            for idx, val in enumerate(row):
                if idx < len(headers):
                    row_data[headers[idx]] = val.strip()

            name = row_data.get("name")
            if not name:
                errors.append({"line": line_num, "reason": "Nome da empresa/lead ausente."})
                continue

            website = normalize_import_website(row_data.get("website"))
            normalized_domain = normalize_domain(website)
            cnpj = clean_cnpj(row_data.get("cnpj"))
            phone = row_data.get("phone")
            whatsapp = row_data.get("whatsapp") or phone
            email = row_data.get("email")
            contact_name = row_data.get("contact_name")
            linkedin = row_data.get("linkedin")
            # Instagram: prioriza coluna própria; cai pro website se for IG; ou
            # extrai por regex de qualquer texto livre da linha.
            instagram_url = (
                row_data.get("instagram")
                or (extract_instagram_url(website) if website else None)
                or extract_instagram_url(name)
            )
            city = row_data.get("city") or campaign.target_city
            state = row_data.get("state") or campaign.target_state
            address = row_data.get("address")
            category = row_data.get("category") or campaign.target_segment

            # Checagem de duplicata na org por Website/Domínio/CNPJ
            if website and website.lower() in existing_websites:
                duplicate_count += 1
                continue

            if normalized_domain and normalized_domain in existing_domains:
                duplicate_count += 1
                continue

            if cnpj and cnpj in existing_cnpjs:
                duplicate_count += 1
                continue

            place_id = generate_csv_place_id(name, city, website)
            if place_id in existing_place_ids:
                duplicate_count += 1
                continue

            lead = Lead(
                organization_id=campaign.organization_id,
                campaign_id=campaign.id,
                place_id=place_id,
                name=name,
                company_name=name,
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
                instagram_url=instagram_url,
                status=LeadStatus.NOVO,
            )

            imported_leads.append(lead)
            existing_place_ids.add(place_id)
            if website:
                existing_websites.add(website.lower())
            if normalized_domain:
                existing_domains.add(normalized_domain)
            if cnpj:
                existing_cnpjs.add(cnpj)

            # Decisor opcional vindo do CSV (colunas contato/linkedin/email).
            if contact_name:
                contact = Contact(
                    lead=lead,
                    name=contact_name,
                    role=ContactRole.OUTRO,
                    email=email,
                    phone=whatsapp,
                    linkedin_url=linkedin,
                    is_primary=True,
                    confidence=50 if email else 30,
                    source="csv",
                )
                imported_contacts.append(contact)

        # Salva na ordem certa: o Lead primeiro (gera o PK) e o Contact depois
        # (a FK `lead_id` vem da relationship). Usar `bulk_save_objects` com a
        # lista misturada quebrava a FK — aqui o unit of work resolve as
        # dependências na mesma sessão.
        if imported_leads or imported_contacts:
            db.add_all([*imported_leads, *imported_contacts])
            db.commit()

        total_rows = line_num - 1
        return {
            "total_rows": total_rows,
            "imported_count": len(imported_leads),
            "contacts_count": len(imported_contacts),
            "duplicate_count": duplicate_count,
            "error_count": len(errors),
            "errors": errors[:50],  # Limita os primeiros 50 erros para não inflar payload
        }
