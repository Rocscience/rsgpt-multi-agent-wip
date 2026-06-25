"""add_usage_breakdown_to_ai_responses

Revision ID: 03488880783f
Revises: 92cd1156a3c2
Create Date: 2025-11-13 12:38:19.803401

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '03488880783f'
down_revision: Union[str, Sequence[str], None] = '92cd1156a3c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('ai_responses',
        sa.Column('usage_breakdown',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True))
    op.create_index('idx_ai_responses_usage_breakdown_gin', 'ai_responses', ['usage_breakdown'], unique=False, postgresql_using='gin')
    op.execute("COMMENT ON COLUMN ai_responses.usage_breakdown IS 'Per-request usage breakdown from openai-agents v0.5.0 (request_usage_entries)'")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_ai_responses_usage_breakdown_gin', table_name='ai_responses')
    op.drop_column('ai_responses', 'usage_breakdown')
