"""empty message

Revision ID: c0690512b6eb
Revises: 8d41d3580335
Create Date: 2020-09-08 10:26:17.978434

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c0690512b6eb'
down_revision = '8d41d3580335'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('teams', sa.Column('losses', sa.Integer(), nullable=True))
    op.add_column('teams', sa.Column('wins', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('teams', 'wins')
    op.drop_column('teams', 'losses')
    # ### end Alembic commands ###
