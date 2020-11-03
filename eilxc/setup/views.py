import os
from pathlib import Path
from flask import render_template, url_for, flash, redirect, request, Blueprint
from flask import jsonify
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message
from werkzeug.security import generate_password_hash,check_password_hash
from sqlalchemy import collate, update, func, asc, desc
from datetime import datetime, timedelta
from itertools import combinations
from eilxc import db, login_manager, app, mail
from eilxc import celery
from eilxc.models import (User, League, School, Runner, Team, Race,
                          Result, Participant, Location, Course)
from eilxc.helpers import *
from eilxc.setup.forms import (LocationCourseForm, CourseForm,
                               SchoolForm, RunnerForm)
from eilxc.core.views import (async_update_seed_times,
                              async_update_all_seed_times,
                              async_update_league_standings,
                              async_get_season_summary)
import random
import time
import googlemaps

setup = Blueprint('setup', __name__)
API_KEY = os.environ['GOOGLE_API_KEY']
gmaps = googlemaps.Client(key=API_KEY)

@setup.route("/create_race", methods=['GET'])
@login_required
def create_race():
    """
    Route to create new race in the database and begin the setup process

    Return: renders race_setup.html
    """
    # create a new race and set user_id to current_user
    user_id = current_user.id
    newRace = Race(user_id=user_id, date=datetime.now())

    # update database and commit changes
    db.session.add(newRace)
    db.session.commit()
    return redirect(url_for('setup.race_setup', race_id=newRace.id))


@setup.route("/<int:race_id>/race_setup", methods=['GET', 'POST'])
@login_required
def race_setup(race_id):
    """
    Route to provide user with ability to create/update the meta data for the
    race (e.g., host_school, location, participating schools, course).  The
    database is updated through a different route using AJAX calls, but after
    each updating this route is re-called to format the page to both display
    the updated information and to open up new areas for the user to continue
    the update process

    Return: renders race_setup.html
    """
    # retrieve all the race data from the database
    race = Race.query.get(race_id)

    # if race is already completed, go to results
    if race.status == 'complete':
        return redirect(url_for('races.results', race_id=race.id))

    # create dictionary of info to print for this race
    race_to_print = {'race_id': race.id,
                     'date': race.date.strftime("%m/%d/%Y"),
                     'host_school_id': race.host_school_id,
                     'location': race.location,
                     'course': race.course,
                     'schools': race.schools}

    # print race info at the start of process
    print('\n------- race_setup route beginning -------')
    print(f"beginning with this data in databse: {race_to_print}\n")

    # build list of all possible host schools and alphabetize
    # TODO: when number of schools gets long, may want to organize and/or
    # limit this list to schools associated with this user. Need to preserve
    # the ability to see all schools if needed
    host_school_list = (
        School.query.order_by(asc(func.lower(School.long_name))).all()
    )

    # if a host school has already been selected and is in database
    if race.host_school_id:

        # move to front so it appears selected
        host_school = School.query.get(race.host_school_id)
        host_school_list.insert(
            0,host_school_list.pop(host_school_list.index(host_school))
        )

        # Build list of locations, ones associated with the school at front
        location_list = Location.query.all()
        host_locations = host_school.locations
        for l in host_locations:
            location_list.insert(0,location_list.pop(location_list.index(l)))

        # if a location has been selected, then put it first in the list so
        # that it is selected when the page is rendered
        if race.location_id:
            location_id = race.location_id
            l = Location.query.get(location_id)
            location_list.insert(0,location_list.pop(location_list.index(l)))

            # build list of courses
            course_list = Course.query.filter_by(location_id=location_id).all()

            # if a course has been selected, move it to top of list
            if race.course_id:
                course_id = race.course_id
                c = Course.query.get(course_id)
                course_list.insert(0, course_list.pop(course_list.index(c)))

    # build the data object containing all data for web page
    data = {'race_id': race_id,
            'date': race.date.strftime("%m/%d/%Y"),
            'group_id': race.group_id,
            'host_school_list': host_school_list,
            'non_participating_schools': []}

    # continue populating data object with info selected during this route
    if race.host_school_id:
        data['host_school_id'] = host_school.id
        data['location_list'] = location_list

        # allocate schools between participating and non participating
        if race.schools:
            data['schools'] = race.schools
            data['non_participating_schools'] = [
                school
                for school in host_school_list
                if school not in race.schools
            ]
        else:
            data['schools'] = [host_school]
            data['non_participating_schools'] = host_school_list[1:]

        # size the select box based on the school lists with a max of 20
        data['select_box_length_schools'] = (
            min(max(len(data['non_participating_schools']),
                    len(data['schools'])),
                20)
        )

    # add location and course if already selected
    if race.location_id:
        data['location_id'] = location_id
        data['course_list'] = course_list
    if race.course_id:
        data['course_id'] = race.course_id

    return render_template('race_setup.html', data=data)


