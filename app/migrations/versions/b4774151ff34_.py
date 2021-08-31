"""empty message

Revision ID: b4774151ff34
Revises: 988d86fa4051
Create Date: 2017-11-29 08:41:09.944843

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4774151ff34'
down_revision = '988d86fa4051'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('boundary', schema=None) as batch_op:
        batch_op.create_unique_constraint('boundary_name', ['boundary_name'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('boundary', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='unique')

    # ### end Alembic commands ###
