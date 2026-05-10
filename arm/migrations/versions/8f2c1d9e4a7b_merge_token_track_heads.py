"""merge add_token_model and track chapters/filesize

Revision ID: 8f2c1d9e4a7b
Revises: add_token_model, edf2272c0a9d
Create Date: 2026-05-10

"""
# Merge revision only — both parents applied distinct schema changes.

# revision identifiers, used by Alembic.
revision = '8f2c1d9e4a7b'
down_revision = ('add_token_model', 'edf2272c0a9d')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
