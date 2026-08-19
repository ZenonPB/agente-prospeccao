"""Serviço de sincronização direta com a API do Google Sheets via OAuth2.

Permite autorizar a organização via OAuth2 do Google e espelhar automaticamente
os leads de uma campanha diretamente em uma planilha do Google Sheets sem intermediários.
"""
import logging
import os
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.db.models import Campaign, Lead
from services.secret_service import SecretService, encrypt_value, decrypt_value
from database.models import OrganizationSecret

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
SHEETS_API_BASE = "https://sheets.googleapis.com/v4/spreadsheets"

class GoogleSheetsService:
    @staticmethod
    def get_auth_url(redirect_uri: str, state: str = "") -> str:
        """Gera a URL de consentimento OAuth2 para o usuário autorizar o escopo de Google Sheets."""
        client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", None) or os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
        ]
        scope_str = " ".join(scopes)
        
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope_str,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        query_parts = [f"{k}={httpx.URL('', params={k: v}).query.decode('utf-8')}" for k, v in params.items()]
        # Formata URL limpa
        from urllib.parse import urlencode
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    @staticmethod
    async def exchange_code_and_store(
        db: Session,
        organization_id: Any,
        code: str,
        redirect_uri: str,
    ) -> Dict[str, Any]:
        """Troca o código de autorização por tokens e persiste o refresh token no OrganizationSecret."""
        client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", None) or os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
        client_secret = getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", None) or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")

        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(GOOGLE_TOKEN_URL, data=payload)
            if res.status_code != 200:
                logger.error("Falha na troca de código OAuth2 Google: %s", res.text)
                return {"success": False, "error": f"HTTP {res.status_code}: {res.text}"}

            data = res.json()

        refresh_token = data.get("refresh_token")
        access_token = data.get("access_token")

        if refresh_token:
            SecretService.set_org_secret(db, organization_id, "GOOGLE_OAUTH_REFRESH_TOKEN", refresh_token)
        elif access_token:
            # Caso não venha refresh_token (já autorizado previamente), salva access token temporário
            SecretService.set_org_secret(db, organization_id, "GOOGLE_OAUTH_ACCESS_TOKEN", access_token)

        return {"success": True, "access_token": access_token}

    @staticmethod
    async def get_access_token(db: Session, organization_id: Any) -> Optional[str]:
        """Obtém um Access Token válido via Refresh Token ou Secret."""
        refresh_token = SecretService.get_org_secret(db, organization_id, "GOOGLE_OAUTH_REFRESH_TOKEN")
        if not refresh_token:
            return SecretService.get_org_secret(db, organization_id, "GOOGLE_OAUTH_ACCESS_TOKEN")

        client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", None) or os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
        client_secret = getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", None) or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")

        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(GOOGLE_TOKEN_URL, data=payload)
            if res.status_code == 200:
                return res.json().get("access_token")
            logger.error("Falha ao renovar Access Token Google OAuth2: %s", res.text)
            return None

    @staticmethod
    async def sync_campaign_to_sheets(
        db: Session,
        organization_id: Any,
        campaign_id: Any,
        spreadsheet_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Sincroniza os leads de uma campanha com uma planilha do Google Sheets."""
        access_token = await GoogleSheetsService.get_access_token(db, organization_id)
        if not access_token:
            return {"success": False, "error": "Organização não conectada ao Google OAuth2"}

        campaign = db.query(Campaign).filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == organization_id,
        ).first()

        if not campaign:
            return {"success": False, "error": "Campanha não encontrada"}

        leads = db.query(Lead).filter(
            Lead.campaign_id == campaign_id,
            Lead.organization_id == organization_id,
        ).all()

        # Monta matriz de dados
        headers = [
            "ID Lead", "Empresa", "CNPJ", "Website", "Telefone", "E-mail",
            "Cidade", "UF", "Status", "Score", "Prioridade", "Resumo Executivo"
        ]
        rows = [headers]
        for lead in leads:
            rows.append([
                str(lead.id),
                lead.company_name or lead.name or "",
                lead.cnpj or "",
                lead.website or "",
                lead.phone or "",
                lead.email or "",
                lead.city or "",
                lead.state or "",
                lead.status.value if lead.status else "",
                lead.qualification_score or 0,
                lead.priority.value if lead.priority else "",
                lead.executive_summary or "",
            ])

        headers_http = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Se não foi passado spreadsheet_id, cria uma nova planilha no Google Drive
            if not spreadsheet_id:
                create_payload = {
                    "properties": {"title": f"Prospecção — {campaign.name}"},
                    "sheets": [{"properties": {"title": "Leads"}}]
                }
                res = await client.post(SHEETS_API_BASE, json=create_payload, headers=headers_http)
                if res.status_code != 200:
                    return {"success": False, "error": f"Erro ao criar planilha: {res.text}"}
                spreadsheet_id = res.json().get("spreadsheetId")

            # 2. Atualiza os dados na planilha na aba 'Leads' (ou primeira página)
            update_url = f"{SHEETS_API_BASE}/{spreadsheet_id}/values/A1:Z{len(rows)}?valueInputOption=USER_ENTERED"
            update_payload = {"values": rows}

            res = await client.put(update_url, json=update_payload, headers=headers_http)
            if res.status_code != 200:
                return {"success": False, "error": f"Erro ao atualizar dados na planilha: {res.text}"}

            spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
            return {
                "success": True,
                "spreadsheet_id": spreadsheet_id,
                "spreadsheet_url": spreadsheet_url,
                "total_synced": len(leads),
            }
