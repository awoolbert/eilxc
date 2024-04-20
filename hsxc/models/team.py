# external imports
from typing import List, TYPE_CHECKING, Tuple
from dataclasses import dataclass

# hsxc imports
from hsxc import db
from .associations import team_roster, race_teams
from .race_score import RaceScore

if TYPE_CHECKING:
    from .runner import Runner
    from .race import Race
    from .school import School
    from .result import Result

@dataclass
class DualRes:
    race_id: int
    race_dt: str
    opp_id: int
    school_name: str
    primary_color: str
    secondary_color: str
    text_color: str
    win_loss: str
    own_score: int
    opp_score: int

@dataclass
class TeamRecord:
    team_id: int
    year: int
    school_name: str
    primary_color: str
    secondary_color: str
    text_color: str
    total_wins: int
    total_losses: int
    league_wins: int
    league_losses: int
    dual_results: List[DualRes]


class Team(db.Model):
    __tablename__ = 'teams'

    id = db.Column(db.Integer, primary_key = True)
    gender = db.Column(db.String(5), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    wins = db.Column(db.Integer)
    losses = db.Column(db.Integer)
    league_wins = db.Column(db.Integer)
    league_losses = db.Column(db.Integer)
    school_id = db.Column(
        db.Integer, db.ForeignKey('schools.id'), nullable=False
    )

    results: List['Result'] = db.relationship('Result', backref='team', lazy=True)
    runners: List['Runner'] = db.relationship('Runner', secondary=team_roster)
    races: List['Race'] = db.relationship('Race', secondary=race_teams)

    def __init__(self, gender: str, year: int, school_id: str) -> None:
        current_max_id = db.session.query(db.func.max(Team.id)).scalar()
        self.id: int = current_max_id + 1 if current_max_id else 1
        self.gender = gender
        self.year = year
        self.school_id = school_id

    def __repr__(self):
        return f'id:{self.id} {self.team_name()}'

    def to_dict(self):
        return {
            'id': self.id,
            'gender': self.gender,
            'year': self.year,
            'school_id': self.school_id,
        }
 
    def team_name(self) -> str:
        """Returns: (str) School Year Gender (e.g,. NCDS 2023 Girls)"""
        return f'{self.school.short_name} {self.year} {self.gender_f()}'

    def gender_f(self) -> str:
        """Returns: (str) Girls or Boys"""
        return self.gender.capitalize()

    def gender_code(self) -> int:
        """Returns: (int) 1 if girls team, 2 if boys team"""
        return 1 if self.gender == 'girls' else 2

    def alphabetized_runners(self) -> List['Runner']:
        """Returns: (list) Runners sorted by last name, first name"""
        return sorted(self.runners, key=lambda r: r.last_first().lower())

    def runners_fastest_to_slowest(self) -> List['Runner']:
        """Returns: (list) Runners sorted by seed time"""
        return sorted(self.runners, key=lambda r: r.seed_time)

    def top_7_runners(self) -> List['Runner']:
        """Returns: (list) Runners sorted by seed time"""
        max_runners = 7 if len(self.runners) >= 7 else len(self.runners)
        return self.runners_fastest_to_slowest()[:max_runners]

    def completed_races(self) -> List['Race']:
        """Returns: (list) Races which are complete and have 5+ runners"""
        return [r for r in self.races if r.status == 'complete']

    def completed_results(self) -> List['Result']:
        return [r for r in self.results if r.status == 'c']

    def has_completed_results(self) -> bool:
        return any([r.status == 'c' for r in self.results])

    def has_five_runners(self, race) -> bool:
        return len([r for r in self.results if r.race == race]) >= 5

    def team_6th_time(self, race) -> int:
        results = [r for r in self.results if r.race == race]
        results = sorted(results, key=lambda r: r.time)
        return results[5].time if len(results) > 5 else 99999999

    def rank(self) -> Tuple[float, float, int, str]:
        """
        Return a tuple of values used to rank the team in the league standings.
        The first value is the win percentage against league opponents. The
        second value is the win percentage against all opponents. The third
        value is the number of wins. The fourth value is the school name.
        """
        league_duals = self.league_wins + self.league_losses
        league_win_pct = self.league_wins / league_duals if league_duals else 0
        total_duals = self.wins + self.losses
        total_win_pct = self.wins / total_duals if total_duals else 0
        return (
            -league_win_pct,
            -total_win_pct,
            -self.wins,
            self.school.short_name
        )
