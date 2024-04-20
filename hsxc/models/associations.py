# hsxc imports
from hsxc import db


league_managers = db.Table('league_managers',
    db.Column('manager_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('league_id', db.Integer, db.ForeignKey('leagues.id'))
)

school_coaches = db.Table('school_coaches',
    db.Column('coach_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('school_id', db.Integer, db.ForeignKey('schools.id'))
)

team_roster = db.Table('team_roster',
    db.Column('team_id', db.Integer, db.ForeignKey('teams.id')),
    db.Column('runner_id', db.Integer, db.ForeignKey('runners.id'))
)

school_locations = db.Table('school_locations',
    db.Column('school_id', db.Integer, db.ForeignKey('schools.id')),
    db.Column('location_id', db.Integer, db.ForeignKey('locations.id'))
)

race_schools = db.Table('race_schools',
    db.Column('race_id', db.Integer, db.ForeignKey('races.id')),
    db.Column('school_id', db.Integer, db.ForeignKey('schools.id'))
)

race_teams = db.Table('race_teams',
    db.Column('race_id', db.Integer, db.ForeignKey('races.id')),
    db.Column('team_id', db.Integer, db.ForeignKey('teams.id'))
)

