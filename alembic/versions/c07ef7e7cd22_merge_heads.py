"""merge heads

Revision ID: c07ef7e7cd22
Revises: e2f3a4b5c6d7, f2b3c4d5e6f7
Create Date: 2025-12-26 18:08:00.262326

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'c07ef7e7cd22'
down_revision = ('e2f3a4b5c6d7', 'f2b3c4d5e6f7')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