@setup.route("/update_race_data", methods=['POST'])
@login_required
def update_race_data():
    """
    AJAX route to update database with selections made on race_setup.html

    Return: none
    """
    try:
        # get data from client request
        client_data = request.get_json()
        print('\n------- update_race_data route beginning -------')
        print(f"recived: \n {client_data}")

        # race is from databse, while client_data is from front end
        race = Race.query.get(client_data['race_id'])

        # create dictionary of info to print for this race
        race_to_print = {'race_id': race.id,
                         'date': race.date.strftime('%m/%d/%Y'),
                         'host_school_id': race.host_school_id,
                         'location_id': race.location_id,
                         'course_id': race.course_id,
                         'schools': race.schools
        }
        print(f"current: \n {race_to_print}")

        # update the race date if provided
        if 'date' in client_data:
            race.date = datetime.strptime(client_data['date'], '%m/%d/%Y')

        # update the host_school if provided
        if 'host_school_id' in client_data:
            # if host_school has changed clear previously selected loation
            # and course
            if race.host_school_id != client_data['host_school_id']:
                if race.location_id:
                    race.location_id = None
                if race.course_id:
                    race.course_id = None
            race.host_school_id = client_data['host_school_id']

        # update the location_id if provided
        if 'location_id' in client_data and client_data['location_id'] != '':
            # if location has changed after a course was selected, remove
            # course since it is assocated with a particular location
            if race.location_id != client_data['location_id']:
                if race.course_id:
                    race.course_id = None
            # if location not already associated with school, add association
            location = Location.query.get(client_data['location_id'])
            if location not in race.host_school.locations:
                race.host_school.locations.append(location)
            race.location_id = client_data['location_id']

        # update the course_id if provided
        if 'course_id' in client_data and client_data['course_id'] != '':
            race.course_id = client_data['course_id']

        # update the participating schools if provided
        if 'schools' in client_data:
            # clear out existing rows from race_schools
            race.schools.clear()
            # iterate through client_data['schools'], add rows to race_schools
            for s_id in client_data['schools']:
                s = School.query.get(s_id)
                race.schools.append(s)

        # update the status when the "next page" is called, indicating that
        # this step in the race_setup is complete
        if 'status' in client_data:
            race.status = client_data['status']

        # create dictionary of info to print for this race
        race_to_print = {
            'race_id': race.id,
            'date': race.date.strftime('%m/%d/%Y'),
            'host_school_id': race.host_school_id,
            'location_id': race.location_id,
            'course_id': race.course_id,
            'schools': race.schools
        }
        print(f"updating to: \n {race_to_print}\n")

        # commit changes to databse
        db.session.commit()

        # Pass JSON_received to the frontend
        JSON_received = {'Status':'Received race'}
        return jsonify(JSON_received)

    except Exception as e:
        print("AJAX excepted " + str(e))
        return str(e)


