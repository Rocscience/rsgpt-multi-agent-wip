"""Update ai_responses timeline column

Revision ID: 92cd1156a3c2
Revises: 7982294c2b12
Create Date: 2025-11-11 15:28:07.293850

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '92cd1156a3c2'
down_revision: Union[str, Sequence[str], None] = '7982294c2b12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('ai_responses', 'timeline',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               comment=None,
               existing_comment='Coalesced timeline of blocks (thinking, messages, tool executions) as JSON',
               existing_nullable=True)
    op.drop_index(op.f('idx_ai_responses_timeline_gin'), table_name='ai_responses', postgresql_using='gin')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_index(op.f('idx_ai_responses_timeline_gin'), 'ai_responses', ['timeline'], unique=False, postgresql_using='gin')
    op.alter_column('ai_responses', 'timeline',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               comment='Coalesced timeline of blocks (thinking, messages, tool executions) as JSON',
               existing_nullable=True)

