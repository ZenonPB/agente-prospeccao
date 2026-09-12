"""Gera e persiste o token de inbound de uma organização.

Uso (a partir de ``services/workers``):

    python -m src.scripts.gerar_inbound_token <organization_id-ou-slug>

O token em claro é exibido uma única vez no stdout. Somente o SHA-256 é
persistido. Não copie o token para logs, issues ou arquivos versionados.
"""
from __future__ import annotations

import argparse
import hashlib
import secrets
import sys
import uuid

from sqlalchemy import or_

from src.database.models import Organization
from src.database.session import SessionLocal


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _resolve_organization(db, identifier: str) -> Organization | None:
    clauses = [Organization.slug == identifier]
    try:
        clauses.append(Organization.id == uuid.UUID(identifier))
    except ValueError:
        pass
    return db.query(Organization).filter(or_(*clauses)).first()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera um token de inbound e persiste somente o hash na organização.",
    )
    parser.add_argument("organization", help="UUID ou slug da organização")
    parser.add_argument(
        "--rotate",
        action="store_true",
        help="substitui um token já existente; o token anterior deixa de funcionar",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        organization = _resolve_organization(db, args.organization.strip())
        if organization is None:
            print("Organização não encontrada.", file=sys.stderr)
            return 2

        if organization.inbound_token_hash and not args.rotate:
            print(
                "A organização já possui token de inbound. Use --rotate para substituí-lo.",
                file=sys.stderr,
            )
            return 3

        token = _new_token()
        organization.inbound_token_hash = _hash_token(token)
        db.commit()

        # Saída intencionalmente única: scripts operacionais podem redirecioná-la
        # diretamente para o secret store, sem misturar metadados e credencial.
        print(token)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
