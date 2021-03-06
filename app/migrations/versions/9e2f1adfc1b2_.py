"""empty message

Revision ID: 9e2f1adfc1b2
Revises: 41497b24fa6e
Create Date: 2018-05-30 14:53:57.107382

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9e2f1adfc1b2'
down_revision = '41497b24fa6e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('sample__site__data')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('sample__site__data',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('row_entry_date', sa.VARCHAR(length=32), nullable=True),
    sa.Column('row_update_date', sa.VARCHAR(length=32), nullable=True),
    sa.Column('sample_date', sa.VARCHAR(length=32), nullable=True),
    sa.Column('sample_value', sa.FLOAT(), nullable=True),
    sa.Column('site_id', sa.INTEGER(), nullable=True),
    sa.ForeignKeyConstraint(['site_id'], [u'sample__site.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sample_date')
    )
    # ### end Alembic commands ###
