"""Increase length of idempotency_key and client_temp_id fields

Revision ID: 9751384d7f4e
Revises: b530a4e41e74
Create Date: 2025-08-26 16:01:11.760527

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9751384d7f4e'
down_revision: Union[str, Sequence[str], None] = 'b530a4e41e74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Increase length of idempotency_key and client_temp_id to accommodate UUIDs (36 chars)
    op.alter_column('chat_messages', 'idempotency_key', 
                   type_=sa.String(length=36), 
                   existing_type=sa.String(length=26))
    op.alter_column('chat_messages', 'client_temp_id', 
                   type_=sa.String(length=36), 
                   existing_type=sa.String(length=26))


def downgrade() -> None:
    """Downgrade schema."""
    # Decrease length back to 26 chars (ULID format)
    op.alter_column('chat_messages', 'idempotency_key', 
                   type_=sa.String(length=26), 
                   existing_type=sa.String(length=36))
    op.alter_column('chat_messages', 'client_temp_id', 
                   type_=sa.String(length=26), 
                   existing_type=sa.String(length=36))
