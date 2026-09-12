"""Hash existing invite tokens in place.

Revision ID: 8e0f2a4c6d7b
Revises: 7d9e1f3a5b6c
"""
from __future__ import annotations

import hashlib
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "8e0f2a4c6d7b"
down_revision: Union[str, Sequence[str], None] = "7d9e1f3a5b6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, token FROM invites WHERE token IS NOT NULL")).mappings().all()
    for row in rows:
        token = str(row["token"])
        if _HEX_64.fullmatch(token):
            continue
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        bind.execute(
            sa.text("UPDATE invites SET token = :token_hash WHERE id = :invite_id"),
            {"token_hash": token_hash, "invite_id": row["id"]},
        )


def downgrade() -> None:
    # O segredo original não pode ser reconstruído a partir do hash.
    pass
