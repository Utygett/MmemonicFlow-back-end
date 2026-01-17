"""add new fields

Revision ID: 6b0257cd1749
Revises: 828feac3f113
Create Date: 2026-01-18 02:16:47.826679
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "6b0257cd1749"
down_revision: Union[str, Sequence[str], None] = "828feac3f113"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем колонки и заполняем существующие строки текущим временем на стороне БД
    op.add_column(
        "card_review_history",
        sa.Column(
            "show_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "card_review_history",
        sa.Column(
            "reveal_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Если не хочешь, чтобы DEFAULT now() оставался для новых строк — убираем дефолт
    op.alter_column("card_review_history", "show_at", server_default=None)
    op.alter_column("card_review_history", "reveal_at", server_default=None)


def downgrade() -> None:
    op.drop_column("card_review_history", "reveal_at")
    op.drop_column("card_review_history", "show_at")
