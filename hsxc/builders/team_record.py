# external imports
from typing import List, Tuple
from dataclasses import dataclass

# hsxc imports
from hsxc import db
from hsxc.models.race_score import RaceScore
from hsxc.models.team import Team
from hsxc.models.league import League
from hsxc.helpers import CUR_YEAR


@dataclass
class DualRes:
    """Info needed to display result of dual meet page"""
    race_id: int
    race_date: str
    opp_id: int
    school_name: str
    school_id: int
    primary_color: str
    secondary_color: str
    text_color: str
    win_loss: str
    w_l_color: str
    own_score: int
    opp_score: int

@dataclass
class TeamRecord:
    """Info needed to display team record (i.e., all dual meet results)"""
    team_id: int
    gender: str
    year: int
    school_id: int
    school_name: str
    primary_color: str
    secondary_color: str
    text_color: str
    total_wins: int
    total_losses: int
    league_wins: int
    league_losses: int
    rank: Tuple[float, float, int, str]
    dual_results: List[DualRes]

@dataclass
class LeagueStandings:
    """Info needed to display league standings"""
    league_id: int
    league_name: str
    year: int
    gender: str
    team_records: List[TeamRecord]


class TeamRecordBuilder:

    def __init__(self, team_id: int) -> None:
        self.team_id = team_id
        self.team = Team.query.get(team_id)
        self.league = self.team.school.league
        self.dual_wins: List[RaceScore] = []
        self.dual_losses: List[RaceScore] = []
        self.total_duals: List[RaceScore] = []
        self.dual_results: List[DualRes] = []
        self.league_wins: int = 0
        self.league_losses: int = 0
        self.rank: Tuple[float, float, int, str] = (0, 0, 0, '')

    def build(self) -> TeamRecord:
        print(f'  building team record for: {self.team}')

        self._get_dual_wins_and_losses()
        self._build_dual_res_objects()
        self._update_teams_table_with_wins_losses()
        self._calculate_rank_for_sorting_results()

        # create and return TeamRecord object
        return TeamRecord(
            team_id=self.team_id,
            gender=self.team.gender_f(),
            year=self.team.year,
            school_id=self.team.school.id,
            school_name=self.team.school.short_name,
            primary_color=self.team.school.primary_color,
            secondary_color=self.team.school.secondary_color,
            text_color=self.team.school.text_color,
            total_wins=len(self.dual_wins),
            total_losses=len(self.dual_losses),
            league_wins=self.league_wins,
            league_losses=self.league_losses,
            rank=self.rank,
            dual_results=self.dual_results,
        )

    def _get_dual_wins_and_losses(self) -> None:
        dual_wins = (RaceScore.query.filter_by(winner_id=self.team_id).all())
        dual_losses = (RaceScore.query.filter_by(loser_id=self.team_id).all())
        all_duals = dual_wins + dual_losses
        self.dual_wins = dual_wins
        self.dual_losses = dual_losses
        self.total_duals = all_duals

    def _build_dual_res_objects(self) -> None:
        # loop over dual meets and build DualRes objects
        dual_results, league_wins, league_losses = [], 0, 0
        for rs in self.total_duals:
            is_win = rs.winner == self.team
            opp: Team = rs.loser if is_win else rs.winner
            res = DualRes(
                race_id=rs.race.id,
                race_date=rs.race.date_f(),
                opp_id=opp.id,
                school_name=opp.school.short_name,
                school_id=opp.school.id,
                primary_color=opp.school.primary_color,
                secondary_color=opp.school.secondary_color,
                text_color=opp.school.text_color,
                win_loss='Win' if is_win else 'Loss',
                w_l_color='green' if is_win else 'red',
                own_score=rs.winner_score if is_win else rs.loser_score,
                opp_score=rs.loser_score if is_win else rs.winner_score,
            )
            dual_results.append(res)
            if opp.school.league == self.league:
                league_wins += 1 if is_win else 0
                league_losses += 1 if not is_win else 0
        dual_results.sort(key=lambda dr: dr.race_date, reverse=True)

        # store results
        self.dual_results = dual_results
        self.league_wins = league_wins
        self.league_losses = league_losses

    def _update_teams_table_with_wins_losses(self) -> None:
        # update wins and losses in teams table
        self.team.wins = len(self.dual_wins)
        self.team.losses = len(self.dual_losses)
        self.team.league_wins = self.league_wins
        self.team.league_losses = self.league_losses
        db.session.commit()

    def _calculate_rank_for_sorting_results(self) -> None:
        # calculate win percentages
        total_duals = len(self.total_duals)
        league_duals = self.league_wins + self.league_losses
        total_win_pct = (
            0.001 if total_duals == 0 else len(self.dual_wins) / total_duals
        )
        league_win_pct = (
            0.001 if league_duals == 0 else self.league_wins / league_duals
        )

        # store rank (a score designed to sort dual results in logical order)
        self.rank = (
            -league_win_pct, 
            -total_win_pct, 
            -len(self.dual_wins), 
            self.team.school.short_name
        )

class LeagueStandingsBuilder:

    def __init__(self, league_id: int) -> None:
        self.league_id = league_id
        self.league = League.query.get(league_id)

    def update_all_team_records(self, year=CUR_YEAR) -> None:
        for gender in ['boys', 'girls']:
            self.build(year, gender)

    def build(self, year: int, gender: str) -> List[TeamRecord]:
        print(
            f'\n building league standings: {year} {self.league.short_name} '
            f'{gender}'
        )

        # get all teams for year
        teams = [
            team
            for school in self.league.schools
            for team in school.teams
            if team.year == year and team.gender == gender.lower()
        ]

        team_records = [TeamRecordBuilder(team.id).build() for team in teams]
        team_records.sort(key=lambda tr: tr.rank)

        return LeagueStandings(
            league_id=self.league_id,
            league_name=self.league.short_name,
            year=year,
            gender=gender,
            team_records=team_records,
        )

