from eilxc import db,login_manager, app
from eilxc.helpers import *
from datetime import datetime
from werkzeug.security import generate_password_hash,check_password_hash
from flask_login import UserMixin
from flask import url_for
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from sqlalchemy import collate, update, func, asc, desc
from eilxc.helpers import *
import math
import statistics
from itertools import combinations
from pprint import pprint
import os
import time


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


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


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key = True)
    first_name = db.Column(db.String(32))
    last_name = db.Column(db.String(32))
    email = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    leagues_managed = db.relationship('League', secondary=league_managers)
    schools_coached = db.relationship('School', secondary=school_coaches)
    setups = db.relationship('Race', backref='user', lazy=True)

    def __init__(self, first_name, last_name, email, password):
        max_id = User.query.order_by(desc(User.id)).first().id
        self.id = max_id + 1
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.password_hash = generate_password_hash(password)

    def check_password(self,password):
        return check_password_hash(self.password_hash,password)

    def get_reset_token(self, expires_sec=1800):
        s = Serializer(app.config['SECRET_KEY'], expires_sec)
        return s.dumps({'user_id': self.id}).decode('utf-8')

    def is_administrator(self):
        return True if self.id < 4 else False

    def races_ready_to_start(self):
        return [race for race in self.setups if race.status == 'ready']

    def races_in_setup(self):
        return [
            race for race in self.setups
            if race.status != 'complete'
            and race.status != 'ready'
        ]

    def display_name(self):
        return f'{self.first_name} {self.last_name}'


    @staticmethod
    def verify_reset_token(token):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token)['user_id']
        except:
            return None
        return User.query.get(user_id)

    def __repr__(self):
        return f"id:{self.id}, email:{self.email}"


class League(db.Model):
    __tablename__ = 'leagues'

    id = db.Column(db.Integer, primary_key = True)
    long_name = db.Column(db.String(64), nullable=False)
    short_name = db.Column(db.String(16), nullable=False)
    schools = db.relationship('School', backref='league', lazy=True)
    managers = db.relationship('User', secondary=league_managers)

    def __init__(self, long_name, short_name):
        max_id = League.query.order_by(desc(League.id)).first().id
        self.id = max_id + 1
        self.long_name = long_name
        self.short_name = short_name

    def __repr__(self):
        return f"id:{self.id}, League:{self.long_name} ({self.short_name})"

    def update_standings(self, year=datetime.today().year):
        """
        (Re)calculates the wins and losses for each team in the league for a
        given year. Does this by rescoring every race in which those teams
        participated. Invitationals are scored as a series of dual races to
        produce simple wins and losses.

        Return: nothing
        """
        # start timer
        t0 = time.time()

        # print route beginning
        print(f'\n----------- calculating league standings for: '
              f'{self.short_name} -----------')

        # get all teams for year
        teams = [
            team
            for school in self.schools
            for team in school.teams
            if team.year == year
        ]

        # clear previous wins and losses
        for team in teams:
            team.wins = 0
            team.losses = 0
            db.session.commit()

        # create races: set of all races involving a leauge team
        races = {
            race
            for team in teams
            for race in team.races
            if race.status == 'complete'
        }

        # create a list of all unique dual race results involving a leauge team
        league_race_result = [
            {'race': race,
             'team': team_score['team'],
             'place': team_score['place']
            }
            for race in races
            for team_pair in [
                combo
                for combo in list(combinations(race.complete_teams(), 2))
                if combo[0].gender == combo[1].gender and
                (combo[0].school.league == self or
                 combo[1].school.league == self)
            ]
            for team_score in race.score_race(team_pair)
            if team_score['team'].school.league == self
        ]

        # loop through league race results and increment each team's wins/losses
        for race_result in league_race_result:
            race_result['team'].wins += 1 if race_result['place'] == 1 else 0
            race_result['team'].losses += 1 if race_result['place'] == 2 else 0
        db.session.commit()

        # print results
        for team in teams:
            print(f'team:{team} W:{team.wins} - {team.losses}:L')

        # stop timer and display processing time
        t1 = time.time()
        print(f'league.standings() required: {t1 - t0}')

        return True

    def standings(self, year=datetime.today().year):
        """
        Aggregates all the information needed to display the standings for all
        teams in the league for the given year

        Returns: {'girls': [{'team': team object,
                            'wins': int number of wins,
                            'losses': int number of losses,
                            'percent': int win percentage}]
                  'boys':  [{'team': team object,
                            'wins': int number of wins,
                            'losses': int number of losses,
                            'percent': int win percentage}]}
                  }
        """
        # start timer
        t0 = time.time()

        # print route beginning
        print(f'\n----------- creating league standings for: {self.short_name} '
              f'-------------')

        # create the league_standings object which will be returned
        league_standings = {'girls': [],
                            'boys': []}

        # get all teams for year
        teams = [
            team
            for school in self.schools
            for team in school.teams
            if team.year == year
        ]

        # fill league standings object with data from every team
        for team in teams:
            league_standings[team.gender].append(
                {
                    'team': team,
                    'wins': team.wins,
                    'losses': team.losses,
                    'percent': (int(round( 100 * (team.wins /
                                                (team.wins + team.losses))))
                                if team.wins + team.losses > 0
                                else '')
                }
            )

        # stop timer and display processing time
        t1 = time.time()
        print(f'league.standings() required: {t1 - t0}')

        return league_standings


