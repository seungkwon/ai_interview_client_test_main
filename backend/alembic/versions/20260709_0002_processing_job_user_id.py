from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260709_0002"
down_revision = "20260709_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "processing_jobs",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_processing_jobs_user_id_users",
        "processing_jobs",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_index("ix_processing_jobs_user_id", "processing_jobs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_processing_jobs_user_id", table_name="processing_jobs")
    op.drop_constraint("fk_processing_jobs_user_id_users", "processing_jobs", type_="foreignkey")
    op.drop_column("processing_jobs", "user_id")
