"""empty message

Revision ID: c9bd56388f14
Revises: f01da78973c0
Create Date: 2023-06-16 13:52:00.770931

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9bd56388f14'
down_revision = 'f01da78973c0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('shell_cast',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('row_entry_date', sa.String(length=32), nullable=True),
    sa.Column('row_update_date', sa.String(length=32), nullable=True),
    sa.Column('site_id', sa.String(length=64), nullable=True),
    sa.Column('site_url', sa.String(length=2048), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('sample_site_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['sample_site_id'], ['sample__site.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('usgs_sites',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('row_entry_date', sa.String(length=32), nullable=True),
    sa.Column('row_update_date', sa.String(length=32), nullable=True),
    sa.Column('usgs_site_id', sa.String(length=16), nullable=True),
    sa.Column('parameters_to_query', sa.String(), nullable=True),
    sa.Column('sample_site_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['sample_site_id'], ['sample__site.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('web_coos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('row_entry_date', sa.String(length=32), nullable=True),
    sa.Column('row_update_date', sa.String(length=32), nullable=True),
    sa.Column('webcoos_id', sa.String(length=64), nullable=True),
    sa.Column('sample_site_id', sa.Integer(), nullable=True),
    sa.Column('site_url', sa.String(length=2048), nullable=True),
    sa.ForeignKeyConstraint(['sample_site_id'], ['sample__site.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.drop_table('webCOOS')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('webCOOS',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('row_entry_date', sa.VARCHAR(length=32), nullable=True),
    sa.Column('row_update_date', sa.VARCHAR(length=32), nullable=True),
    sa.Column('webcoos_id', sa.VARCHAR(length=64), nullable=True),
    sa.Column('sample_site_id', sa.INTEGER(), nullable=True),
    sa.Column('site_url', sa.VARCHAR(length=2048), nullable=True),
    sa.ForeignKeyConstraint(['sample_site_id'], ['sample__site.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.drop_table('web_coos')
    op.drop_table('usgs_sites')
    op.drop_table('shell_cast')
    # ### end Alembic commands ###