@setup.route("/<int:race_id>/race_detail", methods=['GET', 'POST'])
@login_required
def race_detail(race_id):
    """
    Route to provide user with ability to /update the race detail for the
    race (e.g., gender, name, participants).  The database is updated through
    a different route using AJAX calls, but after each updating this route is
    re-called to format the page to both display the updated information and
    to open up new areas for the user to continue the update process

    Return: renders race_detail.html
    """
    # retrieve all the race data from the database
    race = Race.query.get(race_id)

    # if race is already completed, go to results
    if race.status == 'complete':
        return redirect(url_for('races.results', race_id=race.id))

    # create dictionary of info to print for this race
    race_to_print = {
        'race_id': race.id,
        'gender': race.gender,
        'host_school_id': race.host_school_id,
        'location': race.location,
        'course': race.course,
        'schools': race.schools,
        'teams': race.teams
    }

    # print race info at the start of process
    print('\n------- race_detail route beginning -------')
    print(f"beginning with this data in databse: {race_to_print}\n")

    # build the data object containing data for web page and begin to populate
    data = {
        'race': race,
        'race_id': race_id,
        'group_id': race.group_id,
        'races_count': len(race.group_races()),
        'race_number': race.group_races().index(race) + 1,
        'prev_race_id': race.previous_group_race_id(),
        'next_race_id': race.next_group_race_id()
    }

    # order the gender_list to display the chosen value
    if race.gender == 'girls':
        data['gender_list']= ['Girls','Boys','Combined']
    elif race.gender == 'boys':
        data['gender_list'] = ['Boys','Girls','Combined']
    elif race.gender == 'combo':
        data['gender_list'] = ['Combined','Boys','Girls']
    else:
        data['gender_list'] = ['Girls','Boys','Combined']

    # build the list of potential teams based on gender selection
    year = datetime.today().year
    data['potential_teams'] = [
        t
        for s in race.schools
        for t in Team.query.filter_by(school_id=s.id, year=year).all()
        if t.gender == race.gender or race.gender == 'combo'
    ]

    # build the lists of selected teams (assume all teams will be selected)
    # if selected teams list does not yet exist (i.e., defaul to selected)
    if race.teams:
        data['selected_teams'] = race.teams
    else:
        for t in data['potential_teams']:
            race.teams.append(t)
        db.session.commit()
        data['selected_teams'] = data['potential_teams']

    # if results do not yet exist, add runners to the results table and set
    # the status to 'n' for 'not started'.  If they do exist, leave them as is.
    # if this race is part of a group, exclude runners that are already
    # assigned to another race
    if not race.results:
        # build list of runner_ids already assigned in another race in group
        runners_in_group_race = [
            gr_result.runner_id
            for group_race in race.other_group_races()
            for gr_result in group_race.results
        ]

        # create result, exclude runners in another race in group
        for t in race.teams:
            for r in t.runners:
                if r.id not in runners_in_group_race:
                    res = Result(place=r.seed_time,
                                 runner_id=r.id,
                                 race_id=race.id,
                                 team_id=t.id)
                    db.session.add(res)
                    res.status = 'n'

        # commit changes to database
        db.session.commit()

    # create lists of participating and not participating runners
    data['participants'] = []
    data['non_particpants'] = []
    for t in race.teams:
        for r in t.runners:
            if Result.query.filter_by(race_id=race.id,runner_id=r.id).first():
                data['participants'].append(r)
            else:
                data['non_particpants'].append(r)

    # print state of race and return race_detail page
    race_to_print = {
        'race_id': race.id,
        'gender': race.gender,
        'host_school_id': race.host_school_id,
        'location': race.location,
        'course': race.course,
        'schools': race.schools,
        'teams': race.teams,
        'non_participants': data['non_particpants']
    }
    print(f"ending with this data in databse: {race_to_print}")
    print(' ')

    return render_template('race_detail.html', data=data)


@setup.route("/update_race_detail", methods=['POST'])
@login_required
def update_race_detail():
    """
    AJAX route to update database with selections made on race_detail.html

    Return: none
    """
    try:
        # get data from client request
        client_data = request.get_json()

        print(' ')
        print('------- update_race_detail route beginning -------')
        print(f"recived: {client_data}")

        # race is from databse, while client_data is from front end
        race = Race.query.get(client_data['race_id'])
        print(f"current: race_id:{race.id}, name:{race.name}, "
              f"gender:{race.gender} teams:{race.teams}")

        # update the gender if provided
        if client_data['gender']:
            # if they have changed the gender, clear the teams and the results
            # because they are associated with a particular gender
            if race.gender != client_data['gender']:
                res_list = Result.query.filter_by(race_id=race.id).all()
                for r in res_list:
                    db.session.delete(r)
                race.teams.clear()
                db.session.commit()
            race.gender = client_data['gender']

        # update the name if provided
        if 'name' in client_data:
            race.name = client_data['name']
            db.session.commit()

        # determine if any teams were added to selected_teams and
        # add them to the database
        current_teams_ids = [t.id for t in race.teams]
        selected_teams_ids = [int(id) for id in client_data['selected_teams']]
        for st_id in selected_teams_ids:
            if st_id not in current_teams_ids:
                team = Team.query.get(st_id)
                # add the team to race.teams
                race.teams.append(team)

                # add the runners to race.results
                for r in team.runners:
                    res = Result(time=r.seed_time,
                                 runner_id=r.id,
                                 race_id=race.id,
                                 team_id=team.id)
                    db.session.add(res)

        # determine if any teams were removed from selected_teams and
        # remove them from the database
        for ct_id in current_teams_ids:
            if ct_id not in selected_teams_ids:
                team = Team.query.get(ct_id)

                # remove the team from race.teams
                race.teams.remove(team)

                # remove the associated runners from race.results
                res_list = Result.query.filter_by(race_id=race.id,
                                                  team_id=team.id).all()
                for r in res_list:
                    db.session.delete(r)

        # update the status when the "next page" is called, indicating that
        # this step in the race setup is complete
        if 'status' in client_data:
            race.status = client_data['status']
            # ensure that the school list for this race is consistent with
            # team list given teams may have been added or removed from race
            race.schools.clear()
            for team in race.teams:
                race.schools.append(team.school)
            db.session.commit()

        # Commit team and result additions or deletions
        db.session.commit()

        print(
            f"updating to: race_id:{race.id}, name:{race.name}, "
            f"gender:{race.gender}, group_id:{race.group_id} "
            f"teams:{race.teams}\n"
        )

        # Pass JSON_received to the frontend
        JSON_received = {'Status':'Received race'}
        return jsonify(JSON_received)

    except Exception as e:
        print("AJAX excepted " + str(e))
        return str(e)