class School(db.Model):
    __tablename__ = 'schools'

    leagues = db.relationship(League)

    id = db.Column(db.Integer, primary_key = True)
    long_name = db.Column(db.String(64), nullable=False)
    short_name = db.Column(db.String(16), nullable=False)
    primary_color = db.Column(db.String(10))
    secondary_color = db.Column(db.String(10))
    text_color = db.Column(db.String(10))
    city = db.Column(db.String(32))
    state_abbr = db.Column(db.String(2))
    league_id = db.Column(
        db.Integer, db.ForeignKey('leagues.id'), nullable=False
    )
    teams = db.relationship('Team', backref='school', lazy=True)
    coaches = db.relationship('User', secondary=school_coaches)
    races = db.relationship('Race', backref='host_school', lazy=True)
    locations = db.relationship('Location', secondary=school_locations)
    all_races = db.relationship('Race', secondary=race_schools)

    def __init__(self, long_name, short_name, city, state_abbr, league_id,
                 primary_color, secondary_color, text_color):
        max_id = School.query.order_by(desc(School.id)).first().id
        self.id = max_id + 1
        self.long_name = long_name
        self.short_name = short_name
        self.city = city
        self.state_abbr = state_abbr
        self.league_id = league_id
        self.primary_color = primary_color
        self.secondary_color = secondary_color
        self.text_color = text_color

    def __repr__(self):
        return f"{self.short_name}"

    def get_team_gender(self):
        if self.teams:
            return 1 if self.teams[0].gender == 'girls' else 2
        else:
            return 0

    def current_year_teams(self):
        year = datetime.today().year
        return [team for team in self.teams if team.year == year]

    def has_current_year_results(self):
        for team in self.current_year_teams():
            for race in team.races:
                if race.status == 'complete' and team.has_five_runners(race):
                    return True
        return False

    def get_team(self, year, gender):
        return Team.query.filter_by(school_id=self.id,
                                    year=year,
                                    gender=gender).first()

    def img_filename(self):
        """
        Build the filename of the logo graphic from the school short name.

        Return: string representing the filename
        """
        fname = f'img/{self.short_name}-logo.png'.lower()
        fname = fname.replace(' ', '')
        fname = fname.replace('st.', 'st')
        fname = fname.replace('&', '')
        fname = fname.replace("'", "")
        return fname

    def has_image(self):
        return os.access(f'eilxc/static/{self.img_filename()}', os.F_OK)


