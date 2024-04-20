# external imports
from flask import render_template, url_for, flash, redirect, request, jsonify
from flask import Blueprint
from flask_login import current_user, login_required
from flask_mail import Message
from sqlalchemy import func, asc, desc
from random import shuffle
from datetime import datetime, timedelta
from itertools import combinations
from pprint import pprint
from typing import List, Tuple

# hsxc imports
from hsxc import db, mail
from hsxc import celery
from hsxc.models import User, League, School, Runner, Team, Race
from hsxc.models import Result, RaceScore, Location, Course
from hsxc.helpers import CUR_YEAR
from hsxc.controllers.core.views import async_update_seed_times
from hsxc.controllers.core.views import async_update_all_seed_times
from hsxc.controllers.core.views import async_update_league_standings

race_setup = Blueprint('race_setup', __name__)


@race_setup.route("/create_race", methods=['GET'])
@login_required
def create_race():
    user_id = current_user.id
    new_race = Race(user_id=user_id, date=datetime.now())
    db.session.add(new_race)
    db.session.commit()
    return redirect(url_for('race_setup.race_metadata', race_id=new_race.id))


@race_setup.route("/<int:race_id>/race_metadata", methods=['GET'])
@login_required
def race_metadata(race_id: int):
    race: Race = Race.query.get(race_id)

    if race.status == 'complete':
        return redirect(url_for('races.results', race_id=race.id))
    
    data = {
        'race_id'                   : race.id,
        'date'                      : race.date.strftime("%m/%d/%Y"),
        'group_id'                  : race.group_id,
        'host_school_list'          : get_host_school_list(race),
        'non_participating_schools' : []
    }

    if race.host_school_id:
        data.update({
            'host_school_id'            : race.host_school_id,
            'location_list'             : get_location_list(race),
            'schools'                   : get_schools(race),
            'non_participating_schools' : get_non_participating_schools(race),
            'select_box_length_schools' : get_select_box_length_schools(race)
        })
        
    if race.location_id:
        data.update({
            'location_id' : race.location_id,
            'course_list' : get_course_list(race)
        })

    if race.course_id:
        data['course_id'] = race.course_id

    return render_template('race_metadata.html', data=data)

def get_host_school_list(race: Race) -> List[School]:
    host_school_list = (
        School.query.order_by(asc(func.lower(School.long_name))).all()
    )
    if race.host_school_id:
        host_school = School.query.get(race.host_school_id)
        host_school_list.insert(
            0, host_school_list.pop(host_school_list.index(host_school))
        )
    return host_school_list

def get_location_list(race: Race) -> List[Location]:
    host_school = School.query.get(race.host_school_id)
    location_list = Location.query.all()
    host_locations = host_school.locations
    for l in host_locations:
        location_list.insert(0,location_list.pop(location_list.index(l)))

    if race.location_id:
        location_id = race.location_id
        l = Location.query.get(location_id)
        location_list.insert(0,location_list.pop(location_list.index(l)))

    return location_list

def get_schools(race: Race) -> List[School]:
    host_school = School.query.get(race.host_school_id)
    return race.alphabetized_schools() if race.schools else [host_school]

def get_non_participating_schools(race: Race) -> List[School]:
    host_school_list = get_host_school_list(race)
    if race.schools:
        nps = [s for s in host_school_list if s not in race.schools]
        nps = sorted(nps, key=lambda s: s.long_name)
    else:
        nps = sorted(host_school_list[1:], key=lambda s: s.long_name)
    return nps

def get_select_box_length_schools(race: Race) -> int:
    MAXIMUM_BOX_SIZE = 20
    school = get_schools(race)
    nps = get_non_participating_schools(race)
    return min(MAXIMUM_BOX_SIZE, max(len(nps), len(school)))

