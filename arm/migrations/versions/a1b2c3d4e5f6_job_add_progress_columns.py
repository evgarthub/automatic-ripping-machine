"""Add progress tracking columns to job

Revision ID: a1b2c3d4e5f6
Revises: 8f2c1d9e4a7b
Create Date: 2026-09-10

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '8f2c1d9e4a7b'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('job', sa.Column('progress', sa.Integer(), nullable=True))
    op.add_column('job', sa.Column('progress_round', sa.String(16), nullable=True))
    op.add_column('job', sa.Column('eta', sa.String(32), nullable=True))
    op.add_column('job', sa.Column('progress_updated_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('job', 'progress_updated_at')
    op.drop_column('job', 'eta')
    op.drop_column('job', 'progress_round')
    op.drop_column('job', 'progress')
