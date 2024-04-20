# external imports
from sqlalchemy import desc
from typing import TYPE_CHECKING, List

# hsxc imports
from hsxc import db
from hsxc.helpers import timify

if TYPE_CHECKING:
    from .school import School
    from .course import Course
    from .race import Race


class Result(db.Model):
    __tablename__ = 'results'

    id = db.Column(db.Integer, primary_key = True)
    bib = db.Column(db.Integer)
    time = db.Column(db.Integer)
    place = db.Column(db.Integer)
    status = db.Column(db.String(1))
    runner_id = db.Column(
        db.Integer, db.ForeignKey('runners.id'), nullable=False
    )
    race_id = db.Column(db.Integer, db.ForeignKey('races.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)

    def __init__(
        self, 
        place: int, 
        runner_id: int, 
        race_id: int, 
        team_id: int,
        bib: int = None,
        time: int = None,
        status: str ='n'
    ) -> None:
        max_id = Result.query.order_by(desc(Result.id)).first().id
        self.id = max_id + 1
        self.place = place
        self.runner_id = runner_id
        self.race_id = race_id
        self.team_id = team_id
        self.status = status
        self.bib = bib
        self.time = time

    def __repr__(self) -> str:
        return f"Race:{self.race_id} Runner:{self.runner_id} Time:{self.display_time()}"

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'bib': self.bib,
            'time': self.time,
            'place': self.place,
            'status': self.status,
            'runner_id': self.runner_id,
            'race_id': self.race_id,
            'team_id': self.team_id,
        }

    @property
    def pace(self) -> int:
        return self.time / self.race.course.miles()

    def display_time(self) -> str:
        return timify(self.time)

    def display_pace(self) -> str:
        return timify(self.pace)

    def adj_time(self) -> float:
        return self.pace * (1 + self.race.course.adj) * 5 * 0.621371

    def adj_time_f(self) -> str:
        return timify(self.adj_time())

    def adj_pace_f(self) -> str:
        return timify((self.adj_time()) / (5 * 0.621371))

    def team_place(self) -> int:
        if not self.time:
            return 1000
        tp = 1
        for r in self.race.results:
            if r.time and r.team == self.team and r.place < self.place:
                tp += 1
        return tp

