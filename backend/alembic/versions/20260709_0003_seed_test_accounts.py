from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260709_0003"
down_revision = "20260709_0002"
branch_labels = None
depends_on = None


ADMIN_USER = {
    "id": "00000000-0000-0000-0000-000000000001",
    "email": "admin@example.com",
    "password_hash": "$2b$12$P5YeDKifZ9aSysQ6dlwEpuOaxmR3tnQl51Lgd9yzl6ubdhzNK1RtK",
    "display_name": "Admin Tester",
    "role": "admin",
    "is_active": True,
}

STANDARD_USER = {
    "id": "00000000-0000-0000-0000-000000000002",
    "email": "user@example.com",
    "password_hash": "$2b$12$iJaces0BmY7FdErDH8uO1esf17P0guZpNsXtAZmfPQaK5LYJiklyG",
    "display_name": "User Tester",
    "role": "user",
    "is_active": True,
}


def upgrade() -> None:
    users = sa.table(
        "users",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("email", sa.String(length=255)),
        sa.column("password_hash", sa.String(length=255)),
        sa.column("display_name", sa.String(length=100)),
        sa.column("role", sa.String(length=32)),
        sa.column("is_active", sa.Boolean()),
    )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE users
            SET email = :email,
                password_hash = :password_hash,
                display_name = :display_name,
                role = :role,
                is_active = :is_active
            WHERE id = :id
            """
        ),
        ADMIN_USER,
    )

    existing_user = connection.execute(
        sa.text("SELECT id FROM users WHERE id = :id"),
        {"id": STANDARD_USER["id"]},
    ).first()
    if existing_user is None:
        op.bulk_insert(users, [STANDARD_USER])
    else:
        connection.execute(
            sa.text(
                """
                UPDATE users
                SET email = :email,
                    password_hash = :password_hash,
                    display_name = :display_name,
                    role = :role,
                    is_active = :is_active
                WHERE id = :id
                """
            ),
            STANDARD_USER,
        )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE users
            SET email = :email,
                password_hash = :password_hash,
                display_name = :display_name,
                role = :role,
                is_active = :is_active
            WHERE id = :id
            """
        ),
        {
            "id": ADMIN_USER["id"],
            "email": "admin@example.com",
            "password_hash": "dev-only",
            "display_name": "Developer",
            "role": "admin",
            "is_active": True,
        },
    )
    connection.execute(
        sa.text("DELETE FROM users WHERE id = :id"),
        {"id": STANDARD_USER["id"]},
    )
