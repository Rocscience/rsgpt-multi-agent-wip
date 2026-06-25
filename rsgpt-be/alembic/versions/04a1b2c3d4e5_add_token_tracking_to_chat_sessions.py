"""add_token_tracking_to_chat_sessions

Revision ID: 04a1b2c3d4e5
Revises: 03488880783f
Create Date: 2025-11-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '04a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = '03488880783f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('chat_sessions',
        sa.Column('current_token_count', sa.Integer(), nullable=False, server_default='0'))
    op.execute("COMMENT ON COLUMN chat_sessions.current_token_count IS 'The number of input tokens used in the last turn, updated after each turn'")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chat_sessions', 'current_token_count')