def get_course_list(race: Race) -> List[Course]:
    location_id = race.location_id
    course_list = Course.query.filter_by(location_id=location_id).all()
    if race.course_id:
        course_id = race.course_id
        c = Course.query.get(course_id)
        course_list.insert(0, course_list.pop(course_list.index(c)))
    return course_list


@race_setup.route("/update_race_metadata", methods=['POST'])
@login_required
def update_race_metadata():
    try:
        client_data = request.get_json()
        log_data("Received", client_data)

        race = Race.query.get(client_data['race_id'])
        log_data("Current", format_race_data_for_logging(race))

        process_race_metadata_data_from_client(race, client_data)
        log_data("Updating to", format_race_data_for_logging(race))

        db.session.commit()
        return jsonify({'Status':'Received race'})

    except Exception as e:
        # Replace print with a logger for production scenarios
        print(f"AJAX exception: {str(e)}")
        return jsonify({'Error': str(e)}), 500  # Send a 500 Internal Server Error

def log_data(prefix: str, data: dict):
    # This is a stand-in for whatever logging system you'd use.
    print(f"\n------------- {prefix} -------------")
    pprint(data)

def format_race_data_for_logging(race: Race) -> dict:
    return {
        'race_id': race.id,
        'date': race.date.strftime('%m/%d/%Y'),
        'host_school_id': race.host_school_id,
        'location_id': race.location_id,
        'course_id': race.course_id,
        'is_jv': race.is_jv,
        'schools': race.schools
    }

def process_race_metadata_data_from_client(race: Race, client_data: dict):
    if 'date' in client_data:
        race.date = datetime.strptime(client_data['date'], '%m/%d/%Y')

    if 'host_school_id' in client_data:
        update_host_school(race, client_data['host_school_id'])

    if 'location_id' in client_data and client_data['location_id'] != '':
        update_location(race, client_data['location_id'])

    if 'course_id' in client_data and client_data['course_id'] != '':
        race.course_id = client_data['course_id']

    if 'schools' in client_data:
        update_schools(race, client_data['schools'])

    if 'status' in client_data:
        race.status = client_data['status']

def update_host_school(race: Race, host_school_id: int) -> None:
    if race.host_school_id != host_school_id:
        race.location_id = None
        race.course_id = None

    race.host_school_id = host_school_id

def update_location(race: Race, location_id: int) -> None:
    if race.location_id != location_id:
        race.course_id = None

    race.location_id = location_id

    # if location not already associated with school, add association
    location: Location = Location.query.get(location_id)
    host_school: School = School.query.get(race.host_school_id)
    if location not in host_school.locations:
        host_school.locations.append(location)

def update_schools(race: Race, school_ids: List[int]) -> None:
    race.schools.clear()
    for s_id in school_ids:
        race.schools.append(School.query.get(s_id))
    adjust_teams_and_results_for_updated_schools(race)

def adjust_teams_and_results_for_updated_schools(race: Race) -> None:
    for team in race.teams:
        if team.school not in race.schools:
            race.teams.remove(team)

    for res in race.results:
        if res.team.school not in race.schools:
            db.session.delete(res)


@race_setup.route("/<int:race_id>/race_detail", methods=['GET'])
@login_required
def race_detail(race_id: int):
    race: Race = Race.query.get(race_id)

    if race.status == 'complete':
        return redirect(url_for('races.results', race_id=race.id))

    data = {
        'race': race,
        'race_id': race_id,
        'race_name': set_race_name_if_none(race),
        'group_id': race.group_id,
        'races_count': len(race.group_races()),
        'race_number': race.group_races().index(race) + 1,
        'prev_race_id': race.previous_group_race_id(),
        'next_race_id': race.next_group_race_id(),
        'gender_list': get_gender_list(race),
        'varsity_jv_list': get_varsity_jv_list(race),
        'potential_teams': get_potential_teams(race),
        'selected_teams': get_selected_teams(race)
    }
    create_initial_race_results_if_needed(race)
    running, not_running = get_participants_and_non_participants(race)
    data['participants'] = running
    data['non_participants'] = not_running

    return render_template('race_detail.html', data=data)

