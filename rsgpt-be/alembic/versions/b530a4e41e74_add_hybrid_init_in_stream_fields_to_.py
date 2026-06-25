"""Add hybrid init-in-stream fields to chat_messages

Revision ID: b530a4e41e74
Revises: 7bf38ae931f7
Create Date: 2025-08-26 11:16:36.680683

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b530a4e41e74'
down_revision: Union[str, Sequence[str], None] = '7bf38ae931f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the MessageStatus enum type
    messagestatus_enum = sa.Enum('SUBMITTED', 'STREAMING', 'COMPLETED', 'ERRORED', name='messagestatus')
    messagestatus_enum.create(op.get_bind())
    
    # Add new columns
    op.add_column('chat_messages', sa.Column('status', messagestatus_enum, nullable=True))
    op.add_column('chat_messages', sa.Column('idempotency_key', sa.String(length=26), nullable=True))
    op.add_column('chat_messages', sa.Column('client_temp_id', sa.String(length=26), nullable=True))
    
    # Set default status for existing messages
    connection = op.get_bind()
    connection.execute(sa.text("UPDATE chat_messages SET status = 'COMPLETED' WHERE status IS NULL"))
    
    # Make status column non-nullable
    op.alter_column('chat_messages', 'status', nullable=False)
    
    # Create unique constraint on idempotency_key
    op.create_unique_constraint('uq_chat_messages_idempotency_key', 'chat_messages', ['idempotency_key'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop unique constraint
    op.drop_constraint('uq_chat_messages_idempotency_key', 'chat_messages', type_='unique')
    
    # Drop columns
    op.drop_column('chat_messages', 'client_temp_id')
    op.drop_column('chat_messages', 'idempotency_key')
    op.drop_column('chat_messages', 'status')
    
    # Drop the enum type
    messagestatus_enum = sa.Enum(name='messagestatus')
    messagestatus_enum.drop(op.get_bind())
