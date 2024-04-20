# external imports
from sqlalchemy import asc
from itertools import combinations
from dataclasses import dataclass
from datetime import datetime
from typing import List, TYPE_CHECKING
from copy import deepcopy

# hsxc imports
from hsxc import db
from hsxc.helpers import timify
from .associations import race_teams, race_schools
from .race_score import RaceScore
from .team import Team

if TYPE_CHECKING:
    from .runner import Runner
    from .result import Result
    from .school import School


@dataclass
class IndRes:
    """All the data needed for a row in the results table"""
    place: int
    bib: int
    id: int
    runner_id: int
    runner_name: str
    name: str
    grad_year: str
    short_year: str
    school_id: int
    school_name: str
    primary_color: str
    secondary_color: str
    text_color: str
    team_id: int
    time: int
    time_f: str
    pace_f: str
    team_place: int
    points: int or None

@dataclass
class TeamRes:
    """All the data needed for a summary in the team results area"""
    team_id: int
    school_id: int
    school_name: str
    school_long_name: str
    primary_color: str
    text_color: str
    score: int
    place: int
    gender: str
    average_time: str
    first_fifth_spread: str
    time_6th: int
    scorers: List[IndRes]

@dataclass
class WinLossRow:
    """Summary of team's wins/losses for multi-team dual meets"""
    team_id: int
    school_id: int
    school_long_name: str
    primary_color: str
    text_color: str
    gender: str
    wins: int
    losses: int

@dataclass
class ResSum:
    """Summary results of a race"""
    race_id: int
    individual_results: List[IndRes]
    race_results: List[List[TeamRes]]
    win_loss_table: dict or None