def set_race_name_if_none(race: Race) -> str:
    if race.name is None or race.name == 'None':
        slist = [s.short_name for s in race.schools if s != race.host_school]
        race.name = ', '.join(slist) + f' at {race.host_school.short_name}'
        db.session.commit()
    return race.name

def get_gender_list(race: Race) -> List[str]:
    gender_order = ['Girls', 'Boys', 'Combined']
    if race.gender:
        selection = race.gender.replace('combo', 'Combined').capitalize()
        index = gender_order.index(selection)
        gender_order.insert(0, gender_order.pop(index))
    return gender_order

def get_varsity_jv_list(race: Race) -> List[str]:
    return ['JV', 'Varsity'] if race.is_jv else ['Varsity', 'JV']

def get_potential_teams(race: Race) -> List[Team]:
    return [
        team for schl in race.schools
        for team in Team.query.filter_by(school_id=schl.id, year=CUR_YEAR).all()
        if team.gender == race.gender or race.gender == 'combo'
    ]

def get_selected_teams(race: Race) -> List[Team]:
    if race.teams:
        return race.teams
    else:
        potential_teams = get_potential_teams(race)
        for t in potential_teams:
            race.teams.append(t)
        db.session.commit()
        return potential_teams

def create_initial_race_results_if_needed(race: Race) -> None:
    # abort if race already has results
    if race.results:
        return

    runner_ids_in_other_group_races: List[str] = [
        group_result.runner_id
        for group_race in race.other_group_races()
        for group_result in group_race.results
    ]

    runners_needing_results: List[Tuple[Runner, Team]] = [
        (runner, team) for team in race.teams for runner in team.runners
        if runner.id not in runner_ids_in_other_group_races
    ]

    for runner, team in runners_needing_results:
        res = Result(
            place=runner.seed_time, 
            runner_id=runner.id, 
            race_id=race.id, 
            team_id=team.id
        )
        db.session.add(res)
        res.status = 'n'
    db.session.commit()

def get_participants_and_non_participants(
    race: Race
) -> Tuple[List[Runner], List[Runner]]:
    all_runners = [runner for team in race.teams for runner in team.runners]
    participants = [
        r for r in all_runners
        if Result.query.filter_by(race_id=race.id, runner_id=r.id).first()
    ]
    participants = [r for r in participants if r]
    non_participants = [r for r in all_runners if r not in participants]

    participants = sorted(participants, key=lambda r: r.seed_time)
    non_participants = sorted(non_participants, key=lambda r: r.seed_time)
    return participants, non_participants


@race_setup.route("/update_race_detail", methods=['POST'])
@login_required
def update_race_detail():
    try:
        client_data = request.get_json()
        log_data("Received", client_data)

        race = Race.query.get(client_data['race_id'])
        log_data('Current', format_race_data_for_logging(race))

        update_race_gender(race, client_data)
        update_is_jv(race, client_data)
        update_name(race, client_data)
        update_teams(race, client_data)
        update_status_if_provided(race, client_data)
        log_data("Updating to", format_race_data_for_logging(race))

        return jsonify({'Status':'Received race'})

    except Exception as e:
        # Replace print with a logger for production scenarios
        print(f"AJAX exception: {str(e)}")
        return jsonify({'Error': str(e)}), 500  # Send a 500 Internal Server Error

def update_race_gender(race: Race, client_data: dict) -> None:
    # abort if gender not in client_data
    if not client_data['gender'] or client_data['gender'] == '':
        return

    # if gender has changed, clear all results and teams
    if race.gender != client_data['gender']:
        res_list = Result.query.filter_by(race_id=race.id).all()
        for r in res_list:
            db.session.delete(r)
        race.teams.clear()
        db.session.commit()
    race.gender = client_data['gender']

