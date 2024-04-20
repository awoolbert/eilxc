# external imports
from datetime import datetime
from statistics import median
from typing import List, Optional

# hsxc imports
from hsxc import db
from hsxc.helpers import timify, CUR_YEAR
from sqlalchemy import desc
from .associations import team_roster


class Runner(db.Model):
    __tablename__ = 'runners'

    id = db.Column(db.Integer, primary_key = True)
    first_name = db.Column(db.String(32))
    last_name = db.Column(db.String(32))
    grad_year = db.Column(db.Integer, nullable=False)
    seed_time = db.Column(db.Integer)
    teams = db.relationship('Team', secondary=team_roster)
    results = db.relationship('Result', backref='runner', lazy=True)

    def __init__(self, first_name, last_name, grad_year, seed_time):
        max_id = Runner.query.order_by(desc(Runner.id)).first().id
        self.id = max_id + 1
        self.first_name = first_name
        self.last_name = last_name
        self.grad_year = grad_year
        self.seed_time = seed_time

    def __repr__(self):
        return (
            f"id:{self.id} {self.first_name} {self.last_name} "
            f"{self.school_name()} {self.gender_code()} {self.grad_year}"
        )

    def to_dict(self):
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'grad_year': self.grad_year,
            'seed_time': self.seed_time,
        }

    def was_removed(self):
        """ was runner previously deleted from a team but not yet graduated """
        if self.grad_year <= CUR_YEAR - 1:
            return False
        for team in self.teams:
            if team.year == CUR_YEAR:
                return False
        return True

    def school_name(self):
        # uses the most recent team to handle the corner case in which the
        # runner has changed schools
        if self.teams:
            return self.teams[-1].school.short_name
        else:
            return ''

    def get_school(self):
        # uses the most recent team to handle the corner case in which the
        # runner has changed schools
        return self.teams[-1].school if self.teams else ''

    def get_gender(self):
        # uses the most recent team to handle the corner case in which the
        # runner has changed schools
        if self.teams:
            return self.teams[-1].gender
        else:
            return ''

    def gender_code(self):
        if self.teams:
            if self.teams[-1].gender == 'girls':
                return 'F'
            return 'M'
        else:
            return ''

    @property
    def gender(self):
        return self.get_gender()

    def res_count(self, year:int = None):
        if year is not None:
            return len([
                r for r in self.results 
                if r.status=='c' and r.race.date.year == year
            ])
        return len(self.completed_results())

    def update_seed_time(self):
        """
        Uses the median of the last 3 races (using course adjusted times)

        Returns: int 5K time in miliseconds
        """
        # capture current seed time before updating
        old = self.display_seed_time()

        # get list of complete results
        sorted_results = self.sorted_results()

        # if runner has no race results, do not alter seed time
        if not sorted_results:
            return self.seed_time

        # consider at most the last 3 races
        sorted_results = sorted_results[0: min(3, len(sorted_results))]

        # adjust times to consistent 5K distance
        adj_times = [res.adj_time() for res in sorted_results]

        # update and return
        self.seed_time = median(adj_times)
        db.session.commit()

        # display change in seed time
        new = self.display_seed_time()
        print(f'updated {self.display_name()} from {old} to {new}')
        return self.seed_time

    def display_seed_time(self):
        return timify(self.seed_time)

    def display_name(self):
        return f"{self.first_name} {self.last_name}"

    def name(self):
        return f"{self.first_name} {self.last_name}"

    def last_first(self):
        return f"{self.last_name}, {self.first_name}"

    def name_plus_year(self):
        return f"{self.display_name()} {self.grad_year}"

    def sorted_results(self):
        results = self.completed_results()
        if results:
            results = sorted(results, key=lambda r: r.race.reverse_date(),
                                      reverse=True)
        return results

    def minutes(self):
        return int(self.seed_time / 1000 / 60.0)

    def seconds(self):
        mins = int(self.seed_time / 1000 / 60.0)
        secs = self.seed_time / 1000 - mins * 60
        return int(secs)

    def completed_results(self):
        return [res for res in self.results if res.status == 'c']

    def incomplete_results(self):
        return [res for res in self.results if res.status != 'c']

    def current_year_team(self):
        if self.teams is None or len(self.teams) == 0:
            print(f'{self} is not currently on a team')
            return False

        for team in self.teams:
            if team.year == CUR_YEAR:
                print(f'{self} is currently on team:{team}')
                return team

    def delete_not_started_results(self):
        # delete all results that have a status of 'n'
        for res in self.results:
            if res.status == 'n':
                db.session.delete(res)

    def pr(self) -> Optional[int]:
        # return the runner's PR for all time
        if self.results:
            return min([res.adj_time() for res in self.results])
        else:
            return None
        
    def pr_year(self, year: int) -> Optional[int]:
        if not self.results:
            return None
        year_results = [
            res for res in self.results 
            if res.race.date.year == year and res.status == 'c'
        ]
        if year_results:
            return min([res.adj_time() for res in year_results])
        else:
            return None

    @property    
    def nickname(self):
        if '(' in self.first_name and ')' in self.first_name:
            open_paren = self.first_name.index('(')
            close_paren = self.first_name.index(')')
            return self.first_name[open_paren + 1: close_paren]
        return self.first_name