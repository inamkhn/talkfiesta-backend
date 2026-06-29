"""Add lapse_count to vocabulary_srs

Revision ID: a1b2c3d4e5f6
Revises: d08491eb54bb
Create Date: 2026-06-21 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'd08491eb54bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'vocabulary_srs',
        sa.Column('lapse_count', sa.Integer(), server_default='0', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('vocabulary_srs', 'lapse_count')
