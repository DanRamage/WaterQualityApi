"""empty message

Revision ID: 91cda64fb101
Revises: cc1d0cef8ecb
Create Date: 2022-02-23 13:18:00.402292

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '91cda64fb101'
down_revision = 'cc1d0cef8ecb'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('collection_program_info',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('row_entry_date', sa.String(length=32), nullable=True),
    sa.Column('row_update_date', sa.String(length=32), nullable=True),
    sa.Column('program', sa.Text(), nullable=True),
    sa.Column('url', sa.String(length=2048), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('state', sa.String(length=128), nullable=True),
    sa.Column('state_abbreviation', sa.String(length=2), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
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
    op.drop_table('collection__program__info__mapper')
    op.drop_table('collection_program_info')
    # ### end Alembic commands ###
