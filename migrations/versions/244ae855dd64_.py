"""empty message

Revision ID: 244ae855dd64
Revises: 
Create Date: 2020-03-24 18:07:32.694930

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '244ae855dd64'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('leagues',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('long_name', sa.String(length=64), nullable=False),
    sa.Column('short_name', sa.String(length=16), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('locations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=32), nullable=True),
    sa.Column('street_address', sa.String(length=64), nullable=True),
    sa.Column('city', sa.String(length=32), nullable=True),
    sa.Column('state_abbr', sa.String(length=2), nullable=True),
    sa.Column('zip', sa.String(length=5), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('runners',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('first_name', sa.String(length=32), nullable=True),
    sa.Column('last_name', sa.String(length=32), nullable=True),
    sa.Column('grad_year', sa.Integer(), nullable=False),
    sa.Column('seed_time', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('first_name', sa.String(length=32), nullable=True),
    sa.Column('last_name', sa.String(length=32), nullable=True),
    sa.Column('email', sa.String(length=64), nullable=True),
    sa.Column('password_hash', sa.String(length=128), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('courses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=32), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('distance', sa.Float(), nullable=True),
    sa.Column('location_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('league_managers',
    sa.Column('manager_id', sa.Integer(), nullable=True),
    sa.Column('league_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['league_id'], ['leagues.id'], ),
    sa.ForeignKeyConstraint(['manager_id'], ['users.id'], )
    )
    op.create_table('schools',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('long_name', sa.String(length=64), nullable=False),
    sa.Column('short_name', sa.String(length=16), nullable=False),
    sa.Column('primary_color', sa.String(length=10), nullable=True),
    sa.Column('secondary_color', sa.String(length=10), nullable=True),
    sa.Column('text_color', sa.String(length=10), nullable=True),
    sa.Column('league_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['league_id'], ['leagues.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('races',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=True),
    sa.Column('date', sa.DateTime(), nullable=True),
    sa.Column('gender', sa.String(length=5), nullable=True),
    sa.Column('temperature', sa.Float(), nullable=True),
    sa.Column('weather', sa.String(length=32), nullable=True),
    sa.Column('conditions', sa.String(length=32), nullable=True),
    sa.Column('scoring_type', sa.String(length=16), nullable=True),
    sa.Column('host_school_id', sa.Integer(), nullable=True),
    sa.Column('location_id', sa.Integer(), nullable=True),
    sa.Column('course_id', sa.Integer(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
    sa.ForeignKeyConstraint(['host_school_id'], ['schools.id'], ),
    sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('school_coaches',
    sa.Column('coach_id', sa.Integer(), nullable=True),
    sa.Column('school_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['coach_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['school_id'], ['schools.id'], )
    )
    op.create_table('school_locations',
    sa.Column('school_id', sa.Integer(), nullable=True),
    sa.Column('location_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ),
    sa.ForeignKeyConstraint(['school_id'], ['schools.id'], )
    )
    op.create_table('teams',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('gender', sa.String(length=5), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('school_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('participants',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('bib', sa.Integer(), nullable=True),
    sa.Column('order', sa.Integer(), nullable=True),
    sa.Column('runner_id', sa.Integer(), nullable=False),
    sa.Column('race_id', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['race_id'], ['races.id'], ),
    sa.ForeignKeyConstraint(['runner_id'], ['runners.id'], ),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('results',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('bib', sa.Integer(), nullable=True),
    sa.Column('time', sa.Integer(), nullable=True),
    sa.Column('runner_id', sa.Integer(), nullable=False),
    sa.Column('race_id', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['race_id'], ['races.id'], ),
    sa.ForeignKeyConstraint(['runner_id'], ['runners.id'], ),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('team_roster',
    sa.Column('team_id', sa.Integer(), nullable=True),
    sa.Column('runner_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['runner_id'], ['runners.id'], ),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], )
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('team_roster')
    op.drop_table('results')
    op.drop_table('participants')
    op.drop_table('teams')
    op.drop_table('school_locations')
    op.drop_table('school_coaches')
    op.drop_table('races')
    op.drop_table('schools')
    op.drop_table('league_managers')
    op.drop_table('courses')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_table('runners')
    op.drop_table('locations')
    op.drop_table('leagues')
    # ### end Alembic commands ###
