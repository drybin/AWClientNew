"""create builds table

Revision ID: 0001
Revises:
Create Date: 2026-03-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "builds",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("config", JSONB, nullable=False),
        sa.Column("gh_run_id", sa.BigInteger, nullable=True),
        sa.Column("artifact_path", sa.Text, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index("ix_builds_expires_at", "builds", ["expires_at"])
    op.create_index("ix_builds_status", "builds", ["status"])


def downgrade() -> None:
    op.drop_table("builds")
