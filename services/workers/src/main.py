import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from database.session import SessionLocal
from database.models import Lead, LeadStatus
from services.places_service import GooglePlacesService

def run_lead_collection(query: str, max_leads_to_collect: int = 10):
    """
    Executa a coleta de leads via Google Places API e persiste os novos
    registros no banco de dados.

    Para cada lugar retornado pelo serviço, verifica duplicatas pelo
    place_id ou pela combinação nome + website antes de inserir. Leads
    já existentes são ignorados.

    Args:
        query: Texto de busca, ex: "Restaurantes em Campinas, SP".
        max_leads_to_collect: Número máximo de leads a coletar e inserir.
    """
    service = GooglePlacesService()
    db = SessionLocal()

    print(f"\nIniciando coleta de leads para: '{query}'")

    try:
        results = service.search_places(query, max_results=max_leads_to_collect)

        collected_count = 0
        for item in results:
            company_name = item.get("name")
            if not company_name:
                continue

            existing = db.query(Lead).filter(
                (Lead.place_id == item.get("place_id_candidate")) |
                (
                    (Lead.company_name == company_name) &
                    (Lead.website == item.get("website"))
                )
            ).first()

            if existing:
                print(f"  Lead '{company_name}' já existe (ID: {existing.id}). Pulando.")
                continue

            new_lead = Lead(
                place_id=item.get("place_id_candidate"),
                company_name=company_name,
                website=item.get("website"),
                phone=item.get("phone"),
                email=None,
                category=item.get("category"),
                city=item.get("city"),
                state=item.get("state"),
                country=item.get("country", "Brasil"),
                status=LeadStatus.NOVO,
            )
            db.add(new_lead)
            collected_count += 1
            print(f"  ✅ Novo lead adicionado: {company_name} (Site: {new_lead.website or 'N/A'})")

        db.commit()
        print(f"\nColeta finalizada. {collected_count} novos leads adicionados ao DB.")

    except Exception as e:
        db.rollback()
        print(f"\nErro durante a coleta: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_lead_collection("Restaurantes em Araraquara, SP", max_leads_to_collect=10)