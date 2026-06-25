"""Add agent_quota and agent_quota_used columns to users table

Revision ID: b1c2d3e4f5a6
Revises: f0f638995182
Create Date: 2026-01-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'f0f638995182'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('agent_quota', sa.Integer(), nullable=False, server_default='10'))
    op.add_column('users', sa.Column('agent_quota_used', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'agent_quota_used')
    op.drop_column('users', 'agent_quota')
