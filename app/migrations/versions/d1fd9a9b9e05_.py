"""empty message

Revision ID: d1fd9a9b9e05
Revises: 41f0f6924843
Create Date: 2019-06-06 11:00:40.759266

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1fd9a9b9e05'
down_revision = '41f0f6924843'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('sample__site', schema=None) as batch_op:
        batch_op.add_column(sa.Column('site_type_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('site_type_id', 'site_type', ['site_type_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('sample__site', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('site_type_id')

    # ### end Alembic commands ###