class Race(db.Model):
    __tablename__ = 'races'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer)
    name = db.Column(db.String(128))
    date = db.Column(db.DateTime)
    gender = db.Column(db.String(5))
    temperature = db.Column(db.Float)
    weather = db.Column(db.String(32))
    conditions = db.Column(db.String(32))
    scoring_type = db.Column(db.String(16))
    status = db.Column(db.String(8))
    is_jv = db.Column(db.Boolean, default=False)
    host_school_id = db.Column(db.Integer, db.ForeignKey('schools.id'))
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    results = db.relationship('Result', backref='race', lazy=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    schools = db.relationship('School', secondary=race_schools)
    teams = db.relationship('Team', secondary=race_teams)

    def __init__(self, 
        user_id, 
        date,
        name=None,
        gender:str=None,
        scoring_type='dual',
        status='new',
        host_school_id=None,
        location_id=None,
        course_id=None,
        group_id=None,
        is_jv=False,
    ) -> None:
        current_max_id = db.session.query(db.func.max(Race.id)).scalar()
        self.id: int = current_max_id + 1 if current_max_id else 1
        self.date: datetime = date
        self.user_id: int = user_id
        self.name: str = name
        self.gender: str = gender
        self.scoring_type: str = scoring_type
        self.status: str = status
        self.host_school_id: int = host_school_id
        self.location_id: int = location_id
        self.course_id: int = course_id
        self.group_id: int = group_id
        self.is_jv: bool = is_jv
        self._individual_results: List[IndRes] = None

    def __repr__(self) -> str:
        return f"{self.date_f()}: {self.display_name_gender_jv()}"

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'date': self.date_f(),
            'name': self.name,
            'gender': self.gender,
            'scoring_type': self.scoring_type,
            'status': self.status,
            'host_school_id': self.host_school_id,
            'location_id': self.location_id,
            'course_id': self.course_id,
            'group_id': self.group_id,
            'is_jv': self.is_jv,
        }

    def date_f(self) -> str:
        """Returns (str) YYYY-MM-DD"""
        return self.date.strftime("%Y-%m-%d")

    def date_long_f(self) -> str:
        """Returns (str) Month D, YYYY"""
        return self.date.strftime("%B %e, %Y")

    def name_f(self) -> str:
        """Returns (str) name (e.g., ISL Championship - Boys JV)"""
        return f'{self.name} - {self.gender_f()}{" JV" if self.is_jv else ""}'

    def gender_f(self) -> str:
        """Returns (str) Boys, Girls, Combo"""
        return self.gender.capitalize() if self.gender else None

    def complete_teams(self) -> List['Team']:
        """List of teams with 5 or more runners"""
        return [team for team in self.teams if team.has_five_runners(self)]

    def complete_results(self) -> List['Result']:
        """List of results with times"""
        return [res for res in self.results if res.status == 'c']

    def team_count(self) -> int:
        """Number of complete teams competing"""
        return len(self.complete_teams())

    def all_runners(self) -> List['Runner']:
        return [res.runner for res in self.results]

    def sorted_results(self) -> List['Result']:
        """List of results sorted by time from fastest to slowest"""
        return sorted(
            [r for r in self.results if r.time], key=lambda x:(x.time, x.place)
        )

    def group_races(self) -> List['Race']:
        """List of races in this group, sorted by race_id"""
        return (
            Race
            .query
            .filter_by(group_id=self.group_id)
            .order_by(asc(Race.id))
            .all()
        )

    def previous_group_race_id(self) -> int or None:
        """Race_id for the previous race in this group (if applicable)"""
        idx = self.group_races().index(self)
        return None if idx == 0 else self.group_races()[idx - 1].id

    def next_group_race_id(self) -> int or None:
        """Race_id for the next race in this group (if applicable)"""
        group_races = self.group_races()
        idx = group_races.index(self)
        return None if idx == len(group_races) - 1 else group_races[idx + 1].id

    def other_group_races(self) -> List['Race']:
        """List of Race_ids for the other races in this group"""
        group_races = Race.query.filter_by(group_id=self.group_id).all()
        return [race for race in group_races if race.id != self.id]

    def is_championship(self) -> bool:
        return 'championship' in self.name.lower()

    def has_bibs(self) -> bool:
        """Returns true if results have bibs for any runner"""
        return any(not (r.bib is None or r.bib == 0) for r in self.results)

    @property
    def winner_id(self) -> 'School':
        if self.scoring_type != 'invitational':
            return None
        
        return self.results_summary().race_results[0][0].school_id

    def results_summary(self, force_dual=False) -> ResSum:
        print(f'\n preparing results summary for {self.name_f()}')

        individual_results = self.individual_results()
        team_list = self.complete_teams()

        # corner case: only one complete team in race
        if len(team_list) == 1:
            race_results = []
            win_loss_table = None

        # no win_loss_table for invitationals or dual meets with only 2 teams
        elif self.scoring_type == 'invitational' or len(team_list) == 2:
            race_results = [self.score_race(team_list)]
            win_loss_table = None

        # create win_loss_table for multiple dual meet format
        else:
            race_results = [
                self.score_race(team_pair)
                for team_pair in combinations(team_list, 2)
                if team_pair[0].gender == team_pair[1].gender
            ]
            win_loss_table = self.win_loss_table(race_results)

        return ResSum(
            race_id=self.id,
            individual_results=individual_results,
            race_results=race_results,
            win_loss_table=win_loss_table
        )

    def individual_results(self) -> List[IndRes]:
        """Ordered list of IndResult"""
        if not hasattr(self, '_individual_results'):
            self._individual_results = self._calc_individual_results()
        return self._individual_results

    def _calc_individual_results(self) -> List[IndRes]:
        rows, place, points = [], 0, 1
        for res in self.sorted_results():
            # store data in variables for readability/to avoid redundant calls
            runner: Runner = res.runner
            team: Team = res.team
            school: School = team.school

            # increment place and points (if applicable)
            place += 1
            is_scorer = res.team_place() <= 7 and team.has_five_runners(self)
            row_points = points if is_scorer else None
            points += 1 if is_scorer else 0

            # create row
            row = IndRes(
                place = place,
                bib = res.bib,
                id = res.id,
                runner_id = runner.id,
                runner_name=runner.display_name(),
                name = runner.display_name(),
                grad_year = runner.grad_year,
                short_year = "'" + str(runner.grad_year)[2:],
                school_id = school.id,
                school_name = school.short_name,
                primary_color = school.primary_color,
                secondary_color = school.secondary_color,
                text_color = school.text_color,
                team_id = team.id,
                time = res.time,
                time_f = res.display_time(),
                pace_f = res.display_pace(),
                team_place = res.team_place(),
                points = row_points
            )
            rows.append(row)
        return rows

    def score_race(self, teams: List['Team']) -> List[TeamRes]:
        print(f'  scoring id:{self.id} {self.name_f()} with teams:')
        for team in teams: print(f'   {team}')

        teams = [team for team in teams if team.has_five_runners(self)]
        all_scorers = self._create_list_of_scorers(teams)
        race_result = self._create_race_result(teams, all_scorers)
        self._update_race_score_table(teams, race_result)
        
        return race_result

    def _create_list_of_scorers(self, teams: List['Team']) -> List[IndRes]:
        # create an ordered list of only scoring runners
        all_scorers: List[IndRes] = [
            deepcopy(ir) for ir in self.individual_results() 
            if ir.team_id in [team.id for team in teams] and ir.team_place <= 7
        ]

        # calc each runner's points
        for idx, ir in enumerate(all_scorers):
            ir.points = idx + 1

        return all_scorers

    def _create_race_result(self, 
        teams: List['Team'],
        all_scorers: List[IndRes]
    ) -> List[TeamRes]:

        # create list of TeamResult objects
        race_result: List[TeamRes] = []
        for team in teams:
            school: School = team.school
            scorers = [ir for ir in all_scorers if ir.team_id==team.id]
            team_result = TeamRes(
                team_id = team.id,
                school_id = school.id,
                school_name = school.short_name,
                school_long_name = school.long_name,
                primary_color = school.primary_color,
                text_color = school.text_color,
                score = sum([r.points for r in scorers[:5]]),
                place = None,
                gender = team.gender if self.gender == 'combo' else '',
                average_time = timify(sum([r.time for r in scorers[:5]]) / 5),
                first_fifth_spread = timify(scorers[4].time - scorers[0].time),
                time_6th = scorers[5].time if len(scorers) > 5 else 999999999,
                scorers=scorers
            )
            race_result.append(team_result)

        # sort teams by score and assign team places
        race_result = sorted(race_result, key=lambda r: (r.score, r.time_6th))
        for idx, team_result in enumerate(race_result):
            team_result.place = idx + 1

        return race_result

    def _update_race_score_table(self, 
        teams: List['Team'], 
        race_result: 
        List['TeamRes']
    ) -> None:
        if self.scoring_type == 'invitational':
            return
        elif len(teams) > 2 or self.is_jv:
            self._delete_race_scores_for_race()
        else:
            self._add_or_update_race_score(teams, race_result)

    def _delete_race_scores_for_race(self) -> None:
        race_scores: List[RaceScore] = (
            RaceScore.query.filter_by(race_id=self.id,).all()
        )
        if race_scores is not None:
            for race_score in race_scores:
                db.session.delete(race_score)
                db.session.commit()
                print(f"Deleted {race_score} from race_score table")

    def _add_or_update_race_score(self, 
        teams: List['Team'], 
        race_result: 
        List['TeamRes']
    ) -> None:
        # since this is a one-on-one matchup, add race_score to db
        winner, loser = race_result[0], race_result[1]

        # get all race_scores associated with this race in db
        race_scores: List[RaceScore] = (
            RaceScore.query.filter_by(race_id=self.id,).all()
        )
        if race_scores is not None:
            # try to find this particular matchup among race_scores
            team_ids = [team.id for team in teams]
            race_score = next((
                rs for rs in race_scores 
                if rs.winner_id in team_ids and rs.loser_id in team_ids
            ), None)

            # if this matchup is found, update it
            if race_score is not None:
                race_score.winner_id = winner.team_id
                race_score.loser_id = loser.team_id
                race_score.winner_score = winner.score
                race_score.loser_score = loser.score
                self._report_on_race_score(race_score)
                db.session.commit()
                return race_result

        # since it is not in database, create race_score and add to db
        race_score = RaceScore(
            race_id=self.id,
            winner_id=winner.team_id,
            loser_id=loser.team_id,
            winner_score=winner.score,
            loser_score=loser.score
        )
        self._report_on_race_score(race_score)
        db.session.add(race_score)
        db.session.commit()

    def _report_on_race_score(self, race_score: RaceScore) -> None:
        print(
            f'     Winner: {Team.query.get(race_score.winner_id).team_name()}'
            f' ({race_score.winner_score})'
        )
        print(
            f'     Loser:  {Team.query.get(race_score.loser_id).team_name()}'
            f' ({race_score.loser_score})'
        )

    def win_loss_table(self, r_results:List[List[TeamRes]]) -> List[WinLossRow]:
        win_loss_table = []
        # calculate win/loss for each team
        team_wins = {team.id: 0 for team in self.complete_teams()}
        team_losses = {team.id: 0 for team in self.complete_teams()}
        for rr in r_results:
            for tr in rr:
                team_wins[tr.team_id] += tr.place == 1
                team_losses[tr.team_id] += tr.place != 1
        
        for team in self.complete_teams():
            tr = next((
                tr for rr in r_results for tr in rr if tr.team_id == team.id
            ), None)
            win_loss_row = WinLossRow(
                team_id = tr.team_id,
                school_id = tr.school_id,
                school_long_name = tr.school_long_name,
                primary_color = tr.primary_color,
                text_color = tr.text_color,
                gender=tr.gender,
                wins = team_wins[team.id],
                losses = team_losses[team.id]
            )
            win_loss_table.append(win_loss_row)

        # sort win loss table
        return sorted(
            win_loss_table, key=lambda r: (r.wins, -r.losses), reverse=True
        )

    def display_name(self):
        use_name_list = ['complete', 'active', 'ready', 'bib']
        fdate = self.date.strftime("%m/%d/%Y")
        location = f" at {self.location.name}" if self.location else ""
        if self.status in use_name_list:
            return f"{self.name} - {self.display_gender()}{location} on {fdate}"
        else:
            return f"Unnamed race{location} on {fdate}"

    def display_name_gender_jv(self) -> str:
        return self.name_f()

    def display_date_name_gender_jv(self) -> str:
        return f"{self.date_f()} | {self.name_f()}"

    def display_name_date_first(self):
        use_name_list = ['complete', 'active', 'ready', 'bib']
        fdate = self.date.strftime("%m/%d/%Y")
        if self.location:
            location = f" at {self.location.name}"
        else:
            location = ""
        if self.status in use_name_list:
            return f"{fdate}: {self.name} - {self.display_gender()}{location}"
        else:
            return f"{fdate}: Unnamed race{location}"

    def display_gender(self):
        return self.gender.capitalize()

    def display_date(self):
        return self.date.strftime("%Y-%m-%d")

    def reverse_date(self):
        return self.date.strftime("%Y/%m/%d")

    def display_date_long(self):
        return self.date.strftime("%B %e, %Y")

    def alphabetized_schools(self):
        return sorted(self.schools, key=lambda s: s.long_name)