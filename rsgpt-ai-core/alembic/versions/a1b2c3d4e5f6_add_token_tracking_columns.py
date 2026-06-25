"""add token tracking columns to agent_sessions

Revision ID: a1b2c3d4e5f6
Revises: 383380c5c621
Create Date: 2025-11-28 00:00:00.000000

Adds columns to agent_sessions for context window token tracking:
- last_input_tokens: Last known input token count from LLM response
- last_model_name: Model name used for max token calculation
- token_updated_at: When token tracking was last updated
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op  # type: ignore[attr-defined]

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "383380c5c621"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add token tracking columns to agent_sessions."""
    op.add_column(
        "agent_sessions",
        sa.Column(
            "last_input_tokens",
            sa.Integer(),
            nullable=True,
            comment="Last known input token count from LLM response",
        ),
    )
    op.add_column(
        "agent_sessions",
        sa.Column(
            "last_model_name",
            sa.String(length=100),
            nullable=True,
            comment="Model name used for max token calculation",
        ),
    )
    op.add_column(
        "agent_sessions",
        sa.Column(
            "token_updated_at",
            sa.DateTime(),
            nullable=True,
            comment="When token tracking was last updated",
        ),
    )


def downgrade() -> None:
    """Remove token tracking columns from agent_sessions."""
    op.drop_column("agent_sessions", "token_updated_at")
    op.drop_column("agent_sessions", "last_model_name")
    op.drop_column("agent_sessions", "last_input_tokens")
