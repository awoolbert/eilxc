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
from typing import List, Tuple, Optional
import re
from fuzzywuzzy import fuzz

# hsxc imports
from hsxc import db, mail
from hsxc import celery
from hsxc.models import User, League, School, Runner, Team, Race
from hsxc.models import Result, RaceScore, Location, Course
from hsxc.helpers import CUR_YEAR
from hsxc.controllers.db_admin.forms import LocationCourseForm, CourseForm
from hsxc.controllers.db_admin.forms import SchoolForm, ConfirmAddTeamForm
from hsxc.controllers.db_admin.forms import RunnerForm
from hsxc.controllers.core.views import async_update_seed_times
from hsxc.controllers.core.views import async_update_all_seed_times
from hsxc.controllers.core.views import async_update_league_standings

db_admin = Blueprint('db_admin', __name__)

# ------------------------- add_location -------------------------
@db_admin.route("/<int:race_id>/add_location", methods=['GET', 'POST'])
@db_admin.route("/add_location", methods=['GET', 'POST'])
@login_required
def add_location(race_id: int = 0):
    form = LocationCourseForm()

    if not form.validate_on_submit():
        return render_template('add_location.html', form=form)

    location = build_location_from_form(form)
    course = build_course_from_form(form, location)
    flash(f"Added '{course.name}' at '{location.name}'", 'success')

    if race_id != 0:
        associate_location_and_course_with_race(race_id, location, course)
        return redirect(url_for('race_setup.race_metadata', race_id=race_id))

    return redirect(url_for('core.index'))

def build_location_from_form(form: LocationCourseForm) -> Location:
    street_address = f'{form.street_number.data} {form.street_name.data}'
    location = Location(
        name=form.location_name.data,
        street_address=street_address,
        city=form.city.data,
        state_abbr=form.state_abbr.data,
        zip=form.zip.data
    )
    db.session.add(location)
    db.session.commit()
    return location

def build_course_from_form(
    form: LocationCourseForm, 
    location: Location
) -> Course:
    course = Course(
        name=form.course_name.data,
        description=form.course_description.data,
        distance=form.distance.data,
        location_id=location.id
    )
    db.session.add(course)
    db.session.commit()
    return course

def associate_location_and_course_with_race(
    race_id: int, 
    location: Location, 
    course: Course
) -> None:
    race: Race = Race.query.get(race_id)
    host: School = race.host_school
    host.locations.append(location)
    race.location_id = location.id
    race.course_id = course.id
    db.session.commit()


# ------------------------- add_course -------------------------
@db_admin.route("/select_location", methods=['GET'])
@login_required
def select_location() -> None:
    location_list: List[Location] = Location.query.all()
    return render_template('select_location.html', location_list=location_list)

@db_admin.route("/add_course", methods=['GET', 'POST'])
@db_admin.route("/add_course/<int:location_id>", methods=['GET', 'POST'])
@db_admin.route("/<int:race_id>/add_course", methods=['GET', 'POST'])
@login_required
def add_course(race_id: int = 0, location_id: int = 0) -> None:
    if location_id == 0 and race_id == 0:
        return redirect(url_for('db_admin.select_location'))

    form = CourseForm()
    location_list: List[Location] = Location.query.all()

    if location_id != 0:
        location = Location.query.get(location_id)
    elif race_id != 0:
        race: Race = Race.query.get(race_id)
        location: Location = race.location

    location_list.remove(location)

    if not form.validate_on_submit():
        return render_template(
            'add_course.html', 
            form=form, 
            location=location, 
            location_list=location_list
        )

    course = create_course_from_form(form, location)
    if race_id != 0:
        race.course_id = course.id
        db.session.commit()

    flash(f"Added course: '{course.name}' at '{location.name}'", 'success')
    return redirect(url_for('race_setup.race_metadata', race_id=race_id))

def create_course_from_form(form: CourseForm, location: Location) -> Course:
    course = Course(
        name=form.course_name.data,
        description=form.course_description.data,
        distance=form.distance.data,
        location_id=location.id
    )
    db.session.add(course)
    db.session.commit()
    return course


# ------------------------- add_school -------------------------
@db_admin.route("/add_school", methods=['GET', 'POST'])
@db_admin.route("/<int:race_id>/add_school", methods=['GET', 'POST'])
@login_required
def add_school(race_id: int = 0) -> None:
    form = SchoolForm()
    leagues: List[League] = League.query.all()

    if not form.validate_on_submit():
        return render_template('add_school.html', form=form, leagues=leagues)

    school = create_school_from_form(form)

    if not current_user.is_administrator():
        school.coaches.append(current_user)
        db.session.commit()

    flash(f"Added school: '{school.long_name}'", 'success')
    if race_id != 0:
        url = url_for('db_admin.add_team', race_id=race_id, school_id=school.id)
    else:
        url = redirect(url_for('core.index'))
    return redirect(url)

def create_school_from_form(form: SchoolForm) -> School:
    school = School(
        long_name=form.long_name.data,
        short_name=form.short_name.data,
        city=form.city.data,
        state_abbr=form.state_abbr.data,
        primary_color=form.primary_color.data,
        secondary_color=form.secondary_color.data,
        text_color=form.text_color.data,
        league_id=form.league_id.data
    )
    db.session.add(school)
    db.session.commit()
    return school


# ------------------------- add_team -------------------------
@db_admin.route("/<int:school_id>/<int:race_id>/add_team", methods=['GET'])
@db_admin.route("/<int:school_id>/add_team", methods=['GET'])
@login_required
def add_team(school_id: int, race_id: int = 0) -> None:
    school: School = School.query.get(school_id)
    gender_list = [(1,'Girls'), (2, 'Boys')]

    return render_template(
        'add_team.html',
        school=school,
        race_id=race_id,
        gender_list=gender_list,
    )

@db_admin.route(
        "/<int:school_id>/<int:race_id>/<int:gender_code>/create_team", 
        methods=['GET', 'POST'])
@login_required
def create_team(
    school_id: int, 
    race_id: int, 
    gender_code: int, 
) -> None:
    form = ConfirmAddTeamForm()
    school: School = School.query.get(school_id)
    gender = 'girls' if gender_code == 1 else 'boys'

    if form.validate_on_submit():
        if form.confirm.data:
            team = create_team_if_needed(school, gender, CUR_YEAR)
            return redirect(url_for(
                'core.roster',
                team_id=team.id,
                race_id=race_id,
                step=0
            ))
        if form.cancel.data:
            return redirect(url_for(
                'db_admin.add_team',
                school_id=school_id,
                race_id=race_id
            ))
        
    # warn if adding a new sex to school teams
    teams: List[Team] = school.teams
    is_new_gender = len(teams) > 1 and all(t.gender != gender for t in teams)
    if is_new_gender:
        return render_template(
            'confirm_create_team.html',
            form=form,
            school=school,
            race_id=race_id,
            gender_code=gender_code,
            gender=gender
        )
    else:
        team = create_team_if_needed(school, gender, CUR_YEAR)
        return redirect(url_for(
            'core.roster',
            team_id=team.id,
            race_id=race_id,
            step=0
        ))

def create_team_if_needed(
    school: School, 
    gender: str, 
    year: int = CUR_YEAR
) -> Team:
    # return team if it already exists
    team = Team.query.filter_by(
        gender=gender, year=year, school_id=school.id
    ).first()
    if team:
        return team
    
    # create team if it doesn't exist
    team = Team(gender=gender, year=year, school_id=school.id)
    db.session.add(team)
    db.session.commit()

    return team