@setup.route("/update_race_participants", methods=['POST'])
@login_required
def update_race_participants():
    """
    AJAX route to update database with participant selections made on
    race_detail.html

    Return: none
    """
    try:
        # get data from client request
        client_data = request.get_json()

        print(' ')
        print('------- update_race_participants route beginning -------')

        # race is from databse, while client_data is from front end
        race = Race.query.get(client_data['race_id'])

        # print beginning summary information of race
        print(f"starting DB: race_id:{race.id}, name:{race.name}, "
              f"gender:{race.gender}, participantCount:{len(race.results)}")

        # determine if any runners were added to the race and add them
        # to the database
        current_runner_ids = [res.runner_id for res in race.results]
        new_runner_ids = [int(id) for id in client_data['participants']]
        for n_id in new_runner_ids:
            if n_id not in current_runner_ids:
                # get the runner object
                r = Runner.query.get(n_id)

                # get the corresponding team
                team = [t for t in race.teams if t in r.teams][0]

                # create a result for the runner
                res = Result(time=r.seed_time,
                             runner_id=r.id,
                             race_id=race.id,
                             team_id=team.id)
                db.session.add(res)

        # determine if any runners were removed from the race and remove
        # them from the database
        for c_id in current_runner_ids:
            if c_id not in new_runner_ids:
                res = Result.query.filter_by(runner_id=c_id,
                                             race_id=race.id).first()
                db.session.delete(res)

        # commit changes to database
        db.session.commit()

        # print ending summary information of race
        print(f"ending DB: race_id:{race.id}, name:{race.name}, "
              f"gender:{race.gender}, participantCount:{len(race.results)}\n")

        # Pass JSON_received to the frontend
        JSON_received = {'Status':'Received race'}
        return jsonify(JSON_received)

    except Exception as e:
        print("AJAX excepted " + str(e))
        return str(e)


@setup.route("/duplicate_race", methods=['POST'])
@login_required
def duplicate_race():
    """
    AJAX route to duplicate the race meta data to create a group of races.
    This is called at the beginning of race_detail.html when asked how many
    races will be run

    Return: none
    """
    try:
        client_data = request.get_json()
        print('\n------- duplicate_race route beginning -------')

        # race is from databse, while client_data is from front end
        race = Race.query.get(client_data['race_id'])

        # print beginning summary information of race
        print(f"current: race_id:{race.id}, name:{race.name}, "
              f"gender:{race.gender}, group_id:{race.group_id}")

        # set the group_id
        temp_races_array = Race.query.order_by(desc(Race.group_id)).all()
        for r in temp_races_array:
            if r.group_id:
                max_group_id = r.group_id
                break
        race.group_id = max_group_id + 1
        db.session.commit()

        # if more than one race, create new races with corresponding group_id
        newRace = []
        races_count = int(client_data['races_count'])
        for i in range(races_count - 1):
            newRace.append(Race(user_id=race.user_id, date=race.date))
            newRace[i].host_school_id = race.host_school_id
            newRace[i].location_id = race.location_id
            newRace[i].course_id = race.course_id
            newRace[i].group_id = race.group_id
            newRace[i].schools = race.schools
            db.session.add(newRace[i])
            db.session.commit()
        print(f"created {races_count - 1} new race(s)")

        # print ending summary information of race
        print(f"updating to: race_id:{race.id}, name:{race.name}, "
              f"gender:{race.gender}, group_id:{race.group_id}\n")

        # Pass JSON_received to the frontend
        JSON_received = {'Status':'Received race'}
        return jsonify(JSON_received)

    except Exception as e:
        print("AJAX excepted " + str(e))
        return str(e)


