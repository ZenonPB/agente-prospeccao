"""Add performance indexes for high-traffic FKs.

Revision ID: a1b2c3d4e5f6
Revises: f8e9d0c1b2a3
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "f8e9d0c1b2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_leads_campaign_id", "leads", ["campaign_id"])
    op.create_index("ix_leads_assigned_to_id", "leads", ["assigned_to_id"])
    op.create_index("ix_messages_lead_id", "messages", ["lead_id"])
    op.create_index("ix_conversions_lead_id", "conversions", ["lead_id"])


def downgrade() -> None:
    op.drop_index("ix_conversions_lead_id", table_name="conversions")
    op.drop_index("ix_messages_lead_id", table_name="messages")
    op.drop_index("ix_leads_assigned_to_id", table_name="leads")
    op.drop_index("ix_leads_campaign_id", table_name="leads")
