# external imports
from flask import render_template, url_for, redirect, request, Blueprint
from flask import session, jsonify, Response
from flask_login import login_required
import os
import pickle
from typing import Dict, List, Union
from pprint import pprint
import json

# hsxc imports
from hsxc import db
from hsxc.models import School, Runner, Team, Race, Course, Location, NonDuplicate
from .uploader import ResFile, ResFileBuilder, ResFileProcessor 
from .uploader import find_runners_needing_merge, merge_runners
from .forms import UploadForm, RaceImportForm
from hsxc import files
from hsxc.controllers.race_upload.exporter_loader import RaceDataImporter

race_upload = Blueprint('race_upload', __name__)


# *****************************************************************************
# Routes for the automated export and import of race data
# *****************************************************************************

@race_upload.route('/<int:race_id>/export_race_data', methods=['GET'])
@login_required
def export_race_data(race_id):
    race = Race.query.get(race_id)
    print('\n------------------ beginning export_race_data ------------------')
    print(f' exporting data for: {race}')
    data_dict = {
        'race'    : race.to_dict(),
        'schools' : [school.to_dict() for school in race.schools],
        'teams'   : [team.to_dict() for team in race.teams],
        'location': race.location.to_dict(),
        'course'  : race.course.to_dict(),
        'runners' : [
            runner.to_dict() for runner in [r.runner for r in race.results]
        ],
        'results' : [res.to_dict() for res in race.results]
    }

    print(' exported the following data to file download') 
    pprint(data_dict)
    json_str = json.dumps(data_dict)
    fname = f'race_{race_id}_export.json'

    return Response(
        json_str,
        mimetype="application/json",
        headers={"Content-disposition": f"attachment; filename={fname}"}
    )


@race_upload.route('/import_race_data', methods=['GET', 'POST'])
@login_required
def import_race_data():
    """
    Upload a race_data json file for processing and adding to the database.
    """
    print('\n------------------ beginning import_race_data ------------------')

    form = RaceImportForm()
    if form.validate_on_submit():
        # upload the file to the server
        uploaded_file = request.files['file']
        filename = files.save(uploaded_file)
        fpath = files.path(filename)
        print(f' successfully uploaded file to {fpath}')

        # convert the file to a json object
        with open(fpath, 'r') as f:
            json_str = f.read()
            data = json.loads(json_str)
        
        # process file
        race = RaceDataImporter(data).build_race_from_file()

        # delete the uploaded file from the server
        os.remove(fpath)
        print(f' deleted uploaded file from {fpath}')

        return redirect(url_for('races.results', race_id=race.id))

    return render_template('import_race_data.html', form=form)


# *****************************************************************************
# Routes for the upload of a manually created results text file
# *****************************************************************************

@race_upload.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """
    Upload a results file for processing and adding to the database.
    """
    print('\n---------------------- beginning upload- ------------------------')

    form = UploadForm()
    if form.validate_on_submit():

        # upload the file to the server
        uploaded_file = request.files['file']
        filename = files.save(uploaded_file)
        fpath = files.path(filename)
        print(f' successfully uploaded file to {fpath}')

        # convert the results file to a ResFileConverter object
        res_file = ResFileBuilder().build_from_file(fpath)
        session['res_file'] = pickle.dumps(res_file)
        print(f' created ResFile object from: {fpath}')

        # delete the uploaded file from the server
        os.remove(fpath)
        print(f' deleted uploaded file from {fpath}')

        return redirect(url_for('race_upload.process_results_file', step=1))

    return render_template('upload_results.html', form=form)


