"""Merge the opportunity and controlled-learning migration heads.

Revision ID: 3c7d9e1f2a3b
Revises: 3a5b7c9d1e2f, 3b6c8d0e1f2a
"""
from typing import Sequence, Union

from alembic import op


revision: str = "3c7d9e1f2a3b"
down_revision: Union[str, Sequence[str], None] = (
    "3a5b7c9d1e2f",
    "3b6c8d0e1f2a",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Unifica o histórico sem alterar o schema."""
    pass


def downgrade() -> None:
    """Reabre os dois heads anteriores ao fazer downgrade."""
    pass