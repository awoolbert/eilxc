# external imports
from typing import List, Dict, Tuple, Set, Optional
from flask_login import current_user
from datetime import datetime

# hsxc imports
from hsxc import db
from hsxc.models.race import Race
from hsxc.models.course import Course
from hsxc.models.location import Location
from hsxc.models.runner import Runner
from hsxc.models.result import Result
from hsxc.models.league import League
from hsxc.models.school import School
from hsxc.models.team import Team
from hsxc.helpers import CUR_YEAR


class HypotheticalRaceBuilder:
    def __init__(self, 
        gender: str, 
        times_to_use: str,
        scoring_type: str,
        schools: List[School],
    ) -> None:
        self.gender: str = gender
        self.times_to_use: str = times_to_use
        self.scoring_type: str = scoring_type
        self.schools: List[School] = schools

    def build(self) -> Race:
        self._create_race()
        self._set_group_id()
        self._set_name()
        self._set_teams()
        self._set_schools()
        self._set_runners()
        self._associate_times_with_runners()
        self._limit_runners()
        self._set_results()
        return self.race

    def _create_race(self) -> None:
        new_race = Race(
            user_id=current_user.id, 
            date=datetime.now(),
            gender=self.gender,
            scoring_type=self.scoring_type,
            status='complete',
            location_id=self._get_location_id(),
            course_id=self._get_course_id(),
            group_id=None,
            is_jv=False,
        )
        db.session.add(new_race)
        db.session.commit()
        self.race = new_race

    def _set_group_id(self) -> None:
        current_max_id = db.session.query(db.func.max(Race.group_id)).scalar()
        self.race.group_id = current_max_id + 1
        db.session.commit()

    def _get_location_id(self) -> int:
        locations: List[Location] = Location.query.all()
        return next((l.id for l in locations if 'Hypothetical' in l.name),1)

    def _get_course_id(self) -> int:
        courses: List[Course] = Course.query.all()
        return next((c.id for c in courses if 'Hypothetical' in c.name),1)

    def _set_name(self) -> None:
        base_name = f'Hypothetical Race'
        if self.times_to_use == 'pr_current_year':
            time_method = 'Current Year PR'
        elif self.times_to_use == 'pr':
            time_method = 'All Time PR'
        elif self.times_to_use == 'seed_time':
            time_method = 'Median of Last 3 Races'
        self.race.name = f'{base_name} (Based on {time_method})'
        db.session.commit()

    def _set_teams(self) -> None:
        self.teams: List[Team] = [
            team 
            for school in self.schools 
            for team in school.current_year_teams()
            if team.gender == self.gender
        ]
        for team in self.teams:
            self.race.teams.append(team)
            db.session.commit()

    def _set_schools(self) -> None:
        for school in self.schools:
            self.race.schools.append(school)
            db.session.commit()

    def _set_runners(self) ->None:
        self.runners: List[Runner] = [
            runner 
            for team in self.teams 
            for runner in team.runners
        ]

    def _associate_times_with_runners(self) -> None:
        if self.times_to_use == 'pr_current_year':
            runners_to_times: Tuple[Runner, int] = [
                (runner, runner.pr_year(CUR_YEAR)) 
                for runner in self.runners
            ]
        elif self.times_to_use == 'pr':
            runners_to_times: Tuple[Runner, int] = [
                (runner, runner.pr()) 
                for runner in self.runners
            ]
        elif self.times_to_use == 'seed_time':
            runners_to_times: Tuple[Runner, int] = [
                (runner, runner.seed_time) 
                for runner in self.runners
            ]
        else:
            raise ValueError('Invalid times_to_use value')
        
        self.runner_times: List[Tuple[Runner, int]] = [
            runner_to_time for runner_to_time in runners_to_times 
            if runner_to_time[1] is not None
        ]

    def _limit_runners(self) -> None:
        # sort runners by time
        self.runner_times.sort(key=lambda tup: tup[1])

        # limit runners to top 7 per team
        team_count = {team.id: 0 for team in self.teams}
        new_runner_times = []
        for runner_time in self.runner_times:
            runner = runner_time[0]
            if team_count[runner.current_year_team().id] < 9:
                team_count[runner.current_year_team().id] += 1
                new_runner_times.append(runner_time)
        self.runner_times = new_runner_times

    def _set_results(self) -> None:
        place = 1
        for runner, time in self.runner_times:
            res = Result(
                place=place,
                runner_id=runner.id,
                race_id=self.race.id,
                team_id=runner.current_year_team().id,
                time=time,
                status='c'
            )
            db.session.add(res)
            db.session.commit()





