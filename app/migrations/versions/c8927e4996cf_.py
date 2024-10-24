"""empty message

Revision ID: c8927e4996cf
Revises: 301cb14b69be
Create Date: 2024-10-17 09:06:42.751504

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8927e4996cf'
down_revision = '301cb14b69be'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('general_program_popup',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('row_entry_date', sa.String(length=32), nullable=True),
    sa.Column('row_update_date', sa.String(length=32), nullable=True),
    sa.Column('header_title', sa.String(length=32), nullable=True),
    sa.Column('icon', sa.String(length=32), nullable=True),
    sa.Column('site_field', sa.String(length=32), nullable=True),
    sa.Column('site_id', sa.String(length=32), nullable=True),
    sa.Column('link_field', sa.String(length=64), nullable=True),
    sa.Column('site_url', sa.String(length=2048), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('sample_site_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['sample_site_id'], ['sample__site.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('general_program_popup', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_general_program_popup_sample_site_id'), ['sample_site_id'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('general_program_popup', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_general_program_popup_sample_site_id'))

    op.drop_table('general_program_popup')
    # ### end Alembic commands ###