@setup.route("/<int:race_id>/add_location", methods=['GET', 'POST'])
@login_required
def add_location(race_id):
    """
    Route to add a location and a course to the database. This route is called
    from race_setup.html

    Return: render add_location.html
    """
    # use the LocationCourseForm
    form = LocationCourseForm()

    # confirm this is a post request and all fields are valid
    if form.validate_on_submit():
        # get race from database
        race = Race.query.get(race_id)
        host = race.host_school

        # create location and update database
        location = Location(
            name = form.location_name.data,
            street_address = (f"{form.street_number.data} "
                              f"{form.street_name.data}"),
            city = form.city.data,
            state_abbr = form.state_abbr.data,
            zip = form.zip.data
        )
        db.session.add(location)
        db.session.commit()
        host.locations.append(location)
        db.session.commit()

        # create course and update database
        course = Course(name=form.course_name.data,
                        description = form.course_description.data,
                        distance = form.distance.data,
                        location_id=location.id
                        )
        db.session.add(course)
        db.session.commit()
        race.location_id = location.id
        race.course_id = course.id
        db.session.commit()

        # set flash to notify user that location/course setup was successfull
        flash(f"Successfullly added course: '{course.name}' at location:"
              f"'{location.name}'", 'success')

        # return to race_setup.html
        return redirect(url_for('setup.race_setup', race_id=race_id))

    # if this is get request, render add_location.html
    return render_template('add_location.html', form=form)


@setup.route("/autocomplete_possibilities", methods=['GET', 'POST'])
@login_required
def autocomplete_possibilities():
    """
    AJAX route to query goolge places API to autocomplete address fields of
        user supplied location. client_data contains input and sessiontoken

    Return: data = [{'value: str of place_id', 'text': str description }]
    """
    try:
        # get data sent by client
        typed_input = request.args.get('q')
        print(' ')
        print('\n------ getting autocomplete_possibilities ------')
        print(f"recived: input:{typed_input}")

        # call the google API
        results = gmaps.places_autocomplete(typed_input)
        data = [
            {'value': r['place_id'], 'text': r['description']}
            for r in results
        ]

        # Pass data to the front end
        print(f'returning: {data}')
        return jsonify(data)

    except Exception as e:
        print("AJAX excepted " + str(e))
        return str(e)


@setup.route("/get_autofill_address", methods=['GET', 'POST'])
@login_required
def get_autofill_address():
    """
    AJAX route to query goolge places API to get address fields of user
    supplied location.

    Return: data = {
        'street_number': str,
        'route': str street_name,
        'locality': str city,
        'administrative_area_level_1': str state_abbr,
        'postal_code': str zip,
    }
    """
    try:
        # get data sent by client
        client_data = request.get_json()
        print(' ')
        print('\n------ getting autofill_address ------')
        print(f"recived: input:{client_data['text']}")

        place = gmaps.place(client_data['value'])
        address = place['result']['address_components']
        data = {}
        for field in address:
            if 'street_number' in field['types']:
                data['street_number'] = field['short_name']
                continue
            if 'route' in field['types']:
                data['route'] = field['long_name']
                continue
            if 'locality' in field['types']:
                data['locality'] = field['long_name']
                continue
            if 'administrative_area_level_1' in field['types']:
                data['administrative_area_level_1'] = field['short_name']
                continue
            if 'postal_code' in field['types']:
                data['postal_code'] = field['short_name']
                continue

        # Pass data to the front end
        print(f'returning: {data}')
        return jsonify(data)

    except Exception as e:
        print("AJAX excepted " + str(e))
        return str(e)


@setup.route("/<int:race_id>/add_course", methods=['GET', 'POST'])
@login_required
def add_course(race_id):
    """
    Route to add a course to the database. This route is called from
    race_setup.html

    Return: render add_course.html
    """
    # use the CourseForm
    form = CourseForm()

    # check if this is a post request and all fields are valid
    if form.validate_on_submit():
        # get race object from database
        race = Race.query.get(race_id)
        host = race.host_school
        location = race.location

        # create a new course based on input on form from user
        course = Course(name=form.course_name.data,
                        description = form.course_description.data,
                        distance = form.distance.data,
                        location_id=location.id)

        # add course to database and commit changes
        db.session.add(course)
        db.session.commit()

        # set course for race to the newly created course and commit changes
        race.course_id = course.id
        db.session.commit()

        # set flash to notify user that course setup was successfull
        flash(f"Successfullly added course: '{course.name}' at location:"
              f"'{location.name}'", 'success')

        # return to race_setup.html
        return redirect(url_for('setup.race_setup', race_id=race_id))

    # if this is get request, render add_course.html
    return render_template('add_course.html', form=form)