class Team(db.Model):
    __tablename__ = 'teams'

    schools = db.relationship(School)

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
    results = db.relationship('Result', backref='team', lazy=True)
    runners = db.relationship('Runner', secondary=team_roster)
    races = db.relationship('Race', secondary=race_teams)
    participants = db.relationship('Participant', backref='team', lazy=True)

    def __init__(self, gender, year, school_id):
        max_id = Team.query.order_by(desc(Team.id)).first().id
        self.id = max_id + 1
        self.gender = gender
        self.year = year
        self.school_id = school_id

    def __repr__(self):
        return (f"{self.school.short_name} {self.display_gender()} "
                f"'{str(self.year)[2:4]}")

    def display_gender(self):
        """
        Returns: str "Girls" or "Boys"
        """
        return self.gender[0].upper() + self.gender[1:]

    def gender_code(self):
        """
        Returns: int 1 if girls team, 2 if boys team
        """
        return 1 if self.gender == 'girls' else 2

    def alphabetized_runners(self):
        runners = sorted(self.runners, key=lambda r: r.first_name)
        return sorted(runners, key=lambda r: r.last_name)

    def completed_races(self):
        return [
            r for r in self.races
            if r.status == 'complete'
            and self.has_five_runners(r)
        ]

    def has_five_runners(self, race):
        race_results = Result.query.filter_by(race_id=race.id,
                                              team_id=self.id).all()
        if len(race_results) >= 5:
            return True
        else:
            return False

    def team_6th_time(self, race):
        results = Result.query.filter_by(race_id=race.id,
                                         team_id=self.id,
                                         status='c').all()
        results = sorted(results, key=lambda r: r.time)
        return results[5].time if len(results) > 5 else 99999999

    def season_summary(self):
        """
        Summarizes the season's race results

        Returns: {
            'wins': int number of races won,
            'losses': int number of races lost,
            'gender': str "Girls" or "Boys",
            'srr': obj season race results object
        }
        """
        srr = self.season_race_results()
        wins = sum(1 for r in srr if r['outcome'] == 'Win')
        losses = sum(1 for r in srr if r['outcome'] == 'Loss')
        return {
            'wins': wins,
            'losses': losses,
            'gender': self.display_gender(),
            'srr': srr
        }

    def season_race_results(self):
        """
        Summary of each completed race in a season

        Returns: [{
            'race_id': int race.id,
            'race_date': str race.display_date(),
            'outcome': int outcome,
            'opponent_id': int opponent.school.id,
            'opponent_short_name': str opponent.school.short_name,
            'opponent_primary_color': str opponent.school.primary_color,
            'opponent_text_color': str opponent.school.text_color,
            'own_score': int own_score,
            'opp_score': int opp_score
        }]
        """
        print(f'working on season race results for: {self}')
        # create return list
        srr = []

        # get all completed races and print
        completed_races = self.completed_races()
        print(f'found the following races: {completed_races}')

        # evaluate each race (including all pair-wise combinations if the race
        # is an invitational) and append the race result object to srr
        for race in completed_races:
            print(f'\nevaluating: {race}')

            # create list of all opponents in this race
            opponents = [
                t for t in race.teams
                if t is not self
                and t.has_five_runners(race)
            ]

            # for each opponent, score as a separte race and store results
            for opponent in opponents:
                results = race.score_race([self,opponent])
                for result in results:
                    if result['team'] == self:
                        outcome = "Win" if result['place'] == 1 else "Loss"
                        own_score = result['score']
                    else:
                        opp_score = result['score']
                srr.append({
                    'race_id': race.id,
                    'race_date': race.display_date(),
                    'outcome': outcome,
                    'opponent_id': opponent.school.id,
                    'opponent_short_name': opponent.school.short_name,
                    'opponent_primary_color': opponent.school.primary_color,
                    'opponent_text_color': opponent.school.text_color,
                    'own_score': own_score,
                    'opp_score': opp_score
                })

        # sort race results in reverse chonological order
        srr = sorted(srr, key=lambda r: r['race_date'], reverse=True)

        return srr


