"""empty message

Revision ID: 963b706f6f92
Revises: 757789afe568
Create Date: 2017-11-29 14:01:28.784793

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '963b706f6f92'
down_revision = '757789afe568'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('boundary', schema=None) as batch_op:
        batch_op.drop_column('wkt_boundary')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('boundary', schema=None) as batch_op:
        batch_op.add_column(sa.Column('wkt_boundary', sa.TEXT(), nullable=True))

    # ### end Alembic commands ###