@setup.route("/<int:race_id>/bibs", methods=['GET', 'POST'])
@login_required
def bibs(race_id):
    """
    Route to assign bib numbers to participants in a race. This route will
    determine pass the race object along with a list of schools competing
    in any of the group races (not just this one) to bibs.html

    Return: render bibs.html
    """
    # get the race object from database
    race = Race.query.get(race_id)

    # Print race info at the start of process
    print('\n------- bibs route beginning -------')

    # If race is already completed, go to results
    if race.status == 'complete':
        return redirect(url_for('races.results', race_id=race.id))

    # Get all schools in this race group
    group_races = Race.query.filter_by(group_id=race.group_id).all()
    schools = []
    for race in group_races:
        schools.extend(race.schools)
    schools_set = set(schools)
    schools = list(schools_set)
    print(f"race_group:{race.group_id} schools:{schools}")

    # Sort the schools by long_name
    schools.sort(key=lambda s: s.long_name, reverse=False)

    return render_template('bibs.html', race=race, schools=schools)


@setup.route("/participants_for_bib_assignment", methods=['POST'])
@login_required
def participants_for_bib_assignment():
    """
    AJAX route to provide participant and school information when the user
        clicks a particular school for which to make bib assignments

    Return: data, a dictionary containing race, school and runner information
            needed to upate bibs.html as user selects different schools for
            which to make bib assignments
    """
    try:
        # get data sent by client
        client_data = request.get_json()
        print(' ')
        print('\n------ participants_for_bib_assignment route beginning ------')
        print(f"recived: race_id:{client_data['race_id']}")

        # race is from databse, while client_data is from front end
        race = Race.query.get(client_data['race_id'])

        # get all races in this race group
        group_races = Race.query.filter_by(group_id=race.group_id).all()

        # if client_data contains 'status' then update database and return
        if 'status' in client_data:
            for r in group_races:
                r.status = client_data['status']
            db.session.commit()
            return jsonify({'Status':'Updated Race Status to ready'})

        # get all schools in this race group
        schools = []
        for race in group_races:
            schools.extend(race.schools)
        schools_set = set(schools)
        schools = list(schools_set)

        # begin building the data objec that will be returned to client
        data = {'race_id': race.id}

        # add school information to data
        data['schools'] = [
            {
                'school_id': school.id,
                'school_name': school.short_name,
                'primary_color': school.primary_color,
                'text_color': school.text_color,
            }
            for school in schools
        ]

        # add participants to the data object
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
            for race in group_races
            for res in race.results
        ]

        # Pass participants to the frontend
        return jsonify(data)

    except Exception as e:
        print("AJAX excepted " + str(e))
        return str(e)


@setup.route("/update_bib_assignments", methods=['POST'])
@login_required
def update_bib_assignments():
    """
    AJAX route to update the database for any bib assignments or changes

    Return: none
    """
    try:
        # get data sent by client
        client_data = request.get_json()

        # print starting state of database
        print(' ')
        print('------- update_bib_assignments route beginning -------')
        print(f"recived: race_id:{client_data['race_id']} "
              f"schools:{len(client_data['schools'])} "
              f"participants:{len(client_data['participants'])}")

        # Retrieve bib number from client data and assign to result
        for p in client_data['participants']:
            res = Result.query.get(p['result_id'])
            res.bib = p['bib']

        # commit changes to database
        db.session.commit()

        # Pass JSON_received to the frontend
        JSON_received = {'Status':'Received race'}
        return jsonify(JSON_received)

    except Exception as e:
        print("AJAX excepted " + str(e))
        return str(e)


@setup.route("/email_bibs", methods=['GET', 'POST'])
@login_required
def email_bibs():
    """
    AJAX route to email bib assignments to addresses provided by user.  The
    message is a simple plain-text list for clarity

    Return: none
    """
    try:
        # get data sent by client
        client_data = request.get_json()
        print(' ')
        print('------- email_bibs route beginning -------')
        print(f"recived: {client_data}")

        # race is from databse, while client_data is from front end
        race = Race.query.get(client_data['race_id'])

        # create subject string for email
        subject = (f"Bib Assingments for race at {race.location.name} "
                  f"on {race.display_date()}")

        # create message object
        msg = Message(
            subject,
            sender = ('New England Prep XC','neprepxc@gmail.com'),
            recipients=[client_data['recipients']]
        )

        # utilize message body provided by client
        msg.body = client_data['messageBody']

        # send message
        mail.send(msg)

        # Pass JSON_received to the frontend
        JSON_received = {'Status':'Received race'}
        return jsonify(JSON_received)

    except Exception as e:
        print("AJAX excepted " + str(e))
        return str(e)


