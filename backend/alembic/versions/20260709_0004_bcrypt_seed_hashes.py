from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260709_0004"
down_revision = "20260709_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE users
            SET password_hash = :password_hash
            WHERE id = :id
            """
        ),
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "password_hash": "$2b$12$P5YeDKifZ9aSysQ6dlwEpuOaxmR3tnQl51Lgd9yzl6ubdhzNK1RtK",
        },
    )
    connection.execute(
        sa.text(
            """
            UPDATE users
            SET password_hash = :password_hash
            WHERE id = :id
            """
        ),
        {
            "id": "00000000-0000-0000-0000-000000000002",
            "password_hash": "$2b$12$iJaces0BmY7FdErDH8uO1esf17P0guZpNsXtAZmfPQaK5LYJiklyG",
        },
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE users
            SET password_hash = :password_hash
            WHERE id = :id
            """
        ),
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "password_hash": "b0d107a1cb94cd60c513a8636f99b8d700154887e2a96f0310a1b5f3e60a6ddd",
        },
    )
    connection.execute(
        sa.text(
            """
            UPDATE users
            SET password_hash = :password_hash
            WHERE id = :id
            """
        ),
        {
            "id": "00000000-0000-0000-0000-000000000002",
            "password_hash": "9fb23d499e43fadd079634d629ba21dac14b33a860bbca99aae6ffc151cd77e0",
        },
    )
