"""empty message

Revision ID: c7fd7f06feb0
Revises: f7e51f073865
Create Date: 2022-02-23 10:59:24.426115

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7fd7f06feb0'
down_revision = 'f7e51f073865'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.rename_table('project_info_page', 'collection_program_info')

    op.create_table('collection__program__info__mapper',
    sa.Column('collection_program_info_id', sa.Integer(), nullable=False),
    sa.Column('project_area_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['collection_program_info_id'], ['collection_program_info.id'], ),
    sa.ForeignKeyConstraint(['project_area_id'], ['project_area.id'], ),
    sa.PrimaryKeyConstraint('collection_program_info_id', 'project_area_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.rename_table('collection_program_info', 'project_info_page')
    op.drop_table('collection__program__info__mapper')
    # ### end Alembic commands ###