@setup.route("/choose_school", methods=['GET', 'POST'])
@login_required
def choose_school():
    """
    Select a school to which to add/edit/remove a runner

    Return: renders add_school.html
    """
    if current_user.is_administrator():
        schools = School.query.order_by(School.long_name)
    else:
        schools = current_user.schools_coached

    # if initial get request, render add_school.html
    return render_template('choose_school.html', schools=schools)


@setup.route("/<int:race_id>/add_school", methods=['GET', 'POST'])
@login_required
def add_school(race_id):
    """
    Route to add a school to the database

    Return: renders add_school.html
    """
    # use the SchoolForm
    form = SchoolForm()

    # retrieve the list of all leagues from the database
    data = {'league_list': League.query.all()}

    # check if this is a post request and all fields are valid
    if form.validate_on_submit():
        # create the school object based on form input from user
        school = School(long_name = form.long_name.data,
                        short_name = form.short_name.data,
                        city = form.city.data,
                        state_abbr = form.state_abbr.data,
                        primary_color = form.primary_color.data,
                        secondary_color = form.text_color.data,
                        text_color = form.text_color.data,
                        league_id = form.league_id.data)

        # add school to database and commit
        db.session.add(school)
        db.session.commit()

        # make this user a coach for this school
        if not current_user.is_administrator():
            school.coaches.append(current_user)
            db.session.commit()

        # redirect to add_runner route
        return redirect(url_for('setup.add_runner',
                                race_id=race_id,
                                school_id=school.id,
                                gender_code=0))

    # if initial get request, render add_school.html
    return render_template('add_school.html', form=form, data=data)


@setup.route("/<int:race_id>/<int:school_id>/<int:gender_code>/add_runner", methods=['GET', 'POST'])
@login_required
def add_runner(race_id, school_id, gender_code):
    """
    Route to add a runner to the database

    Return: renders add_runner.html
    """
    # use RunnerForm
    form = RunnerForm()

    # get the basic information for this route from the database
    school = School.query.get(school_id)
    year = datetime.today().year

    # Begin to build the data object that will be sent to jinja
    data = {'race_id': race_id,
            'school_id': school_id,
            'school': school,
            'gender_code': gender_code,
            'year': year,}

    # determine if this user should be able to delete runners
    data['able_to_delete'] = (
        True if (current_user.id < 4
                 or school in current_user.schools_coached)
             else False
    )

    # if the race has participants already, then flag that so that the
    # "return to race setup" button can take them to race_detail instead
    # of race_setup
    if race_id == 0:
        data['return_page'] = f'/{school_id}/school'
    else:
        race = Race.query.get(race_id)
        if race.results:
            data['return_page'] = f'/{race_id}/race_detail'
        else:
            data['return_page'] = f'{race_id}/race_setup'

    print(' ')
    print('------- add_runner route beginning -------')
    print('Loading with:', data)

    # order the gender_list to display the chosen value. if this is the first
    # time through (i.e., the gender_code is still 0) return the basic template
    if gender_code == 1:
        gender = 'girls'
        data['gender_list']= ['Girls','Boys']
    elif gender_code == 2:
        gender = 'boys'
        data['gender_list'] = ['Boys','Girls']
    else:
        # this is the first time through and we can jump to rendering html
        data['gender_list'] = ['Girls','Boys']
        return render_template('add_runner.html', data=data, form=form)

    # get the team from the database
    team = Team.query.filter_by(school_id = school.id,
                                year=year,
                                gender=gender).first()
    print(team)
    # if the team does not yet exist, then create it
    if not team:
        team = Team(gender=gender,
                    year=year,
                    school_id=school.id)
        db.session.add(team)
        db.session.commit()

    # update the data object for the team and its roster of runners
    data['team'] = team
    data['team_id'] = team.id
    data['runners'] = team.alphabetized_runners()

    print('Data to Jinja: ', data)

    # if post request and form is valid, create runner object
    if form.validate_on_submit():
        minutes = form.minutes.data
        seconds = form.seconds.data
        seed_time = (minutes * 60 + seconds) * 1000
        runner = Runner(first_name = form.first_name.data,
                        last_name = form.last_name.data,
                        grad_year = form.grad_year.data,
                        seed_time = int(seed_time))

        # add runner to database and commit
        db.session.add(runner)
        db.session.commit()

        # associate runner with the current team and commit change
        team.runners.append(runner)
        db.session.commit()

        # check if runner already in the database, and if so go to
        # confirmation page
        potential_matches = (
            Runner.query.filter_by(last_name=runner.last_name).all()
        )

        # consider those who were at the same school and were removed
        matches = []
        for pmatch in potential_matches:
            if pmatch != runner:
                if pmatch.was_removed():
                    if pmatch.get_school() == school:
                        matches.append(pmatch)
                    elif pmatch.first_name == runner.first_name:
                        matches.append(pmatch)

        if matches:
            print(f'\nfound previously removed matching runners:{matches}')
            return render_template(
                'found_existing_runner.html',
                matches=matches,
                race_id=race_id,
                school_id=school_id,
                gender_code=gender_code,
                runner=runner
            )
        else:
            message = f'Successfully added {runner.display_name()} to database'
            print(message)
            flash(message, 'success')

        # render the page again to utilize the changes (i.e., displaying the
        # new runner among the team members)
        return redirect(url_for('setup.add_runner', gender_code=gender_code,
                                                    race_id=race_id,
                                                    school_id=school_id))

    # if this is not a form submission, render add_runner.html
    return render_template('add_runner.html', data=data, form=form)


