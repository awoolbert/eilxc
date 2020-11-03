import os
import datetime
from datetime import date, datetime
from flask import jsonify
from flask import render_template, url_for, flash, redirect, request, Blueprint
from flask_login import login_user, current_user, logout_user, login_required
from eilxc import celery
from eilxc.models import (League, School, Runner, Team, Race,
                          Result, Participant, Location, Course)
from eilxc.helpers import *
from pprint import pprint
import time

core = Blueprint('core',__name__)


@core.route('/')
def index():
    """
    Route to simply display index.html.  Route is often called after invalid
    actions

    Return: render index.html
    """
    # build list of school objects for all schools with a logo
    all_schools = School.query.all()
    schools_with_logos = [s for s in all_schools if s.has_image()]
    schools_with_logos = sorted(schools_with_logos, key=lambda s: s.long_name)

    return render_template('index.html', schools=schools_with_logos)


@core.route("/<int:runner_id>/runner", methods=['GET'])
@login_required
def runner(runner_id):
    """
    Route to display data and results for a given runner

    Return: redirect to runner.html when complete
    """
    print(' ')
    print('-------------- starting runner route --------------')

    # get runner from database
    runner = Runner.query.get(runner_id)
    print(f'building route for {runner}')

    # render runner.html
    return render_template('runner.html', runner=runner)


@core.route("/update_all_seed_times")
@login_required
def update_all_seed_times():
    """
    Temporary route to update every runner's seed time.

    Return: nothing.  Redirects to home.html when complete
    """
    runners = Runner.query.all()
    runners = [r for r in runners if r.grad_year > datetime.today().year]
    runner_count = len(runners)
    message = (f'Updating seed times for {runner_count} runners.  '
                'Page will display when finished')
    task = async_update_all_seed_times.delay()
    location = url_for('core.taskstatus', task_id=task.id)
    print(location)
    return render_template(
        'updating_seed_times.html', location=location,
                                    runner_count=f'{runner_count:,.0f}'
    )


@core.route('/status/<task_id>')
@login_required
def taskstatus(task_id):
    try:
        task = async_update_all_seed_times.AsyncResult(task_id)
        if task.state == 'PENDING':
            response = {
                'state': task.state,
                'current': 0,
                'total': 1,
                'status': 'Pending...'
            }
        elif task.state != 'FAILURE':
            response = {
                'state': task.state,
                'current': task.info.get('current', 0),
                'total': task.info.get('total', 1),
                'Status': 'Working...'
            }
            if 'result' in task.info:
                response['result'] = task.info['result']
        else:
            response = {
                'state': task.state,
                'current': 1,
                'total': 1,
            }
        return jsonify(response)

    except Exception as e:
        print("AJAX excepted " + str(e))
        return str(e)


@core.route("/<int:race_id>/<int:school_id>/<int:gender_code>/<int:runner_id>/found_existing_runner", methods=['GET'])
@login_required
def found_existing_runner(race_id, school_id, gender_code, runner_id):
    """
    Route to display data and results for a given runner

    Return: redirect to runner.html when complete
    """
    print(' ')
    print('------- starting found_existing_runner route -------')

    # get runner from database
    runner = Runner.query.get(runner_id)
    print(f'building route for {runner}')

    # render runner.html
    return render_template('found_existing_runner.html',
                            runner=runner,
                            race_id=race_id,
                            school_id=school_id,
                            gender_code=gender_code,
                            new_runner=new_runner
    )


@core.route('/<int:school_id>/school')
@login_required
def school(school_id):
    """
    Route to simply display index.html.  Route is often called after invalid
    actions

    Return: render index.html
    """
    # get school object from database
    school = School.query.get(school_id)
    print(' ')
    print('------- starting school route -------')
    print(f'building route for {school.long_name}')

    # get this year's teams
    teams = school.current_year_teams()
    print(f'found teams: {teams}')

    # get this year's races
    cy_races = []
    for team in teams:
        cy_races.extend(team.races)

    # build list of all race results
    races = [r for r in school.all_races if r.status == 'complete'
                                         and r not in cy_races]

    # sort races list
    races = sorted(races, key=lambda r: r.gender, reverse=True)
    races = sorted(races, key=lambda r: r.name)
    races = sorted(races, key=lambda r: r.reverse_date(), reverse=True)

    # start background job to calculate season summary
    team_ids = [team.id for team in teams]
    task = async_get_season_summary.delay(team_ids)
    location = url_for('core.ss_status', task_id=task.id)

    # render runner.html
    return render_template('school.html', school=school,
                                           location=location,
                                           teams=teams,
                                           races=races)