def update_is_jv(race: Race, client_data: dict) -> None:
    # abort if is_jv not in client_data
    if 'is_jv' not in client_data or client_data['is_jv'] == '':
        return

    # ensure that is_jv is a boolean
    if isinstance(client_data['is_jv'], str):
        is_jv_bool = True if client_data['is_jv'].lower() == 'true' else False
        client_data['is_jv'] = is_jv_bool

    race.is_jv = client_data['is_jv']
    db.session.commit()

def update_name(race: Race, client_data: dict) -> None:
    if 'name' in client_data:
        race.name = client_data['name']
        db.session.commit()

def update_teams(race: Race, client_data: dict) -> None:
    # add any newly selected teams
    current_teams_ids = [t.id for t in race.teams]
    selected_teams_ids = [int(id) for id in client_data['selected_teams']]
    for selected_team_id in selected_teams_ids:
        if selected_team_id in current_teams_ids:
            continue

        team = Team.query.get(selected_team_id)
        race.teams.append(team)
        for result in team.runners:
            res = Result(result.seed_time, result.id, race.id, team.id)
            db.session.add(res)

    # adjust for any newly deleted teams
    for current_team_id in current_teams_ids:
        if current_team_id in selected_teams_ids:
            continue

        team = Team.query.get(current_team_id)
        race.teams.remove(team)
        results = Result.query.filter_by(race_id=race.id, team_id=team.id).all()
        for result in results:
            db.session.delete(result)

    db.session.commit()

def update_status_if_provided(race: Race, client_data: dict) -> None:
    if 'status' not in client_data or client_data['status'] == '':
        return

    race.status = client_data['status']
    race.schools.clear()
    for team in race.teams:
        race.schools.append(team.school)
    db.session.commit()


@race_setup.route("/update_race_participants", methods=['POST'])
@login_required
def update_race_participants() -> None:
    try:
        client_data = request.get_json()
        race: Race = Race.query.get(client_data['race_id'])
        add_newly_selected_runners(race, client_data)
        remove_newly_unselected_runners(race, client_data)
        return jsonify({'Status':'Received race'})

    except Exception as e:
        # Replace print with a logger for production scenarios
        print(f"AJAX exception: {str(e)}")
        return jsonify({'Error': str(e)}), 500  # Send a 500 Internal Server Error

def add_newly_selected_runners(race: Race, client_data: dict) -> None:
    current_runner_ids = [res.runner_id for res in race.results]
    new_runner_ids = [int(id) for id in client_data['participants']]

    for id in new_runner_ids:
        if id in current_runner_ids:
            continue
        runner: Runner = Runner.query.get(id)
        team: Team = next(t for t in race.teams if t in runner.teams)
        res = Result(runner.seed_time, runner.id, race.id,team.id)
        db.session.add(res)

    db.session.commit()

def remove_newly_unselected_runners(race: Race, client_data: dict) -> None:
    current_runner_ids = [res.runner_id for res in race.results]
    new_runner_ids = [int(id) for id in client_data['participants']]

    for id in current_runner_ids:
        if id in new_runner_ids:
            continue
        res = Result.query.filter_by(runner_id=id, race_id=race.id).first()
        db.session.delete(res)

    db.session.commit()


@race_setup.route("/duplicate_race", methods=['POST'])
@login_required
def duplicate_race():
    """
    AJAX route to duplicate the race meta data to create a group of races.
    This is called at the beginning of race_detail.html when asked how many
    races will be run
    """
    try:
        client_data = request.get_json()
        race: Race = Race.query.get(client_data['race_id'])

        # set the group_id
        max_group_id = db.session.query(func.max(Race.group_id)).scalar() or 0
        race.group_id = max_group_id + 1
        db.session.commit()

        # if more than one race, create new races with corresponding group_id
        races_count = int(client_data['races_count'])
        for i in range(races_count - 1):
            additional_group_race = Race(
                user_id=race.user_id, 
                date=race.date,
                host_school_id = race.host_school_id,
                location_id = race.location_id,
                course_id = race.course_id,
                group_id = race.group_id,
            )
            additional_group_race.schools = race.schools
            db.session.add(additional_group_race)
            db.session.commit()

        return jsonify({'Status':'Received race'})

    except Exception as e:
        # Replace print with a logger for production scenarios
        print(f"AJAX exception: {str(e)}")
        return jsonify({'Error': str(e)}), 500  # Send a 500 Internal Server Error


