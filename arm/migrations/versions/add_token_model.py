"""Add Token model for API authentication

Revision ID: add_token_model
Revises: 50d63e3650d2
Create Date: 2026-04-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_token_model'
down_revision = '50d63e3650d2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('token',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=False),
                    sa.Column('token_hash', sa.String(length=128), nullable=False),
                    sa.Column('expiry', sa.DateTime(), nullable=False),
                    sa.Column('created_at', sa.DateTime(), nullable=True),
                    sa.Column('last_used', sa.DateTime(), nullable=True),
                    sa.ForeignKeyConstraint(['user_id'], ['user.user_id'], ),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('token_hash')
                    )


def downgrade():
    op.drop_table('token')