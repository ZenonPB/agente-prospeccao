"""Rastreamento de abertura e clique de e-mails (roadmap-vendas 4.2).

Rotas **públicas** (sem auth — o cliente de e-mail do destinatário as acessa):
- `GET /t/{token}` — pixel 1×1 transparente; grava `Message.opened_at`.
- `GET /c/{token}?url=` — redireciona para a URL original; grava
  `Message.clicked_at`.

O token vem do `Message.tracking_token` (gerado no envio da cadência). Toda a
resposta é sem-cache (`no-store`) para evitar reuso indevido de leituras.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from src.db.dependencies import get_db
from src.db.models import Message
from src.services.observability import log_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tracking"])

# GIF transparente 1×1 (43 bytes) — padrão da indústria p/ pixel de abertura.
_TRANSPARENT_1PX_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff"
    b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
    b"\x00\x02\x02D\x01\x00;"
)


def _find_message(db: Session, token: str) -> Message:
    message = db.query(Message).filter(Message.tracking_token == token).first()
    if not message:
        raise HTTPException(status_code=404, detail="Token de tracking não encontrado")
    return message


@router.get("/t/{token}")
def tracking_pixel(
    token: str,
    db: Session = Depends(get_db),
) -> Response:
    """Pixel de abertura: grava `opened_at` na primeira leitura e devolve um GIF 1×1."""
    try:
        message = _find_message(db, token)
        if message.opened_at is None:
            message.opened_at = datetime.now(timezone.utc)
            db.commit()
            log_event("email_opened", lead_id=str(getattr(message, "lead_id", "")) or None)
    except HTTPException:
        # Pixel não deve "quebrar" o e-mail se o token não existir — devolve
        # o GIF mesmo assim (image load silencioso), sem registrar nada.
        pass
    except Exception as e:  # noqa: BLE001
        db.rollback()
        logger.warning("Falha ao registrar abertura token=%s: %s", token, e)

    return Response(
        content=_TRANSPARENT_1PX_GIF,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Content-Length": str(len(_TRANSPARENT_1PX_GIF)),
        },
    )


@router.get("/c/{token}")
def tracking_redirect(
    token: str,
    url: str = Query(..., description="URL original para onde redirecionar"),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Link rastreado: grava `clicked_at` e redireciona para a URL original."""
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL inválida")

    message = _find_message(db, token)
    if message.clicked_at is None:
        message.clicked_at = datetime.now(timezone.utc)
        db.commit()
        log_event("email_clicked", lead_id=str(getattr(message, "lead_id", "")) or None, url=url)

    return RedirectResponse(url=url, status_code=302)