@race_setup.route("/<int:race_id>/using_bibs", methods=['GET', 'POST'])
@login_required
def using_bibs(race_id):
    """Route to determine if this race is using bibs"""
    race = Race.query.get(race_id)
    if race.status == 'complete':
        return redirect(url_for('races.results', race_id=race.id))

    return render_template('using_bibs.html', race=race)


@race_setup.route("/<int:race_id>/bibs", methods=['GET'])
@login_required
def bibs(race_id):
    race: Race = Race.query.get(race_id)

    if race.status == 'complete':
        return redirect(url_for('races.results', race_id=race.id))

    schools = get_schools_in_group_races(race)
    return render_template('bibs.html', race=race, schools=schools)

def get_schools_in_group_races(race: Race) -> List[School]:
    group_races = get_group_races(race)
    schools: List[School] = list(
        {school for race in group_races for school in race.schools}
    )
    schools.sort(key=lambda s: s.long_name, reverse=False)
    return schools

def get_group_races(race: Race) -> List[Race]:
    return Race.query.filter_by(group_id=race.group_id).all()


@race_setup.route("/get_participants_for_bib_assignment", methods=['POST'])
@login_required
def get_participants_for_bib_assignment():
    """AJAX route to generate data needed for bib assignment."""
    try:
        client_data = request.get_json()
        race: Race = Race.query.get(client_data['race_id'])
        group_races = get_group_races(race)

        # if client_data contains 'status' then update database and return
        if 'status' in client_data:
            for r in group_races:
                r.status = client_data['status']
            db.session.commit()
            return jsonify({'Status':'Updated Race Status to ready'})

        data = {'race_id': race.id}
        data['schools'] = [
            {
                'school_id': school.id,
                'school_name': school.short_name,
                'primary_color': school.primary_color,
                'text_color': school.text_color,
            }
            for school in get_schools_in_group_races(race)
        ]
        data['participants'] = [
            {
                'result_id': res.id,
                'runner_id': res.runner.id,
                'runner_last_name': res.runner.last_name,
                'runner_first_name': res.runner.first_name,
                'race_id': race.id,
                'team_id': res.team.id,
                'school_id': res.team.school.id,
                'gender': res.team.gender,
                'bib': res.bib,
            }
            for race in group_races for res in race.results
        ]

        return jsonify(data)

    except Exception as e:
        # Replace print with a logger for production scenarios
        print(f"AJAX exception: {str(e)}")
        return jsonify({'Error': str(e)}), 500  # Send a 500 Internal Server Error


@race_setup.route("/update_bib_assignments", methods=['POST'])
@login_required
def update_bib_assignments():
    """AJAX route to update the database for any bib assignments or changes"""
    try:
        client_data = request.get_json()

        for participant_info in client_data['participants']:
            res: Result = Result.query.get(participant_info['result_id'])
            res.bib = participant_info['bib']
        db.session.commit()
        return jsonify({'Status':'Received race'})

    except Exception as e:
        # Replace print with a logger for production scenarios
        print(f"AJAX exception: {str(e)}")
        return jsonify({'Error': str(e)}), 500  # Send a 500 Internal Server Error


