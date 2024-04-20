# external imports
from sqlalchemy import desc

# hsxc imports
from hsxc import db


class Participant(db.Model):
    __tablename__ = 'participants'

    id = db.Column(db.Integer, primary_key = True)
    bib = db.Column(db.Integer)
    order = db.Column(db.Integer)
    runner_id = db.Column(
        db.Integer, db.ForeignKey('runners.id'), nullable=False
    )
    race_id = db.Column(db.Integer, db.ForeignKey('races.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)

    def __init__(self, bib, order, runner_id, race_id, team_id):
        max_id = Participant.query.order_by(desc(Participant.id)).first().id
        self.id = max_id + 1
        self.bib = bib
        self.order = order
        self.runner_id = runner_id
        self.race_id = race_id
        self.team_id = team_id
