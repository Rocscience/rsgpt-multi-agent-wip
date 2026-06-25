"""remove_download_url_s3_only

Revision ID: a1b2c3d4e5f6
Revises: 0ab9c2560c80
Create Date: 2025-11-06 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '0ab9c2560c80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Remove download_url, make S3 required."""

    # Step 1: Update any NULL S3 fields to placeholder values
    # (This ensures existing data won't break when we make columns NOT NULL)
    op.execute("""
        UPDATE mcp_registry
        SET s3_bucket = 'rsinsight-mcp-releases-staging'
        WHERE s3_bucket IS NULL
    """)
    op.execute("""
        UPDATE mcp_registry
        SET s3_key = 'placeholder/migration-needed'
        WHERE s3_key IS NULL
    """)
    op.execute("""
        UPDATE mcp_versions
        SET s3_bucket = 'rsinsight-mcp-releases-staging'
        WHERE s3_bucket IS NULL
    """)
    op.execute("""
        UPDATE mcp_versions
        SET s3_key = 'placeholder/migration-needed'
        WHERE s3_key IS NULL
    """)

    # Step 2: Make S3 fields NOT NULL in mcp_registry
    op.alter_column('mcp_registry', 's3_bucket',
                    existing_type=sa.String(length=255),
                    nullable=False)
    op.alter_column('mcp_registry', 's3_key',
                    existing_type=sa.Text(),
                    nullable=False)

    # Step 3: Make S3 fields NOT NULL in mcp_versions
    op.alter_column('mcp_versions', 's3_bucket',
                    existing_type=sa.String(length=255),
                    nullable=False)
    op.alter_column('mcp_versions', 's3_key',
                    existing_type=sa.Text(),
                    nullable=False)

    # Step 4: Remove download_url columns
    op.drop_column('mcp_registry', 'download_url')
    op.drop_column('mcp_versions', 'download_url')


def downgrade() -> None:
    """Downgrade schema - Restore download_url, make S3 optional."""

    # Step 1: Add download_url columns back
    op.add_column('mcp_registry',
                  sa.Column('download_url', sa.Text(), nullable=True))
    op.add_column('mcp_versions',
                  sa.Column('download_url', sa.Text(), nullable=True))

    # Step 2: Set placeholder values for download_url
    op.execute("""
        UPDATE mcp_registry
        SET download_url = 'https://placeholder.rocscience.ai/migration-rollback'
        WHERE download_url IS NULL
    """)
    op.execute("""
        UPDATE mcp_versions
        SET download_url = 'https://placeholder.rocscience.ai/migration-rollback'
        WHERE download_url IS NULL
    """)

    # Step 3: Make download_url NOT NULL
    op.alter_column('mcp_registry', 'download_url',
                    existing_type=sa.Text(),
                    nullable=False)
    op.alter_column('mcp_versions', 'download_url',
                    existing_type=sa.Text(),
                    nullable=False)

    # Step 4: Make S3 fields nullable again
    op.alter_column('mcp_registry', 's3_bucket',
                    existing_type=sa.String(length=255),
                    nullable=True)
    op.alter_column('mcp_registry', 's3_key',
                    existing_type=sa.Text(),
                    nullable=True)
    op.alter_column('mcp_versions', 's3_bucket',
                    existing_type=sa.String(length=255),
                    nullable=True)
    op.alter_column('mcp_versions', 's3_key',
                    existing_type=sa.Text(),
                    nullable=True)
