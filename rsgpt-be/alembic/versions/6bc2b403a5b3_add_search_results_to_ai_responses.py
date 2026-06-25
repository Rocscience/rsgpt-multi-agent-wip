"""add_search_results_to_ai_responses

Revision ID: 6bc2b403a5b3
Revises: d3cc4abd3c8a
Create Date: 2025-10-27 10:56:38.057224

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6bc2b403a5b3'
down_revision: Union[str, Sequence[str], None] = 'd3cc4abd3c8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ai_responses', 
        sa.Column('search_results', 
            postgresql.JSONB(astext_type=sa.Text()), 
            nullable=True))


def downgrade() -> None:
    op.drop_column('ai_responses', 'search_results')
