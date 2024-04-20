# external imports

# hsxc imports
from hsxc import db


class RaceScore(db.Model):
    __tablename__ = 'race_scores'

    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.Integer, db.ForeignKey('races.id'), nullable=False)
    winner_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    loser_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    winner_score = db.Column(db.Integer)
    loser_score = db.Column(db.Integer)

    race = db.relationship(
        'Race', 
        backref=db.backref('race_scores', lazy=True)
    )
    winner = db.relationship(
        'Team', 
        foreign_keys=[winner_id], 
        backref=db.backref('races_won', lazy=True)
    )
    loser = db.relationship(
        'Team', 
        foreign_keys=[loser_id], 
        backref=db.backref('races_lost', lazy=True)
    )

    def __init__(
        self, 
        race_id, 
        winner_id, 
        loser_id, 
        winner_score, 
        loser_score
    ) -> None:
        self.race_id = race_id
        self.winner_id = winner_id
        self.loser_id = loser_id
        self.winner_score = winner_score
        self.loser_score = loser_score

    def __repr__(self) -> str:
        return f'RaceScore:{self.id}, Race_id:{self.race_id}'