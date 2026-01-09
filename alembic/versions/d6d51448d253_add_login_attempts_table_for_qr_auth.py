"""add_login_attempts_table_for_qr_auth

Revision ID: d6d51448d253
Revises: 6a9b1c2d3e4f
Create Date: 2026-01-09 22:02:12.916868

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'd6d51448d253'
down_revision = '6a9b1c2d3e4f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'login_attempts',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('telegram_id', sa.BigInteger(), nullable=True),
        sa.Column('telegram_username', sa.String(), nullable=True),
        sa.Column('telegram_first_name', sa.String(), nullable=True),
        sa.Column('telegram_last_name', sa.String(), nullable=True),
        sa.Column('telegram_photo_url', sa.String(), nullable=True),
        sa.Column('one_time_secret', sa.String(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('qr_code_data', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_login_attempts_token', 'login_attempts', ['token'], unique=True)
    op.create_index('ix_login_attempts_user_id', 'login_attempts', ['user_id'])
    op.create_index('ix_login_attempts_one_time_secret', 'login_attempts', ['one_time_secret'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_login_attempts_one_time_secret', table_name='login_attempts')
    op.drop_index('ix_login_attempts_user_id', table_name='login_attempts')
    op.drop_index('ix_login_attempts_token', table_name='login_attempts')
    op.drop_table('login_attempts')
