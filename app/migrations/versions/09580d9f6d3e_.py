"""empty message

Revision ID: 09580d9f6d3e
Revises: 0f2b93db7efc
Create Date: 2022-04-11 10:42:29.220930

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '09580d9f6d3e'
down_revision = '0f2b93db7efc'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('beach_ambassador', schema=None) as batch_op:
        batch_op.add_column(sa.Column('site_url', sa.String(length=2048), nullable=True))
        batch_op.drop_column('site_surl')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('beach_ambassador', schema=None) as batch_op:
        batch_op.add_column(sa.Column('site_surl', sa.VARCHAR(length=2048), nullable=True))
        batch_op.drop_column('site_url')

    # ### end Alembic commands ###