@setup.route("/<int:race_id>/<int:school_id>/<int:gender_code>/<int:delete_runner_id>/<int:add_runner_id>/confirm_add_runner", methods=['GET','POST'])
@login_required
def confirm_add_runner(race_id, school_id, gender_code, delete_runner_id, add_runner_id):
    print(f' ')
    print(f'----------- starting confirm_add_runner route --------------')
    print(f'race:_id:{race_id}')
    print(f'school: {School.query.get(school_id)}')
    print(f'gender_code: {gender_code}')
    print(f'delete_runner: {Runner.query.get(delete_runner_id)}')
    print(f'add_runner: {Runner.query.get(add_runner_id)}')

    # get add_runner from database
    add_runner = Runner.query.get(add_runner_id)

    # If there is a runner to delete, delete that runner
    if delete_runner_id != 0:
        delete_runner = Runner.query.get(delete_runner_id)

        # delete any results with status = n
        delete_runner.delete_not_started_results()

        # remove from current team
        cur_team = delete_runner.current_year_team()
        if cur_team:
            print(f'removing {delete_runner} from {cur_team}')
            cur_team.runners.remove(delete_runner)
            db.session.commit()

        # delete runner if there are not completed results
        if delete_runner.completed_results():
            # create message
            flash_status = 'success'
            message = (f'{delete_runner} was removed from this team, but has'
                       f'results in the database and will not be deleted')
            print(message)
            flash(message,'success')
        else:
            # Create message
            flash_status = 'success'
            message = f'Successfully deleted {delete_runner} from the database.'
            flash(message,'success')
            print(message)

            db.session.delete(delete_runner)
            db.session.commit()

    # associate add_runner to the current team
    cur_year = datetime.today().year
    gender = 'girls' if gender_code == 1 else 'boys'
    team = Team.query.filter_by(school_id=school_id,
                                year=cur_year,
                                gender=gender).first()
    team.runners.append(add_runner)
    db.session.commit()
    message = f'successfully added {add_runner} to {team}'
    print(message)
    flash(message, 'success')

    return redirect(url_for('setup.add_runner', race_id=race_id,
                                                school_id=school_id,
                                                gender_code=gender_code))

@setup.route("/create_team_if_needed", methods=['POST'])
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


@setup.route("/edit_delete_runner", methods=['POST'])
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
        runner = Runner.query.get(runner_data['runner_id'])

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


@setup.route("/<int:race_id>/delete_race", methods=['GET', 'POST'])
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


@setup.route("/remove_demo")
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

@setup.route("/create_demo")
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
    random.shuffle(pairs)

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
                this_time = runner.seed_time + random.randint(-5000,5000)
                result = Result(
                    place=this_time,
                    runner_id=runner.id,
                    race_id=race.id,
                    team_id=team.id
                )
                db.session.add(result)
                db.session.commit()
                result.bib = bib
                bib += 1
                result.time = this_time
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


@setup.route("/roll_back_demo")
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