@race_setup.route("/email_bib_assignments", methods=['POST'])
@login_required
def email_bib_assignments():
    """
    AJAX route to email bib assignments to addresses provided by user.  The
    message is a simple plain-text list for clarity
    """
    try:
        client_data = request.get_json()
        race: Race = Race.query.get(client_data['race_id'])

        subject = (
            f'Bib Assingments for race at {race.location.name} '
            f'on {race.display_date()}'
        )
        msg = Message(
            subject=subject,
            sender=('New England Prep XC','neprepxc@gmail.com'),
            recipients=[client_data['recipients']],
            body=client_data['messageBody']
        )
        mail.send(msg)

        return jsonify({'Status':'Received race'})

    except Exception as e:
        # Replace print with a logger for production scenarios
        print(f"AJAX exception: {str(e)}")
        return jsonify({'Error': str(e)}), 500  # Send a 500 Internal Server Error





@race_setup.route("/create_team_if_needed", methods=['POST'])
@login_required
def create_team_if_needed():
    """
    AJAX route to create a new team and add it to the database

    Return: none
    """
    try:
        # get client data from request
        client_data = request.get_json()
        print(f"recived: {client_data}")

        # set a gender code
        gender = 'girls' if client_data['gender_code'] == 1 else 'boys'

        # if the team does not yet exist, create it
        team = Team.query.filter_by(school_id = client_data['school_id'],
                                    year=client_data['year'],
                                    gender=gender).first()
        print(team)
        if not team:
            team = Team(gender=gender,
                        year=client_data['year'],
                        school_id=client_data['school_id'])
            db.session.add(team)
            db.session.commit()

        # Pass JSON_received to the frontend
        JSON_received = {'Status':'Received race'}
        return jsonify(JSON_received)

    except Exception as e:
        print("AJAX excepted " + str(e))
        return str(e)


@race_setup.route("/edit_delete_runner", methods=['POST'])
@login_required
def edit_delete_runner():
    """
    AJAX route to edit or delete an existing runner.  Disallowed if runner
    already exists

    Return: none
    """
    try:
        # get the runner data from the client
        runner_data = request.get_json()
        print('\n------- edit_delete_runner route beginning -------')
        print(f'Editing with: {runner_data}')

        # retrieve runner from the database
        runner: Runner = Runner.query.get(runner_data['runner_id'])

        # if request is 'delete', veryify if ok to delete
        if runner_data['edit_or_delete'] == 'delete':

            # remove from current team
            cur_team = runner.current_year_team()
            if cur_team:
                print(f'removing {runner} from {cur_team}')
                cur_team.runners.remove(runner)
                db.session.commit()

            # delete runner if there are not completed results
            if runner.completed_results():
                print(f'{runner} has results in the database and will '
                      f'not be deleted')

                # create message
                flash_status = 'success'
                message = (f'{runner.display_name()} removed from {cur_team}, '
                           f'but previous results will remain in the database')
            else:
                # Create message
                flash_status = 'success'
                message = (f'Successfully deleted {runner.display_name()} '
                           f'from the database.')
                db.session.delete(runner)
                db.session.commit()

            flash(message, 'success')
            print(message)


        # if runner being edited, update runner information from client_data
        if runner_data['edit_or_delete'] == 'edit':
            # Update runner data only if fields are provided
            if runner_data['first_name']:
                runner.first_name = runner_data['first_name']
            if runner_data['last_name']:
                runner.last_name = runner_data['last_name']
            if runner_data['grad_year']:
                runner.grad_year = runner_data['grad_year']
            if runner_data['seed_time']:
                runner.seed_time = runner_data['seed_time']

            # commit changes
            db.session.commit()
            message = (f'Successfully updated {runner.display_name()} '
                       f'in the database.')
            flash(message, 'success')
            flash_status = 'success'

        # Pass JSON_received to the frontend
        JSON_received = {'status':flash_status, 'message':message}
        return jsonify(JSON_received)

    except Exception as e:
        print("AJAX excepted " + str(e))
        return str(e)