class Runner(db.Model):
    __tablename__ = 'runners'

    id = db.Column(db.Integer, primary_key = True)
    first_name = db.Column(db.String(32))
    last_name = db.Column(db.String(32))
    grad_year = db.Column(db.Integer, nullable=False)
    seed_time = db.Column(db.Integer)
    teams = db.relationship('Team', secondary=team_roster)
    results = db.relationship('Result', backref='runner', lazy=True)
    participants = db.relationship('Participant', backref='runner', lazy=True)

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

    def was_removed(self):
        """ was runner previously deleted from a team but not yet graduated """
        if self.grad_year <= datetime.now().year - 1:
            return False
        for team in self.teams:
            if team.year == datetime.now().year:
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
        if self.teams:
            return self.teams[-1].school
        else:
            return ''

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

    def update_seed_time(self):
        """
        Uses the median of the last 3 races (using pace, not time to adjust for
        different length courses) to set determine the estimated 5K time

        Returns: int 5K time in miliseconds
        """
        # capture current seed time before updating
        old = self.display_seed_time()

        """ ************************************************************** """
        """ ************************************************************** """
        # TEMPORARY CODE: allows multiple races without distorting seed times
        # get list of complete results
        # sorted_results = [
        #     r for r in self.results if r.status == 'c'
        #                             and r.race.reverse_date() < "2020/01/01"
        # ]
        # PERMANENT CODE:
        # get list of complete results
        sorted_results = [r for r in self.results if r.status == 'c']
        """ ************************************************************** """
        """ ************************************************************** """

        # if runner has not race results, do not alter seed time
        if not sorted_results:
            return self.seed_time

        # sort from most to least recent
        sorted_results.sort(key=lambda x: x.race.date, reverse=True)

        # consider at most the last 3 races
        if len(sorted_results) > 3:
            sorted_results = sorted_results[0:4]

        # adjust times to consistent 5K distance
        adj_times = [
            res.time / res.race.course.distance * 5
            for res in sorted_results
        ]

        # update and return
        self.seed_time = statistics.median(adj_times)
        db.session.commit()

        # display change in seed time
        new = self.display_seed_time()
        print(f'updated {self.display_name()} from {old} to {new}')
        return self.seed_time

    def display_seed_time(self):
        return timify(self.seed_time)

    def display_name(self):
        return f"{self.first_name} {self.last_name}"

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

    def current_year_team(self):
        if self.teams:
            for team in self.teams:
                if team.year == datetime.today().year:
                    print(f'{self} is currently on team:{team}')
                    return team

        print(f'{self} is not currently on a team')
        return False

    def delete_not_started_results(self):
        # delete all results that have a status of 'n'
        for res in self.results:
            if res.status == 'n':
                db.session.delete(res)


class Location(db.Model):
    __tablename__ = 'locations'

    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(32))
    street_address = db.Column(db.String(64))
    city = db.Column(db.String(32))
    state_abbr = db.Column(db.String(2))
    zip = db.Column(db.String(5))
    courses = db.relationship('Course', backref='location', lazy=True)
    races = db.relationship('Race', backref='location', lazy=True)
    schools = db.relationship('School', secondary=school_locations)

    def __init__(self, name, street_address, city, state_abbr, zip):
        max_id = Location.query.order_by(desc(Location.id)).first().id
        self.id = max_id + 1
        self.name = name
        self.street_address = street_address
        self.city = city
        self.state_abbr = state_abbr
        self.zip = zip

    def __repr__(self):
        return (f"id:{self.id}  {self.name}")


class Course(db.Model):
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(32))
    description = db.Column(db.Text)
    distance = db.Column(db.Float)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    races = db.relationship('Race', backref='course', lazy=True)

    def __init__(self, name, description, distance, location_id):
        max_id = Course.query.order_by(desc(Course.id)).first().id
        self.id = max_id + 1
        self.name = name
        self.description = description
        self.distance = distance
        self.location_id = location_id

    def __repr__(self):
        return (f"id:{self.id}  {self.name}")

    def meters(self):
        return f'{int(self.distance * 1000):,}'

    def miles(self):
        return self.distance * 0.621371


