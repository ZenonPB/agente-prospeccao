import os
import sys
import asyncio
from typing import Optional, Dict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.database.session import SessionLocal
from src.database.models import Lead, LeadStatus, Enrichment
from src.services.places_service import GooglePlacesService 
from src.services.technical_enrichment_service import TechnicalEnrichmentService 
from src.services.scoring_service import AIScoringService 

async def run_lead_collection(query: str, max_leads_to_collect: int = 10):
    """
    Executa a coleta de leads via Google Places API.
    """
    places_service = GooglePlacesService()
    db = SessionLocal()

    print(f"\n[Pipeline] Iniciando coleta de leads para: '{query}'")

    try:
        results = await places_service.search_places(query, max_results=max_leads_to_collect)
        collected_count = 0
        for item in results:
            company_name = item.get("name")
            if not company_name:
                continue

            google_place_id = item.get("place_id_candidate")
            website_url = item.get("website")

            existing_lead = db.query(Lead).filter(
                (Lead.place_id == google_place_id) |
                ((Lead.company_name == company_name) & (Lead.website == website_url))
            ).first()

            if existing_lead:
                print(f"  [Pipeline] Lead '{company_name}' já existe (ID: {existing_lead.id}). Pulando.")
                continue

            new_lead = Lead(
                place_id=google_place_id,
                company_name=company_name,
                website=website_url,
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
            print(f"  ✅ [Pipeline] Novo lead coletado: {company_name} (Site: {new_lead.website or 'N/A'})")

        db.commit()
        print(f"\n[Pipeline] Coleta de leads finalizada. Total de {collected_count} novos leads adicionados ao DB.")

    except Exception as e:
        db.rollback()
        print(f"\nErro durante a coleta de leads: {e}")
        raise
    finally:
        db.close()

async def run_lead_enrichment_and_scoring(limit: int = 5):
    """
    Executa o enriquecimento técnico e o scoring para leads com status NOVO.
    """
    enrichment_service = TechnicalEnrichmentService()
    scoring_service = AIScoringService()
    db = SessionLocal()

    print(f"\n[Pipeline] Iniciando enriquecimento técnico para {limit} leads NOVO.")

    try:
        # Busca leads com status NOVO que possuam um website
        leads_to_enrich = db.query(Lead).filter(
            Lead.status == LeadStatus.NOVO,
            Lead.website.isnot(None) # Garante que haja um site para enriquecer
        ).limit(limit).all()

        if not leads_to_enrich:
            print("[Pipeline] Nenhum lead NOVO com website encontrado para enriquecer.")
            return

        for lead in leads_to_enrich:
            print(f"  [Enriquecimento] Processando website para '{lead.company_name}': {lead.website}")
            
            # Executa o enriquecimento técnico
            technical_report_json = await enrichment_service.enrich_website(lead.website)

            # Verifica se já existe um registro de Enrichment para este lead
            enrichment = db.query(Enrichment).filter(Enrichment.lead_id == lead.id).first()

            if enrichment:
                enrichment.raw_technical_data = technical_report_json
                enrichment.website_exists = technical_report_json.get('overall_status') != 'SITE_OFFLINE'
                enrichment.ssl_ok = technical_report_json.get('ssl', {}).get('ssl_ok', False)
                enrichment.https_redirect_ok = technical_report_json.get('ssl', {}).get('https_redirect_ok', False)
                enrichment.cms = technical_report_json.get('cms_detection')
                enrichment.load_time_ms = technical_report_json.get('http_headers', {}).get('load_time_ms')
                enrichment.security_issues = technical_report_json.get('errors', []) + technical_report_json.get('warnings', [])
            else:
                enrichment = Enrichment(
                    lead_id=lead.id,
                    raw_technical_data=technical_report_json,
                    website_exists=technical_report_json.get('overall_status') != 'SITE_OFFLINE',
                    ssl_ok=technical_report_json.get('ssl', {}).get('ssl_ok', False),
                    https_redirect_ok=technical_report_json.get('ssl', {}).get('https_redirect_ok', False),
                    cms=technical_report_json.get('cms_detection'),
                    load_time_ms=technical_report_json.get('http_headers', {}).get('load_time_ms'),
                    security_issues=technical_report_json.get('errors', []) + technical_report_json.get('warnings', [])
                )
                db.add(enrichment)
            
            # Scoring via IA
            scoring_result = await scoring_service.score_lead(technical_report_json)
            if scoring_result:
                lead.qualification_score = scoring_result.get("qualification_score", 0)
                lead.qualification_reason = scoring_result.get("qualification_reason", "")
                lead.primary_need = scoring_result.get("primary_need", "NONE")
                issues = scoring_result.get("issues_found", [])
                enrichment.security_issues = [
                    f"[{i.get('severity','')}] {i.get('title','')}: {i.get('description','')}" for i in issues
                ]
                if lead.qualification_score >= 60:
                    lead.status = LeadStatus.QUALIFICADO
                else:
                    lead.status = LeadStatus.DESQUALIFICADO
                print(f"  📊 [Scoring] Lead '{lead.company_name}' score: {lead.qualification_score} → {lead.status.value}")
            else:
                lead.status = LeadStatus.ANALISADO
                print(f"  ⚠️  [Scoring] Falha ao scoring '{lead.company_name}'. Status mantido ANALISADO.")

        db.commit()
        print(f"\n[Pipeline] Enriquecimento técnico finalizado para {len(leads_to_enrich)} leads.")

    except Exception as e:
        db.rollback()
        print(f"\nErro durante o enriquecimento de leads: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(run_lead_enrichment_and_scoring(limit=5))