@race_setup.route("/<int:race_id>/delete_race", methods=['GET', 'POST'])
@login_required
def delete_race(race_id):
    """
    Route to delete a race (and associated relationships) from database

    Return: redirect to home.html when complete
    """
    # get race from database
    race = Race.query.get(race_id)
    print('\n-----------------------------')
    print(f'attempting to delete {race}')

    # prohibit deleting races unless user setup race or is adminstrator
    if not current_user.is_administrator() and current_user.id != race.user_id:
        flash('You are not authorized to delete this race', 'danger')
        return redirect(url_for('races.results', race_id=race.id))

    # capture league_ids before deleting
    league_ids = {
        school.league.id
        for school in race.schools
    }

    # delete via helper function
    delete_race_by_id(race_id=race_id, user_id=current_user.id)

    # update league standings via background task
    for league_id in league_ids:
        if league_id != 3:
            async_update_league_standings.delay(league_id=league_id)

    return redirect(url_for('core.index'))


@race_setup.route("/remove_demo")
@login_required
def remove_demo():
    async_remove_demo.delay(user_id=current_user.id)
    return redirect(url_for('core.index'))


@celery.task(bind=True)
def async_remove_demo(self, user_id):
    races = Race.query.all()
    races = [race for race in races if race.id > 18]
    for race in races:
        print(f'deleting race {race.id}')
        delete_race_by_id(race_id=race.id,
                          user_id=user_id,
                          updated_seed_times=False)

    # update league standings via background task
    for league_id in [1, 2]:
        async_update_league_standings.delay(league_id=league_id)

    # update seed times
    async_update_all_seed_times.delay()

@race_setup.route("/create_demo")
@login_required
def create_demo():
    async_create_demo.delay(user_id=current_user.id)
    return redirect(url_for('core.index'))


@celery.task(bind=True)
def async_create_demo(self, user_id):
    # get all full teams of both genders for schools in EIL and ISL
    schools = School.query.all()
    schools = [school for school in schools if school.league.id < 3]
    teams = [
        team
        for school in schools
        for team in school.current_year_teams()
        if len(team.runners) > 4
    ]

    # find all relevant intra league team combinations
    pairs = list(combinations(teams, 2))
    pairs = [
        pair
        for pair in pairs
        if (pair[0].gender == pair[1].gender)
    ]
    shuffle(pairs)

    # create races for each pair
    max_id = Race.query.order_by(desc(Race.id)).first().id
    group_id = max_id + 1
    day = datetime.today()
    for pair in pairs:
        race = Race(user_id, day)
        db.session.add(race)
        db.session.commit()

        race.host_school_id = pair[0].school.id
        race.location_id = 5
        race.course_id = 5
        race.status = 'complete'
        race.name = f'{pair[0].school.short_name} vs {pair[1].school.short_name}'
        race.gender = pair[0].gender
        race.group_id = group_id
        group_id += 1
        db.session.commit()

        print(f'Creating race: {race}')
        bib = 1
        for team in pair:
            race.schools.append(team.school)
            race.teams.append(team)
            for runner in team.runners:
                result = Result(
                    place=runner.seed_time,
                    runner_id=runner.id,
                    race_id=race.id,
                    team_id=team.id
                )
                db.session.add(result)
                db.session.commit()
                result.bib = bib
                bib += 1
                result.time = runner.seed_time
                result.status = 'c'
                db.session.commit()
        day += timedelta(hours=4)

    # correct places
    races_to_fix = Race.query.all()
    races_to_fix = [race for race in races_to_fix if race.id > 18]
    for race in races_to_fix:
        new_place = 1
        for res in race.sorted_results():
            res.place = new_place
            new_place += 1
        db.session.commit()

    # update league standings via background task
    for league_id in [1, 2]:
        async_update_league_standings.delay(league_id=league_id)


