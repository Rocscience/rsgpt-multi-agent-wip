"""add_uppercase_cancelled_to_messagestatus

Revision ID: 562139430c84
Revises: 1dbcff81ce16
Create Date: 2025-10-20 15:57:32.660679

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '562139430c84'
down_revision: Union[str, Sequence[str], None] = '1dbcff81ce16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add the 'CANCELLED' value to the PostgreSQL "messagestatus" enum.
    
    Performs an ALTER TYPE statement that adds the enum value if it does not already exist.
    """
    # Add 'CANCELLED' value to the existing messagestatus enum type
    # Note: This matches the uppercase convention of existing enum values
    # (SUBMITTED, STREAMING, COMPLETED, ERRORED)
    op.execute("ALTER TYPE messagestatus ADD VALUE IF NOT EXISTS 'CANCELLED'")


def downgrade() -> None:
    """
    No-op downgrade for this migration.
    
    This downgrade does not remove the 'CANCELLED' value from the `messagestatus` PostgreSQL enum because PostgreSQL does not support removing enum values in-place. Removing it would require dropping and recreating the enum (and migrating dependent data), which is intentionally not performed here.
    """
    # NOTE: PostgreSQL does not support removing enum values
    # Once added, the 'CANCELLED' value will remain in the enum
    # This is a limitation of PostgreSQL enums
    # To truly remove it would require dropping and recreating the enum,
    # which would require complex migration logic
    pass