@race_upload.route("/process_results_file/<int:step>")
@login_required
def process_results_file(step:int):
    """
    Process an uploaded results file and add the results to the database.
    """
    print(f'\n-------- beginning process_results_file: Step {step} -----------')

    # get the results file from the session
    res_file:ResFile = pickle.loads(session['res_file'])
    print(f' processing results from file: {res_file.fpath}')

    # step 1: confirm the school mapping
    if step == 1:
        print(' getting school mapping from the results file...')
        res_file = ResFileProcessor(res_file).create_school_map()

        # convert map to provide school object(s) instead of ids
        smap:Dict[str,Union[School, List[School]]] = {}
        for school_str, school_id in  res_file.school_map.items():
            if isinstance(school_id, list):
                schools =[School.query.get(s_id) for s_id in school_id]
            else:
                schools = School.query.get(school_id)
            smap[school_str] = schools
        session['res_file'] = pickle.dumps(res_file)

        print(' initial school mapping sent to user:')
        for school_str, schools in smap.items():
            is_list = isinstance(schools, list)
            if is_list:
                map_res = schools if len(schools) < 5 else 'No matches'
            else:
                map_res = schools
            print(f'  {school_str} -> {map_res}')

        return render_template('confirm_school_mapping.html', school_map=smap)

    # step 2: confirm race_name, race_date, race_location, race_course
    elif step == 2:
        print(' getting race meta data from the results file...')
        res_file = ResFileProcessor(res_file).set_race_meta_data()

        # get race_name
        race_name = res_file.race_name
        
        # get gender list and set order
        gender = ['Boys', 'Girls', 'Both']
        if res_file.race_gender == 'girls':
            gender = ['Girls', 'Boys', 'Both']

        # get Varsity or JV list and set order
        v_jv = ['Varsity', 'JV']
        if res_file.race_varsity_jv == 'jv':
            v_jv = ['JV', 'Varsity']

        # set scoring_type list and set order
        scoring = ['Dual Meet(s)', 'Invitational']
        if res_file.race_scoring_type == 'invitational':
            scoring = ['Invitational', 'Dual Meet(s)']
        
        # set date
        race_date = res_file.race_date.strftime('%m/%d/%Y')

        # set location and course
        l_ids = res_file.race_location_id
        print(l_ids)
        if isinstance(l_ids, list):
            locations = [Location.query.get(l_id) for l_id in l_ids]
            location = Location.query.get(res_file.race_location_id[0])
            courses = location.courses
        else:
            locations = Location.query.get(l_ids)
        print(locations)

        # pass meta data to the template
        meta_data = {
            'Race Name': race_name,
            'Gender': gender,
            'Varsity or JV': v_jv,
            'Scoring': scoring,
            'Date': race_date,
            'Location': locations,
            'Course': courses,
        }
        return render_template('confirm_meta_data.html', meta_data=meta_data)

    # step 3: confirm runners
    elif step == 3:
        print(' getting runner mapping from the results file...')
        res_file = ResFileProcessor(res_file).create_runner_map()
        smap = res_file.school_map
        rmap = res_file.runner_map.copy()

        # build list of dicts to pass to the template
        rows = []
        for idx, runner_id in rmap.items():
            row = res_file.data[idx].copy()
            row['idx'] = idx

            # prepare the runner's name from file for display
            rname = f"{row['first_name']} {row['last_name']}"
            rname += f" {row['grad_year']}" if row['grad_year'] else ''
            row['name_in_file'] = rname

            # get school.short_name, school.primary_color, school.text_color
            school_id = smap[row['school']]
            school = School.query.get(school_id)
            row['school_short_name'] = school.short_name
            row['school_primary_color'] = school.primary_color
            row['school_text_color'] = school.text_color

            # add runner(s)
            if isinstance(runner_id, list):
                row['exact_match'] = False
                runners = [Runner.query.get(r_id) for r_id in runner_id]
                row['runners'] = runners
            else:
                row['exact_match'] = True
                row['runner'] = Runner.query.get(runner_id)

            rows.append(row)

        print(' initial runner mapping sent to user:')
        for row in rows:
            if row['exact_match']:
                print(f'  {row["name_in_file"]} -> {row["runner"]}')
            else:
                print(f'  {row["name_in_file"]} -> {row["runners"]}')

        session['res_file'] = pickle.dumps(res_file)
        session['rows'] = pickle.dumps(rows)

        return render_template('confirm_runner_mapping.html', rows=rows)

    # step 4: build race and results and add to the database
    elif step == 4:
        race_id = ResFileProcessor(res_file).finalize_race()
        return redirect(url_for('races.results', race_id=race_id))

    return redirect(url_for('users.home'))


@race_upload.route('/confirm_school_mapping', methods=['POST'])
@login_required
def confirm_school_mapping():
    print(f'\n-------------- beginning confirm_school_mapping ---------------')

    # report on the user's confirmed school mapping
    confirmed_map = request.form
    print('User confirmed the following school mapping:')
    for school_str, school_id in confirmed_map.items():
        if school_id.isnumeric():
            school = School.query.get(int(school_id))
            print(f'  {school_str} -> {school}')
        else:
            school = School.query.filter_by(long_name=school_id).first()
            print(f'  {school_str} -> {school}')

    # update the school map and save it to the session
    res_file = pickle.loads(session['res_file'])
    res_file = ResFileProcessor(res_file).confirm_school_mapping(confirmed_map)
    session['res_file'] = pickle.dumps(res_file)
    return redirect(url_for('race_upload.process_results_file', step=2))    


@race_upload.route('/get-courses', methods=['POST'])
def get_courses_for_location():
    location_id = request.form.get('location_id')
    courses = Course.query.filter_by(location_id=location_id).all()
    course_list = [{'id': course.id, 'name': course.name} for course in courses]
    return jsonify(course_list)


