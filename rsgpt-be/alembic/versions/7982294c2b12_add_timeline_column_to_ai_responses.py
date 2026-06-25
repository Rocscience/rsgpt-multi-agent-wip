"""add_timeline_column_to_ai_responses

Revision ID: 7982294c2b12
Revises: 6bc2b403a5b3
Create Date: 2025-11-07 11:23:44.705090

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7982294c2b12'
down_revision: Union[str, Sequence[str], None] = '6bc2b403a5b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('ai_responses',
        sa.Column('timeline',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True))
    op.create_index('idx_ai_responses_timeline_gin', 'ai_responses', ['timeline'], unique=False, postgresql_using='gin')
    op.execute("COMMENT ON COLUMN ai_responses.timeline IS 'Coalesced timeline of blocks (thinking, messages, tool executions) as JSON'")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_ai_responses_timeline_gin', table_name='ai_responses')
    op.drop_column('ai_responses', 'timeline')