class Race(db.Model):
    __tablename__ = 'races'

    id = db.Column(db.Integer, primary_key = True)
    group_id = db.Column(db.Integer)
    name = db.Column(db.String(128))
    date = db.Column(db.DateTime)
    gender = db.Column(db.String(5))
    temperature = db.Column(db.Float)
    weather = db.Column(db.String(32))
    conditions = db.Column(db.String(32))
    scoring_type = db.Column(db.String(16))
    status = db.Column(db.String(8))
    host_school_id = db.Column(db.Integer, db.ForeignKey('schools.id'))
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    results = db.relationship('Result', backref='race', lazy=True)
    participants = db.relationship('Participant', backref='race', lazy=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    schools = db.relationship('School', secondary=race_schools)
    teams = db.relationship('Team', secondary=race_teams)

    def __init__(self, user_id, date):
        max_id = Race.query.order_by(desc(Race.id)).first().id
        self.id = max_id + 1
        self.date = date
        self.user_id = user_id
        self.status = 'new'
        self.scoring_type = 'invitational'

    def __repr__(self):
        fdate = self.date.strftime("%Y-%m-%d")
        return f"{fdate}: {self.name}"

    def display_name(self):
        use_name_list = ['complete', 'active', 'ready', 'bib']
        fdate = self.date.strftime("%m/%d/%Y")
        if self.location:
            location = f" at {self.location.name}"
        else:
            location = ""
        if self.status in use_name_list:
            return f"{self.name} - {self.display_gender()}{location} on {fdate}"
        else:
            return f"Unnamed race{location} on {fdate}"

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
        return self.gender[0].upper() + self.gender[1:]

    def display_date(self):
        return self.date.strftime("%m/%d/%Y")

    def team_count(self):
        return len(self.complete_teams())

    def reverse_date(self):
        return self.date.strftime("%Y/%m/%d")

    def display_date_long(self):
        return self.date.strftime("%B %d, %Y")

    def complete_teams(self):
        return [team for team in self.teams if team.has_five_runners(self)]

    def all_runners(self):
        return [res.runner for res in self.results]

    def sorted_results(self):
        return sorted([res for res in self.results if res.time],
                      key=lambda r: r.time)

    def group_races(self):
        return (
            Race.query.filter_by(group_id=self.group_id)
                      .order_by(asc(Race.id))
                      .all()
        )

    def previous_group_race_id(self):
        indx = self.group_races().index(self)
        if indx == 0:
            return None
        else:
            return self.group_races()[indx - 1].id

    def next_group_race_id(self):
        indx = self.group_races().index(self)
        if indx == len(self.group_races()) - 1:
            return None
        else:
            return self.group_races()[indx + 1].id

    def other_group_races(self):
        group_races = Race.query.filter_by(group_id=self.group_id).all()
        return [race for race in group_races if race.id != self.id]

    def results_summary(self, force_dual=False):
        """
        Return: result_obj, dict of dicts needed to display results
                result_obj = {
                    ind_results: list of individual_result dicts that store
                        information needed to display rows in individual results
                        portion of results.html
                    race_results: list of team_results dicts, each of which
                        contain information to display team scores portion
                        of results.html (e.g., score, scoring runners, 1-5
                        spread, average_time, etc.)
                    race: race object from database
                    win_loss_table: dict with information needed to display
                        win_loss_table portion of results.html.  This is only
                        needed for races of > 2teams which are scored as a
                        series of dual races
                }
        """

        # Get race object from database
        print(f'preparing results for: {self}')

        # Get list of results for this race from the database
        temp_ind_results = self.sorted_results()

        # Build ind_results: a list of python results objects that conveniently
        # bring together data needed to score and display the individual results
        ind_results = []  # List to hold new results objects
        place = 1
        points = 1
        for r in temp_ind_results:
            runner = {'place':place,
                      'bib':r.bib,
                      'id': r.id,
                      'runner': r.runner,
                      'name': r.runner.display_name(),
                      'class': r.runner.grad_year,
                      'school': r.team.school,
                      'team': r.team,
                      'time': r.time,
                      'time_f': r.display_time(),
                      'pace_f': r.display_pace(),
                      'team_place': r.team_place()
                      }
            place += 1
            if runner['team_place'] <= 7 and r.team.has_five_runners(self):
                runner['points'] = points
                points += 1
            else:
                runner['points'] = None
            ind_results.append(runner)

        # Build list of teams that competed and had at least 5 runners
        team_list = self.complete_teams()

        # Determine if race is invitational or dual and score as one race or
        # many one-vs-one races.  If latter, aggregate the overall wins/losses
        # into a summary table
        race_results = []
        win_loss_table = []
        if not force_dual and self.scoring_type == 'invitational':
            # Produce a single result with potentially many teams
            race_results.append(self.score_race(team_list))

        else:
            # Generate list of team_lists representing all pair-wise
            # combinations of teams in the original team_list
            scoring_combinations = list(combinations(team_list, 2))

            # Remove cross gender combinations (needed for "combo" scoring_type)
            scoring_combinations = [
                c for c in scoring_combinations
                if c[0].gender == c[1].gender
            ]

            # Loop through team combinations and score each as separate race
            for combo in scoring_combinations:
                race_results.append(self.score_race(combo))

            # If team_list longer than 2, calculate the win/loss for each team
            if len(team_list) > 2 or force_dual:
                for team in team_list:
                    appendGender = ''
                    if self.gender == 'combo':
                        appendGender = (
                            ' (Girls)' if team.gender == 'girls' else ' (Boys)'
                        )
                    team_win_loss = {
                        'team':team,
                        'school':team.school,
                        'wins':0,
                        'losses':0,
                        'appendGender': appendGender
                    }
                    for result in race_results:
                        if result[0]['team'] == team:
                            team_win_loss['wins'] += 1
                        elif result[1]['team'] == team:
                            team_win_loss['losses'] +=1
                    win_loss_table.append(team_win_loss)
                win_loss_table = sorted(
                    win_loss_table, key=lambda x: (x['losses'], x['wins'])
                )

        return {'ind_results': ind_results,
                'race_results': race_results,
                'race': self,
                'win_loss_table': win_loss_table}

    def score_race(self, teams):
        """
        Returns: [{'team': team object,
                   'school': school object,
                   'place': int team's place in race,
                   'score': int team's final score,
                   'time_6th': int time of 6th place runner,
                   'appendGender': str "(Girls)" or "(Boys)" if combo race,
                   'average_time': int top 5 runner average time,
                   '1_5_spread': int spread between team's 1st and 5th runner,
                   'team_scorers': [{'name': ,
                                     'result_id': ,
                                     'runner_id': ,
                                     'time': ,
                                     'time_f': ,
                                     'points': ,
                                     'team_place': ,
                                     }]
                   }]
        """
        # eliminate any teams that do not have 5 scoring runners
        teams = [team for team in teams if team.has_five_runners(self)]
        print(f'  scoring race:{self.id} with teams: {teams}')

        # create list of only scoring runners
        scorers = [
            res for res in self.sorted_results()
            if res.team in teams
            and res.team_place() < 8
        ]

        # Build team_results: a list of result objects for each team in race
        # which conveniently stores team level information needed to display
        # overall and team vs team results
        team_results = [
            {
                'team': team,
                'school': team.school,
                'time_6th': team.team_6th_time(self),
                'appendGender': ('' if self.gender != 'combo'
                                    else ' (Girls)' if team.gender == 'girls'
                                                    else ' (Boys)'),
                'scorers': [
                    {
                    'name': res.runner.display_name(),
                    'result_id': res.id,
                    'runner_id': res.runner.id,
                    'time': res.time,
                    'time_f': res.display_time(),
                    'points': indx + 1,
                    'team_place': res.team_place()
                    }
                    for indx, res in enumerate(scorers)
                    if res.team == team
                ]
            }
            for team in teams
        ]

        # Calculate and store score, 1-5 spread, and average time
        for team in team_results:
            team['score'] = sum(
                s['points'] for s in team['scorers'] if s['team_place'] < 6
            )
            team['1_5_spread'] = timify(
                team['scorers'][4]['time'] - team['scorers'][0]['time']
            )
            team['average_time'] = timify(statistics.mean(
                s['time'] for s in team['scorers'] if s['team_place'] < 6
            ))

        #  Sort teams by 'score' using time_6th as tie-breaker
        team_results = sorted(
            team_results, key=lambda tr: (tr['score'], tr['time_6th'])
        )

        # Record the team's place
        p = 1
        for team in team_results:
            team['place'] = p
            p += 1

        # Return the team_results
        return team_results


class Result(db.Model):
    __tablename__ = 'results'

    id = db.Column(db.Integer, primary_key = True)
    bib = db.Column(db.Integer)
    time = db.Column(db.Integer)
    place = db.Column(db.Integer)
    status = db.Column(db.String(1))
    runner_id = db.Column(db.Integer, db.ForeignKey('runners.id'),
                          nullable=False)
    race_id = db.Column(db.Integer, db.ForeignKey('races.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)

    def __init__(self, place, runner_id, race_id, team_id):
        max_id = Result.query.order_by(desc(Result.id)).first().id
        self.id = max_id + 1
        self.place = place
        self.runner_id = runner_id
        self.race_id = race_id
        self.team_id = team_id
        self.status = 'n'

    def __repr__(self):
        return f"Race:{self.race_id} Time:{self.display_time()}"

    def display_time(self):
        return timify(self.time)

    def display_pace(self):
        return timify(self.time / self.race.course.miles())

    def team_place(self):
        if not self.time:
            return 1000
        tp = 1
        for r in self.race.results:
            if r.time and r.team == self.team and r.time < self.time:
                tp += 1
        return tp


class Participant(db.Model):
    __tablename__ = 'participants'

    id = db.Column(db.Integer, primary_key = True)
    bib = db.Column(db.Integer)
    order = db.Column(db.Integer)
    runner_id = db.Column(db.Integer, db.ForeignKey('runners.id'),
                          nullable=False)
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
