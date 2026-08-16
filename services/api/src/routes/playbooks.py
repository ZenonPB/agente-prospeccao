"""Playbooks por consultor (item 4.21).

Repositório de mensagens que funcionaram por vertical, anotadas pelo
próprio time. Todos os membros da org podem ler; só o autor ou admin
pode editar/remover. Sem endpoint público de copiar — a UI só exibe o
texto para o consultor copiar manualmente.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.db.dependencies import get_db
from src.db.models import (
    ConsultantPlaybook,
    Organization,
    OrganizationMember,
    User,
)
from src.auth.dependencies import (
    get_current_user,
    get_user_membership,
    get_user_organization,
)

router = APIRouter(prefix="/playbooks", tags=["playbooks"])


def _playbook_dict(p: ConsultantPlaybook) -> dict:
    return {
        "id": str(p.id),
        "organization_id": str(p.organization_id),
        "author_id": str(p.author_id),
        "author_name": p.author.name if p.author else None,
        "author_email": p.author.email if p.author else None,
        "vertical": p.vertical,
        "subject": p.subject,
        "body": p.body,
        "tags": p.tags or [],
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


class CreatePlaybookRequest(BaseModel):
    vertical: Optional[str] = Field(None, max_length=120)
    subject: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1)
    tags: List[str] = Field(default_factory=list)


class UpdatePlaybookRequest(BaseModel):
    vertical: Optional[str] = Field(None, max_length=120)
    subject: Optional[str] = Field(None, min_length=1, max_length=255)
    body: Optional[str] = Field(None, min_length=1)
    tags: Optional[List[str]] = None


@router.get("")
def list_playbooks(
    vertical: Optional[str] = Query(None, max_length=120),
    author_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _org: Organization = Depends(get_user_organization),
):
    """Lista os playbooks da organização. Qualquer membro pode ler."""
    q = db.query(ConsultantPlaybook).filter(
        ConsultantPlaybook.organization_id == _org.id,
    )
    if vertical:
        q = q.filter(ConsultantPlaybook.vertical == vertical)
    if author_id:
        q = q.filter(ConsultantPlaybook.author_id == author_id)
    rows = (
        q.order_by(ConsultantPlaybook.updated_at.desc().nullslast())
        .limit(limit)
        .all()
    )
    return {"items": [_playbook_dict(p) for p in rows]}


@router.post("")
def create_playbook(
    body: CreatePlaybookRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    """Cria um playbook. O autor é o usuário autenticado."""
    pb = ConsultantPlaybook(
        organization_id=_org.id,
        author_id=user.id,
        vertical=body.vertical,
        subject=body.subject.strip(),
        body=body.body,
        tags=body.tags,
    )
    db.add(pb)
    db.commit()
    db.refresh(pb)
    return _playbook_dict(pb)


@router.patch("/{playbook_id}")
def update_playbook(
    playbook_id: str,
    body: UpdatePlaybookRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    actor: OrganizationMember = Depends(get_user_membership),
):
    """Atualiza um playbook. Apenas o autor ou admin."""
    import uuid
    pb = (
        db.query(ConsultantPlaybook)
        .filter(
            ConsultantPlaybook.id == uuid.UUID(playbook_id),
            ConsultantPlaybook.organization_id == _org.id,
        )
        .first()
    )
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook não encontrado")
    is_author = str(pb.author_id) == str(user.id)
    is_admin = actor.role in ("OWNER", "ADMIN")
    if not (is_author or is_admin):
        raise HTTPException(
            status_code=403,
            detail="Apenas o autor ou admin pode editar este playbook",
        )

    if body.vertical is not None:
        pb.vertical = body.vertical
    if body.subject is not None:
        pb.subject = body.subject.strip()
    if body.body is not None:
        pb.body = body.body
    if body.tags is not None:
        pb.tags = body.tags
    db.commit()
    db.refresh(pb)
    return _playbook_dict(pb)


@router.delete("/{playbook_id}")
def delete_playbook(
    playbook_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    actor: OrganizationMember = Depends(get_user_membership),
):
    """Remove um playbook. Apenas o autor ou admin."""
    import uuid
    pb = (
        db.query(ConsultantPlaybook)
        .filter(
            ConsultantPlaybook.id == uuid.UUID(playbook_id),
            ConsultantPlaybook.organization_id == _org.id,
        )
        .first()
    )
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook não encontrado")
    is_author = str(pb.author_id) == str(user.id)
    is_admin = actor.role in ("OWNER", "ADMIN")
    if not (is_author or is_admin):
        raise HTTPException(
            status_code=403,
            detail="Apenas o autor ou admin pode remover este playbook",
        )
    db.delete(pb)
    db.commit()
    return {"deleted": True, "id": playbook_id}