@core.route('/ss_status/<task_id>')
@login_required
def ss_status(task_id):
    try:
        task = async_get_season_summary.AsyncResult(task_id)
        if task.state == 'PENDING':
            response = {
                'state': task.state,
                'current': 0,
                'total': 1,
                'status': 'Pending...'
            }
        elif task.state != 'FAILURE':
            response = {
                'state': task.state,
                'current': task.info.get('current', 0),
                'total': task.info.get('total', 1),
                'Status': 'Working...'
            }
            if 'result' in task.info:
                response['result'] = task.info['result']
        else:
            response = {
                'state': task.state,
                'current': 1,
                'total': 1,
            }
        return jsonify(response)

    except Exception as e:
        print("AJAX excepted " + str(e))
        return str(e)


@core.route('/<int:league_id>/league')
@login_required
def league(league_id):
    """
    Route to display the league standings tables for the current season

    Return: render league.html
    """
    league = League.query.get(league_id)
    standings = league.standings()
    standings = [
        sorted(standings[gender],
               key=lambda t:
               t['percent'] if isinstance(t['percent'], int) else - 1,
               reverse=True)
        for gender in standings
    ]

    # build list of school objects for all schools in league with a logo
    league_schools = league.schools
    league_schools = sorted(league_schools, key=lambda s: s.long_name)

    # add schools to data
    logo_data = [
        {
            'school':school,
            'img_filename':school.img_filename()
        }
        for school in league_schools
        if school.has_image()
    ]
    # img_width = f'{int(100 * 0.99 / min(len(logo_data),11))}%'
    img_width = f'10%'

    year = datetime.today().year

    # render runner.html
    return render_template('league.html', league=league,
                                          standings=standings,
                                          logo_data=logo_data,
                                          img_width=img_width,
                                          year=year)


@core.route('/<int:league_id>/calc_league_standings')
@login_required
def calc_league_standings(league_id):
    task = async_update_league_standings.delay(league_id=league_id,
                                               year=datetime.today().year)
    return redirect(url_for('core.index'))

@celery.task(bind=True)
def async_update_seed_times(self, runner_ids):
    t0 = time.time()
    runners = []
    for runner_id in runner_ids:
        runners.append(Runner.query.get(runner_id))
    runner_count = len(runners)
    for runner in runners:
        current = runner.display_seed_time()
        if runner.completed_results():
            runner.update_seed_time()
            updated = runner.display_seed_time()
        else:
            runner.seed_time = 1500000
            db.session.commit()
    t1 = time.time()
    print(f'\nSeed times for {runner_count} updated in {t1-t0} seconds\n')
    return {'current': runner_count, 'total': runner_count, 'result': 1}


@celery.task(bind=True)
def async_update_all_seed_times(self):
    t0 = time.time()
    runners = Runner.query.all()
    runners = [r for r in runners if r.grad_year > datetime.today().year]
    runner_count = len(runners)
    for indx, runner in enumerate(runners):
        current = runner.display_seed_time()
        if runner.completed_results():
            runner.update_seed_time()
            updated = runner.display_seed_time()
        else:
            runner.seed_time = 1500000
            db.session.commit()
        self.update_state(
            state='PROGRESS',
            meta={'current': indx,'total': runner_count}
        )
    t1 = time.time()
    print(f'\nSeed times for {runner_count} updated in {t1-t0} seconds\n')
    return {'current': runner_count, 'total': runner_count, 'result': 1}


@celery.task(bind=True)
def async_get_season_summary(self, team_ids):
    t0 = time.time()
    print(f'\n---------- Starting Season Summary Route ----------\n')
    self.update_state(
        state='PROGRESS',
        meta={'current': 1,'total': 1}
    )
    teams = []
    for team_id in team_ids:
        teams.append(Team.query.get(team_id))
    ss = {team.gender: team.season_summary() for team in teams}
    t1 = time.time()
    print(f'\n Completed route in {int(t1-t0)} seconds\n')
    return {'current': 1, 'total': 1, 'result': ss}


@celery.task(bind=True)
def async_update_league_standings(self, league_id, year=datetime.today().year):
    league = League.query.get(league_id)
    league.update_standings(year)
    return {'current': 1, 'total': 1, 'result': 1}
