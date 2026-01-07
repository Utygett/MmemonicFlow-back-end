"""stub revision to restore chain

Revision ID: 423016263637
Revises:
Create Date: 2026-01-08 00:00:00
"""
from typing import Sequence, Union

revision: str = "423016263637"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Заглушка. Ничего не делает.
    pass


def downgrade() -> None:
    pass