@race_setup.route("/roll_back_demo")
@login_required
def roll_back_demo():
    """
    Temporary route to test various one-off functionality.

    Return: nothing.  Redirects to home.html when complete
    """
    # return harvey rupp to belmont hill team
    bh = Team.query.get(161)
    print(f'retrieved {bh}')
    hr = Runner.query.get(1700)
    print(f'retrieved {hr}')
    if bh not in hr.teams:
        bh.runners.append(hr)
        db.session.commit()

    # set primary_key values below which will be untouched
    first_deleted_race = 19
    first_deleted_runner = 3712
    first_deleted_result = 4750
    first_deleted_school = 68
    first_deleted_team = 315
    first_deleted_location = 8
    first_deleted_course = 9
    first_deleted_league = 4

    # do not allow unless user is administrator
    if not current_user.is_administrator():
        return redirect(url_for('races.results', race_id=race.id))

    # delete races and associated results for races in delete range
    races = Race.query.all()
    for race in races:
        if race.id >= first_deleted_race:
            delete_race_by_id(race.id)

    # disassociate runners from teams and delete
    teams = Team.query.all()
    for team in teams:
        if team.id >= first_deleted_team:
            team.runners.clear()
    db.session.commit()

    runners = Runner.query.all()
    for runner in runners:
        if runner.id >= first_deleted_runner:
            db.session.delete(runner)
    db.session.commit()

    # delete teams
    for team in teams:
        if team.id >= first_deleted_team:
            db.session.delete(team)
    db.session.commit()

    # delete courses
    courses = Course.query.all()
    for course in courses:
        if course.id >= first_deleted_course:
            db.session.delete(course)
    db.session.commit()

    # disassociate locaions from schools and delete
    schools = School.query.all()
    for school in schools:
        if school.id >= first_deleted_school:
            school.locations.clear()
    db.session.commit()

    locations = Location.query.all()
    for location in locations:
        if location.id >= first_deleted_location:
            db.session.delete(location)
    db.session.commit()

    # disassociate schools from leagues and delete
    leagues = League.query.all()
    for league in leagues:
        if league.id >= first_deleted_league:
            league.schools.clear()
    db.session.commit()

    for school in schools:
        if school.id >= first_deleted_school:
            db.session.delete(school)
    db.session.commit()

    # delete leagues
    for league in leagues:
        if league.id >= first_deleted_league:
            db.session.delete(league)
    db.session.commit()

    # recalculate all runners seed times
    async_update_all_seed_times.delay()

    # update league standings via background task
    for league_id in [1, 2]:
        async_update_league_standings.delay(league_id=league_id)
    return redirect(url_for('core.index'))


def delete_race_by_id(race_id, user_id, updated_seed_times=True):
    """
    Delete a race (and associated relationships) from database

    Return: none
    """
    # get race object from database
    race = Race.query.get(race_id)

    # determine all effected runners
    runners = race.all_runners()

    # get user
    user = User.query.get(user_id)

    # prohibit deleting races unless user setup race or is adminstrator
    if not user.is_administrator() and user.id != race.user_id:
        flash('You are not authorized to delete this race', 'danger')
        return redirect(url_for('races.results', race_id=race.id))

    # clear team associations from race
    print(f'teams: {race.teams}')
    race.teams.clear()
    db.session.commit()
    print("cleared teams")

    # clear school associations from race
    race.schools.clear()
    print("cleared schools")

    # clear race_scores for race
    race_scores = RaceScore.query.filter_by(race_id=race.id).all()
    for race_score in race_scores:
        db.session.delete(race_score)
    print('cleared race_scores')

    # clear all results from race
    for res in race.results:
        db.session.delete(res)
    db.session.commit()
    print("cleared results")

    # delete race from database and commit changes
    db.session.delete(race)
    db.session.commit()

    # update seed_times on background worker
    if updated_seed_times:
        runner_ids = [runner.id for runner in runners]
        async_update_seed_times.delay(runner_ids=runner_ids)

    # update the league standings on background worker
    leagues = {
        team.school.league
        for team in race.teams
        if team.school.league != 3
    }
    for league in leagues:
        async_update_league_standings.delay(
            league_id=league.id, year=CUR_YEAR
        )

