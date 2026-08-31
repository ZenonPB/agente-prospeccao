"""Add performance indexes for high-traffic FKs.

Revision ID: b2c3d4e5f6a8
Revises: a9b8c7d6e5f4
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a8"
down_revision = "a9b8c7d6e5f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_leads_campaign_id", "leads", ["campaign_id"])
    op.create_index("ix_messages_lead_id", "messages", ["lead_id"])
    op.create_index("ix_conversions_lead_id", "conversions", ["lead_id"])


def downgrade() -> None:
    op.drop_index("ix_conversions_lead_id", table_name="conversions")
    op.drop_index("ix_messages_lead_id", table_name="messages")
    op.drop_index("ix_leads_campaign_id", table_name="leads")