@race_upload.route('/confirm_meta_data', methods=['POST'])
@login_required
def confirm_meta_data():
    print(f'\n-------------- beginning confirm_meta_data ---------------')

    # report on the user's selections
    selections:dict[str,str] = request.form
    print('User confirmed the following meta data:')
    for category, selection in selections.items():
        if category == 'Course':
            course = Course.query.get(int(selection))
            print(f'  {category} -> {course}')
        elif category == 'Location':
            location = Location.query.get(int(selection))
            print(f'  {category} -> {location}')
        else:
            print(f'  {category} -> {selection}')

    # update the school map and save it to the session
    res_file = pickle.loads(session['res_file'])
    res_file = ResFileProcessor(res_file).confirm_race_meta_data(selections)
    session['res_file'] = pickle.dumps(res_file)
    return redirect(url_for('race_upload.process_results_file', step=3))    


@race_upload.route('/confirm_runner_mapping', methods=['POST'])
@login_required
def confirm_runner_mapping():
    print(f'\n-------------- beginning confirm_runner_mapping ---------------')
    res_file = pickle.loads(session['res_file'])
    rows = pickle.loads(session['rows'])
    rmap = {}

    # report on the user's confirmed runner mapping
    confirmed_map = request.form
    print(confirmed_map)
    print(' user confirmed the following runner mapping:')
    for idx, runner_id in confirmed_map.items():
        row = next(r for r in rows if r['idx'] == int(idx))
        if runner_id == '-1':
            rmap[int(idx)] = None
            print(f"  {row['name_in_file']} -> None")
        elif runner_id.isnumeric():
            rmap[int(idx)] = int(runner_id)
            runner = Runner.query.get(int(runner_id))
            print(f"  {row['name_in_file']} -> {runner}")
        elif row['exact_match']:
            runner_id = res_file.runner_map[int(idx)]
            rmap[int(idx)] = runner_id
            runner = Runner.query.get(runner_id)
            print(f"  {row['name_in_file']} -> {runner}")

    # update the runner map and save it to the session
    res_file = ResFileProcessor(res_file).confirm_runner_mapping(rmap)
    session['res_file'] = pickle.dumps(res_file)
    session.pop('rows')
    return redirect(url_for('race_upload.process_results_file', step=4))    


# *****************************************************************************
# Routes to repair any errors created in manual race uploading
# *****************************************************************************

@race_upload.route('/find_duplicate_runners', methods=['GET', 'POST'])
@login_required
def find_duplicate_runners():
    print('\n--------------- beginning find_duplicate_runners ---------------')
    duplicates = find_runners_needing_merge()
    return render_template('find_duplicate_runners.html', pairs=duplicates)


@race_upload.route('/merge_runners/<int:id1>/<int:id2>', methods=['POST'])
@login_required
def merge_runners_route(id1, id2):
    print('\n--------------- beginning merge_runners ---------------')
    r1 = Runner.query.get(id1)
    r2 = Runner.query.get(id2)

    if r1 is None or r2 is None:
        return jsonify(success=False, message="Runner not found"), 404

    try:
        print(f'merging {r1} and {r2}')
        merge_runners(r1, r2)
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

    return jsonify(success=True, message="Runners merged successfully"), 200


@race_upload.route('/mark_not_duplicates/<int:id1>/<int:id2>', methods=['GET'])
@login_required
def mark_not_duplicates(id1: int, id2: int):
    min_id = min(id1, id2)
    max_id = max(id1, id2)
    r1 = Runner.query.get(min_id)
    r2 = Runner.query.get(max_id)
    print(f'marking {r1} and {r2} as not duplicates')
    non_duplicate_pair = NonDuplicate(runner1_id=min_id, runner2_id=max_id)
    db.session.add(non_duplicate_pair)
    db.session.commit()

    return redirect(url_for('race_upload.find_duplicate_runners'))


@race_upload.route('/ensure_races_added_to_schools_and_teams', methods=['GET'])
@login_required
def ensure_races_added_to_schools_and_teams():
    all_races = Race.query.all()
    all_teams = Team.query.all()

    for team in all_teams:
        print(f'{team}: {len(team.races)} races')
        for race in team.races:
            if team.school not in race.schools:
                race.schools.append(team.school)
                print(f' added {team.school} to {race}')
                db.session.commit()

    print('')
    for race in all_races:
        print(f'{race}: {len(race.schools)} schools')

    # for team in all_teams:
    #     print(f' team: {team}, school: {team.school}')

    return redirect(url_for('users.home'))
