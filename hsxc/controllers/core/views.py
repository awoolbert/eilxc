# external imports
from flask import request, jsonify
from flask import render_template, url_for, flash, redirect, Blueprint
from flask_login import current_user, login_required
from typing import List, Dict, Tuple, OrderedDict
from collections import OrderedDict
import time
import re
from fuzzywuzzy import fuzz


# hsxc imports
from hsxc import celery, db
from hsxc.models import League, School, Runner, Team
from hsxc.models import Race, Course, Result, Location
from hsxc.helpers import CUR_YEAR, timify
from hsxc.controllers.core.forms import RunnerForm
from hsxc.builders.team_record import TeamRecordBuilder
from hsxc.builders.team_record import LeagueStandingsBuilder
from hsxc.builders.course_normalizer import CourseAdjuster
from hsxc.builders.course_normalizer import YearEndEffectCalculator
from hsxc.builders.course_normalizer import update_all_course_adjustments
from hsxc.builders.times_graph import RunnerGraphBuilder

core = Blueprint('core',__name__)


# ----------------------------------- index -----------------------------------
@core.route('/')
def index():
    """
    Route to simply display index.html.  Route is often called after invalid
    actions

    Return: render index.html
    """
    # TODO: each user should see only a set of relevant schools

    # get leagues
    leagues = League.query.all()

    return render_template('index.html', leagues=leagues)


# ---------------------------------- league ----------------------------------
@core.route('/<int:league_id>/league/<int:year>')
@core.route('/<int:league_id>/league')
@login_required
def league(league_id, year=CUR_YEAR):
    """
    Route to display the league standings tables for the current season

    Return: render league.html
    """
    t0 = time.time()
    league: League = League.query.get(league_id)
    print('\n-------------------- starting league route --------------------')
    print(f'league: {league.long_name} ({league.short_name})')

    years = build_list_of_possible_years(league)
    championships, champs = assemble_championship_race_info(league, year)
    standings = get_league_standings(league, year)
    leaderboards = create_leaderboards(league, None, year, 20, False)

    print(f'\n completed route in {round(time.time()-t0,2)} seconds\n')

    # render runner.html
    return render_template(
        'league.html', 
        league = league,
        championships = championships,
        champs = champs if champs else None,
        standings = standings,
        img_width = f'10%',
        year = year,
        years = years,
        leaderboards = leaderboards,
    )

def build_list_of_possible_years(league: League) -> List[int]:
    years = list({t.year for school in league.schools for t in school.teams})
    years.sort(reverse=True)
    return years

def assemble_championship_race_info(
    league: League, 
    year: int
) -> Tuple[List[Race], Dict[str, School]]:
    # find championship meet if exists
    all_races: List[Race] = Race.query.all()
    championships: List[Race] = [
        r for r in all_races 
        if r.status == 'complete'
        and (league.short_name in r.name or league.long_name in r.name)
        and r.is_championship()
        and r.date.year == year
    ]

    # sort the championship races (V-girls, V-boys, JV-girls, JV-boys)
    if championships:
        championships.sort(key=lambda r: (-r.is_jv, r.gender), reverse=True)
        championships.sort(key=lambda r: r.date.date(), reverse=True)

    # idenify the championship schools
    if championships:
        champs = [School.query.get(r.winner_id) for r in championships[0:2]]
        champs = dict(zip(['girls', 'boys'], champs))
    else: 
        champs = None

    return championships, champs

def get_league_standings(league: League, year: int) -> Dict[str, List[Team]]:
    standings: Dict[str, List[Team]] = {'Girls':[], 'Boys':[]}
    for gender in ['Girls', 'Boys']:
        standings[gender] = [
            t for school in league.schools for t in school.teams
            if t.gender == gender.lower() and t.year == year
        ]
        standings[gender].sort(key=lambda t: t.rank())
    return standings

def create_leaderboards(
    league: League = None,
    school: School = None,
    year: int = None,
    num_results: int = 100,
    include_championships: bool = True,
) -> Dict[str, List[Result]]:
    # identify school or schools for this leaderboard
    if school is not None:
        schools = [school]
    else:
        schools: List[School] = School.query.all()
        if league is not None:
            schools = [s for s in schools if s in league.schools]

    # limit to appropriate year if needed
    teams: List[Team] = [t for school in schools for t in school.teams]
    if year != 0:
        teams = [t for t in teams if t.year == year]

    # get corresponding results: excluding championships if needed
    results = [r for t in teams for r in t.completed_results()]
    if not include_championships:
        results = [r for r in results if not r.race.is_championship()]

    # create leaderboard lists
    results.sort(key=lambda r: r.adj_time())
    leaderboards = OrderedDict()
    leaderboards, runner_ids = {'girls':[], 'boys':[]}, []
    for gender in ['girls', 'boys']:
        count = 0
        for res in results:
            team: Team = res.team
            runner: Runner = res.runner
            if team.gender==gender and runner.id not in runner_ids:
                runner_ids.append(runner.id)
                count += 1
                leaderboards[gender].append(res)
                if count == num_results:
                    break
    return leaderboards


# ---------------------------------- school ----------------------------------
@core.route('/<int:school_id>/school/<int:year>')
@core.route('/<int:school_id>/school')
@login_required
def school(school_id, year=CUR_YEAR):
    """
    School summary page displaying races and rosters for a given year.

    Return: render school.html
    """
    # get school object from database
    print('\n-------------------- starting school route --------------------')
    school: School = School.query.get(school_id)
    print(f'building route for {school.long_name}')

    # get this year's teams
    teams = [school.get_team(year, gender) for gender in ['girls', 'boys']] 
    teams = [t for t in teams if t]
    print(f'found teams: {teams}')

    # get the team records (results of all varsity dual meets for teams)
    team_records = [TeamRecordBuilder(team.id).build() for team in teams]

    # organize races by category
    team_races = [r for team in teams for r in team.completed_races()]
    championships = [r for r in team_races if r.is_championship()]
    varsity_dual_races = [
        Race.query.get(dual_result.race_id)
        for team_record in team_records 
        for dual_result in team_record.dual_results
    ]
    jv_or_invitational = [
        r for r in team_races if r not in varsity_dual_races + championships
    ]

    # get races for other years' teams
    other_races = [r for r in school.completed_races() if r not in team_races]

    # sort each list of races
    for races in [championships, jv_or_invitational, other_races]:
        races.sort(key=lambda r: (r.date_f(), -r.is_jv, r.gender), reverse=True)

    # find list of all possible years with teams for this school
    years: List[int] = list({team.year for team in school.teams})
    years.sort(reverse=True)

    return render_template(
        'school.html', 
        school=school,
        teams=teams,
        championships=championships,
        other_races=other_races,
        has_dual_meet_results=any(tr.dual_results for tr in team_records),
        team_records=team_records,
        other_team_races=jv_or_invitational,
        year=year,
        years=years
    )


# ---------------------------------- courses ----------------------------------
@core.route("/courses", methods=['GET'])
@login_required
def courses():
    print('\n-------------------- starting courses route --------------------')
    courses: List[Course] = Course.query.all()

    # exclude psuedo-courses
    courses = [
        c for c in courses 
        if 'hypothetical' not in c.name.lower() 
        and 'missing course' not in c.name.lower()
    ]

    # associate courses with schools
    course_tups: List[Tuple[Course, School, int]] = []
    for course in courses:
        if course.location.schools:
            tup = (course, course.location.schools[0], len(course.results()))
            course_tups.append(tup)
        else:
            course_tups.append((course, None, len(course.results())))

    # sort by league and school
    def league_short_name_and_school_short_name(tup: Tuple[Course, School]):
        course, school, results = tup
        if school is None:
            return ('zzz', 'zzz')
        else:
            return (school.league.short_name, school.short_name)
    course_tups.sort(key=league_short_name_and_school_short_name)

    return render_template(
        'courses.html', 
        course_list=course_tups,
    )


# ---------------------------------- course ----------------------------------
@core.route("/<int:course_id>/course", methods=['GET'])
@login_required
def course(course_id: int):
    """
    Route to display data for a given course

    Return: redirect to course.html when complete
    """
    print('\n--------------------- starting course route ---------------------')
    course: Course = Course.query.get(course_id)
    print(f'building route for {course}')

    # determine if cours associated with a particular school
    location: Location = course.location
    school = location.schools[0] if location.schools else None
    has_school = False if school is None else True

    # calculate course adjustment
    cadj = CourseAdjuster(course.id).run()
    print(f' course adjustment: {cadj.adj_f}')

    # create leaderboards
    all_races: List[Race] = course.races
    all_results: List[Result] = [r for race in all_races for r in race.results]
    all_results.sort(key=lambda r: r.time)
    leaderboards = OrderedDict()
    leaderboards, runner_ids = {'girls':[], 'boys':[]}, []
    for gender in ['girls', 'boys']:
        count = 0
        for res in all_results:
            team: Team = res.team
            runner: Runner = res.runner
            if team.gender==gender and runner.id not in runner_ids:
                runner_ids.append(runner.id)
                count += 1
                leaderboards[gender].append(res)
                if count == 20:
                    break

    return render_template(
        'course.html', 
        course=course,
        location=course.location,
        cadj=cadj,
        has_school=has_school,
        school=school,
        leaderboards=leaderboards,
    )


# ---------------------------------- runner ----------------------------------
@core.route("/<int:runner_id>/runner", methods=['GET'])
@login_required
def runner(runner_id):
    """
    Route to display data and results for a given runner

    Return: redirect to runner.html when complete
    """
    print('\n--------------------- starting runner route ---------------------')
    runner = Runner.query.get(runner_id)
    graph_html = RunnerGraphBuilder(runner).build()
    print(f' building route for {runner}')

    return render_template('runner.html', runner=runner, graph_html=graph_html)


# ------------------------------- leaderboards -------------------------------
@core.route("/leaderboards", methods=['GET'])
@core.route(
    "/<int:league_id>/<int:school_id>/<int:year>/<int:champ>/leaderboards", 
    methods=['GET']
)
@login_required
def leaderboards(league_id=0, school_id=0, year=0, champ=1):
    """
    """
    print('\n------------------ starting leaderboards route ------------------')
    print(f'league:{league_id}, school:{school_id}, year:{year}, champ:{champ}')

    league: League = League.query.get(league_id) if league_id != 0 else None
    school: School = School.query.get(school_id) if school_id != 0 else None
    include_championships = champ == 1

    # build league list
    all_leagues: List[League] = League.query.all()
    all_leagues.sort(key=lambda l: l.short_name)
    league_list = [(l.id, l.short_name) for l in all_leagues]
    league_list.insert(0, (0, 'All Leagues'))
    if league is not None:
        league_list.remove((league_id, league.short_name))
        league_list.insert(0, (league_id, league.short_name))

    # build school list
    all_schools: List[School] = School.query.all()
    all_schools.sort(key=lambda s: f'{s.league.short_name} {s.short_name}')
    school_list = [
        (s.id, f'{s.league.short_name}: {s.short_name}') for s in all_schools
    ]
    school_list.insert(0, (0, 'All Schools'))
    if school is not None:
        league_short_name = school.league.short_name
        school_tup = (school_id, f'{league_short_name}: {school.short_name}')
        school_list.remove(school_tup)
        school_list.insert(0, school_tup)

    # build year list
    all_years = [y for y in range(2019, CUR_YEAR+1)]
    year_list = [(y, y) for y in all_years if y != 2020]
    year_list.sort(reverse=True)
    year_list.insert(0, (0, 'All Years'))
    if year != 0:
        year_list.remove((year, year))
        year_list.insert(0, (year, year))

    # build championship list
    champ_list = [(1, 'Include Championships'), (0, 'Exclude Championships')]
    if champ == 0:
        champ_list.remove((0, 'Exclude Championships'))
        champ_list.insert(0, (0, 'Exclude Championships'))

    leaderboards = create_leaderboards(
        league=league,
        school=school,
        year=year,
        num_results=100,
        include_championships=include_championships,
    )

    return render_template(
        'leaderboards.html', 
        leaderboards=leaderboards,
        league_list=league_list,
        school_list=school_list,
        year_list=year_list,
        year=year,
        current_year=CUR_YEAR,
        champ_list=champ_list,
    )


# ---------------------------------- roster ----------------------------------
@core.route("/<int:team_id>/roster", methods=['GET', 'POST'])
@core.route("/<int:team_id>/roster/<int:race_id>/<int:step>", methods=['GET', 'POST'])
@login_required
def roster(team_id, race_id=0, step=1):
    """
    Page to make changes to a given team's roster.

    Return: render roster.html
    """
    team: Team = Team.query.get(team_id)
    school: School = team.school
    years = get_years_school_has_same_gender_team(team)
    genders = get_sorted_gender_list(team)
    other_runners = get_other_possible_runners_for_this_team(team)
    grad_years = get_years_for_grad_year_dropdown_option(team)
    form = RunnerForm(choices=grad_years)

    if form.validate_on_submit(): 
        runner = create_runner_from_form(form)
        report_runner_successfully_added_to_database(runner)
        add_runner_to_team(team, runner)
        matches = find_any_runners_matching_this_runner(runner, team.school.id)
        if matches:
            return redirect(url_for(
                'core.found_matching_runner',
                runner_id=runner.id,
                team_id=team.id,
                race_id=race_id,
                step=step,
            ))
        else:
            return redirect(url_for(
                'core.roster', 
                team_id=team.id, 
                race_id=race_id, 
                step=step
            ))

    return render_template(
        'roster.html',
        team=team,
        school=school,
        race_id=race_id,
        form=form,
        return_page=request.referrer,
        year=team.year,
        years=years,
        gender=team.gender.title(),
        genders=genders,
        able_to_delete=is_user_able_to_delete_runner(school),
        other_runners=other_runners,
        return_to=create_return_to_url(race_id, team, step),
    )

def get_years_school_has_same_gender_team(team: Team) -> List[int]:
    years = list({t.year for t in team.school.teams if t.gender == team.gender})
    years.sort(reverse=True)
    return years

def get_sorted_gender_list(team: Team) -> List[str]:
    return ['Girls','Boys'] if team.gender_f()=='Girls' else ['Boys','Girls']

def get_other_possible_runners_for_this_team(team: Team) -> List[Runner]:
    other_runners = list({
        r for t in team.school.teams for r in t.runners 
        if t.gender == team.gender 
        and r.grad_year > team.year
        and abs(r.grad_year - team.year) < 5
        and r not in team.runners
    })
    other_runners.sort(key=lambda r: (r.grad_year, r.last_first()))
    if other_runners is not None: 
        print(f'found other runners: {other_runners}')
    return other_runners

def get_years_for_grad_year_dropdown_option(team: Team) -> List[int]:
    min_grade_to_include = 6 # grad_year choices will be 6th grade and up
    return [team.year + i for i in range(1,(14-min_grade_to_include))]
    
def process_add_runner_form_and_refresh_page(
    form: RunnerForm, 
    team: Team,
    race_id: int,
    step: int
) -> None:
    runner = create_runner_from_form(form)
    report_runner_successfully_added_to_database(runner)
    add_runner_to_team(team, runner)
    matches = find_any_runners_matching_this_runner(runner, team.school.id)
    print(matches)
    if matches:
        return redirect(url_for(
            'core.found_matching_runner',
            runner_id=runner.id,
            team_id=team.id,
            race_id=race_id,
            step=step,
        ))
    else:
        message = f'Successfully added {runner.display_name()} to database'
        flash(message, 'success')
        return redirect(url_for(
            'core.roster', 
            team_id=team.id, 
            race_id=race_id, 
            step=step
        ))

def create_runner_from_form(form: RunnerForm) -> Runner:
    minutes = form.minutes.data
    seconds = form.seconds.data if form.seconds.data else 0
    seed_time = (minutes * 60 + seconds) * 1000
    runner = Runner(
        first_name = form.first_name.data,
        last_name = form.last_name.data,
        grad_year = form.grad_year.data,
        seed_time = int(seed_time)
    )
    db.session.add(runner)
    db.session.commit()

    return runner

def report_runner_successfully_added_to_database(runner: Runner):
    message = f'Successfully added {runner.name_plus_year()} to database'
    print(message)
    flash(message, 'success')

def add_runner_to_team(team: Team, runner: Runner):
    team.runners.append(runner)
    db.session.commit()

def find_any_runners_matching_this_runner(
    runner: Runner, 
    school_id: int
) -> List[Runner]:
    school: School = School.query.get(school_id)
    runners: List[Runner] = school.all_runners()
    matches = [r for r in runners if is_similar_runner(runner, r)]
    return matches

def is_similar_runner(runner: Runner, other: Runner) -> bool:
    is_not_self = runner.id != other.id
    has_high_score = get_similarity_score(runner, other) >= 80
    has_similar_grad_year = abs(runner.grad_year - other.grad_year) <= 4
    return is_not_self and has_high_score and has_similar_grad_year

def get_similarity_score(runner: Runner, other: Runner) -> int:
    r_name = normalize_string(runner.display_name())
    o_name = normalize_string(other.display_name())
    sim = fuzz.token_set_ratio(r_name, o_name)
    print(r_name, o_name, sim)
    return sim

def normalize_string(s: str) -> str:
    s = s.lower()
    s = re.sub(r'\W+', ' ', s)  # replace punctuation with single space
    s = re.sub(r'\s+', ' ', s)  # replace multiple spaces with single space
    s = s.strip()  # remove leading/trailing spaces
    return s

def is_user_able_to_delete_runner(school: School) -> bool:
    is_coach = True if school in current_user.schools_coached else False
    is_admin = current_user.is_administrator()
    return is_coach or is_admin

def create_return_to_url(race_id: int, team: Team, step: int) -> str:
    school: School = team.school
    if race_id == 0:
        ret_url = url_for('core.school', school_id=school.id, year=team.year)
    else:
        route_name = 'race_metadata' if step == 0 else 'race_detail'
        ret_url = url_for(f'race_setup.{route_name}', race_id=race_id)
    return ret_url


# --------------------------- found_matching_runner ---------------------------
@core.route(
    "/<int:runner_id>/<int:team_id>/<int:race_id>/<int:step>/found_matching_runner", 
    methods=['GET']
)
@login_required
def found_matching_runner(
    runner_id: int, 
    team_id: int, 
    race_id: int, 
    step: int
) -> None:
    runner: Runner = Runner.query.get(runner_id)
    team: Team = Team.query.get(team_id)
    school: School = team.school
    matches = find_any_runners_matching_this_runner(runner, school.id)
    print(matches)
    return render_template(
            'found_matching_runner.html',
            runner=runner,
            team=team,
            race_id=race_id,
            step=step,
            matches=matches,
    )


# ---------------------------- confirm_add_runner ----------------------------
@core.route(
    "/<int:team_id>/<int:race_id>/<int:step>/confirm_add_runner"
    "/<int:duplicate_runner_id>/<int:existing_runner_id>", 
    methods=['GET']
)
@login_required
def confirm_runner_is_duplicate(
    team_id: int,
    race_id: int, 
    step: int,
    duplicate_runner_id: int,
    existing_runner_id: int,
) -> None:
    team: Team = Team.query.get(team_id)
    if duplicate_runner_id != 0:
        duplicate_runner: Runner = Runner.query.get(duplicate_runner_id)
        duplicate_runner.delete_not_started_results()
        make_sure_existing_runner_is_on_the_team(existing_runner_id, team)
        remove_duplicate_runner_from_team(duplicate_runner, team)
        delete_duplicate_runner_from_db(duplicate_runner)

    return redirect(url_for(
        'core.roster', 
        team_id=team_id, 
        race_id=race_id,
        step=step
    ))

def make_sure_existing_runner_is_on_the_team(
    runner_id: int, 
    team: Team
) -> None:
    add_runner = Runner.query.get(runner_id)
    if add_runner not in team.runners:
        team.runners.append(add_runner)
        db.session.commit()

def remove_duplicate_runner_from_team(runner: Runner, team: Team) -> None:
    team.runners.remove(runner)
    db.session.commit()

def delete_duplicate_runner_from_db(runner: Runner) -> None:
    runner_str = runner.name_plus_year()
    if runner.completed_results():
        message = (
            f'{runner_str} was removed from this team, but has'
            f'results in the database and will not be deleted'
        )
        print(message)
        flash(message,'success')
    else:
        message = f'Deleted {runner_str} from the database.'
        print(message)
        flash(message,'success')

        db.session.delete(runner)
        db.session.commit()


# ------------------------------- update_runner -------------------------------
@core.route("/update_runner", methods=['POST'])
@login_required
def update_runner():
    """AJAX route to update runner information in database"""
    try:
        print(f'\n------------------ starting update_runner ------------------')
        data = request.get_json()
        print(
            f'received: {data}\n'
            f"updating runner {data['runner_id']} with {data['first_name']} "
            f"{data['last_name']} {data['grad_year']} and "
            f"{timify(data['seed_time'])}"
        )

        # get runner object from database
        runner: Runner = Runner.query.get(data['runner_id'])

        # update runner object
        runner.first_name = data['first_name']
        runner.last_name = data['last_name']
        runner.grad_year = data['grad_year']
        runner.seed_time = data['seed_time']

        # commit changes to database
        db.session.commit()

        # Pass JSON_received to the frontend
        return jsonify({'status':'success'})

    except Exception as e:
        print("AJAX excepted " + str(e))
        return str(e)


# -------------------------- delete_or_remove_runner --------------------------
@core.route("/delete_or_remove_runner", methods=['POST'])
@login_required
def delete_or_remove():
    """
    AJAX route to delete runner from database or remove from team

    Return: none
    """
    try:
        print(f'\n---------------- starting delete_or_remove ----------------')
        data = request.get_json()
        print(f'received: {data}')
        team: Team = Team.query.get(data['team_id'])
        runner: Runner = Runner.query.get(data['runner_id'])

        # abort if user is not authorized
        if not is_user_able_to_delete_runner(team.school):
            txt = 'User is not authorized to delete a runner for this team'
            flash(txt, 'danger')
            return jsonify({'status':'success'})

        print(f'removing {runner} from {team} and deleting if no results')

        # remove any incomplete results (i.e, staged races)
        for result in runner.incomplete_results():
            db.session.delete(result)
            db.session.commit()

        # remove runner from team
        runner.teams.remove(team)
        db.session.commit()
        flash(f'Removed {runner.name()} from {team.team_name()}', 'success')

        # if runner has no completed results, delete from database
        if len(runner.completed_results()) == 0:
            print(f'{runner} has no completed results, deleting from database')
            db.session.delete(runner)
            db.session.commit()
            flash(f'Deleted {runner.name()} from database', 'success')

        # Pass JSON_received to the frontend
        return jsonify({'status':'success'})

    except Exception as e:
        print("AJAX excepted " + str(e))
        return str(e)


@core.route("/change_team", methods=['POST'])
@login_required
def change_team():
    """
    AJAX route when user chooses a new team from roster page

    Return: none
    """
    try:
        # get client data from request
        data = request.get_json()
        print(f"recived: {data}")

        # attempt to get team from database
        team: Team = Team.query.filter_by(
            school_id=data['school_id'], 
            gender=data['gender'].lower(), 
            year=data['year'],
        ).first()

        # if team exists, send data to route to new roster page
        if team is not None:
            print(f'found team: {team}, routing to roster page')
            return jsonify({
                'status':'Found Team', 
                'previous_team_id':data['team_id'],
                'team_id':team.id
            })

        # since no team exists, confirm user wants to create it
        school = School.query.get(data['school_id'])
        msg = (
            f"{school.long_name} does not yet have a {data['gender'].lower()} "
            f"team for {data['year']}.  Would you like to create one?"
        )

        # Pass JSON_received to the frontend
        return jsonify({'status':'No Team', 'message':msg})

    except Exception as e:
        print("AJAX excepted " + str(e))
        return str(e)


@core.route("/create_team", methods=['POST'])
@login_required
def create_team():
    """AJAX Route to create a new team"""
    print(f'\n--------------------- starting create_team ---------------------')
    data = request.get_json()
    print(f'received: {data}')
    school_id, gender, year = data['school_id'],  data['gender'], data['year']
    print(f'school_id: {school_id}, gender: {gender}, year: {year}')

    # get school from database
    school = School.query.get(school_id)

    # abort if user is not admin
    is_coach = True if school in current_user.schools_coached else False
    is_admin = current_user.is_administrator()
    if not (is_admin or is_coach):
        flash('Only the coach or an admin can create a team', 'danger')
        return redirect(url_for('core.school', school_id=school.id, year=year))

    # abort if team already exists
    existing_team = Team.query.filter_by(
        school_id=school_id, gender=gender.lower(), year=year
    ).first()
    if existing_team is not None:
        print(f'team already exists: {existing_team}')
        flash(f'{year} {gender.title()} team already exists', 'warning')
        return redirect(url_for('core.roster', team_id=existing_team.id))

    # create the new team
    team = Team(gender=gender.lower(), year=year, school_id=school_id)

    # add team to database and commit
    db.session.add(team)
    db.session.commit()
    print(f'created team: {team}')
    flash_txt = (
        f'Successfully created team for {team.school.short_name} '
        f'{year} {gender.title()}'
    )
    flash(flash_txt, 'success')
    return jsonify({'status':'Success', 'team_id':team.id})


@core.route("/<int:team_id>/delete_team", methods=['GET'])
@login_required
def delete_team(team_id:int):
    """
    Route to delete a team if possible

    Return: none
    """
    print(f'\n--------------------- starting delete_team ---------------------')
    print(f'team_id: {team_id}')

    # get team from database and delete
    team: Team = Team.query.get(team_id)
    school: School = team.school
    year: int = team.year

    # abort if user is not admin
    is_coach = True if school in current_user.schools_coached else False
    is_admin = current_user.is_administrator()
    if not (is_admin or is_coach):
        flash('Only the coach or an admin can delete a team', 'danger')
        return redirect(url_for('core.school', school_id=school.id, year=year))

    # abort if team has results
    if team.has_completed_results():
        flash('Team has results, cannot delete', 'danger')
        return redirect(url_for('core.school', school_id=school.id, year=year))

    # remove all results from team
    team.results.clear()

    # get all runners on team
    runners: List[Runner] = team.runners.copy()

    # remove all runners from team
    team.runners.clear()

    # delete all runners from database
    for runner in runners:
        if runner.completed_results():
            message = (
                f'{runner.name_plus_year()} was removed from this team, but '
                f'has results in the database and will not be deleted'
            )
            print(message)
        else:
            db.session.delete(runner)

    # remove all races from team
    team.races.clear()

    # remove team from school
    school = School.query.get(team.school_id)
    school.teams.remove(team)

    db.session.delete(team)
    db.session.commit()

    return redirect(url_for('core.school', school_id=school.id, year=year))


@core.route("/<int:school_id>/delete_school", methods=['GET'])
@login_required
def delete_school(school_id: int):
    """
    Route to delete a school if possible

    Return: none
    """
    print(f'\n--------------------- starting delete_school ---------------------')
    print(f'school_id: {school_id}')

    # get team from database and delete
    school: School = School.query.get(school_id)

    # abort if user is not admin
    if current_user.id != 1:
        flash('Only the admin can delete a school', 'danger')
        return redirect(url_for('core.school', school_id=school.id, year=CUR_YEAR))

    # abort if team has teams with results
    has_results = any([t.has_completed_results() for t in school.teams])
    if has_results:
        flash('School has results, cannot delete', 'danger')
        return redirect(url_for('core.school', school_id=school.id, year=CUR_YEAR))

    # remove all locations from school
    school.locations.clear()

    # remove school from any races
    school.all_races.clear()

    # remove school from any coaches
    school.coaches.clear()

    db.session.delete(school)
    db.session.commit()

    return redirect(url_for('core.index'))


@core.route("/choose_school", methods=['GET'])
@login_required
def choose_school():
    """
    Select a school to which to add/edit/remove a runner

    Return: renders add_school.html
    """
    if current_user.is_administrator():
        schools = School.query.all()
    else:
        schools = current_user.schools_coached

    school_teams = {
        school: sorted([t for t in school.teams], key=lambda x: x.year)[-1]
        for school in schools
    }
    school_teams = sorted(school_teams.items(), key=lambda x: x[0].long_name)

    return render_template('choose_school.html', school_teams=school_teams)


@core.route("/increment_year_and_create_new_teams", methods=['GET'])
@login_required
def increment_year_and_create_new_teams():
    print('\n--------- starting increment_year_and_create_new_teams ---------')
    previous_year = CUR_YEAR - 1

    all_schools = School.query.all()
    for school in all_schools:
        print(f' starting {school}')

        # get teams from previous year
        prev_year_teams = [t for t in school.teams if t.year == previous_year]

        # abort if no teams for previous year
        if not prev_year_teams:
            print(f'  no teams for {school} in {previous_year}, skipping')
            continue

        # for each prev_year_team create a corresponding team for this year
        for prev_year_team in prev_year_teams:
            print(f'  rolling over {prev_year_team} to new year')

            # abort if team already exists for this year
            corresponding_team = Team.query.filter_by(
                school_id=school.id,
                gender=prev_year_team.gender,
                year=CUR_YEAR
            ).first()
            if corresponding_team is not None:
                print(f'   team already exists: {corresponding_team}')
                continue
            
            # create new team for this year
            cur_year_team = Team(
                gender=prev_year_team.gender,
                year=CUR_YEAR,
                school_id=school.id
            )
            db.session.add(cur_year_team)
            db.session.commit()

            # add eligible runners from previous year team to current year team
            returning_runners = [
                r for r in prev_year_team.runners if r.grad_year > CUR_YEAR
            ]
            for runner in returning_runners:
                print(f'   adding {runner} to {cur_year_team}')
                cur_year_team.runners.append(runner)
                db.session.commit()

    return redirect(url_for('core.index'))


@core.route('/transfer_runner_to_new_school/<int:runner_id>/<int:school_id>', methods=['GET'])
@login_required
def transfer_runner_to_new_school(runner_id, school_id):
    print('\n------------ starting transfer_runner_to_new_school ------------')
    runner = Runner.query.get(runner_id)
    school = School.query.get(school_id)
    print(f' transferring {runner} to {school}')

    # find previous_year_team of runner
    prev_year_team = [t for t in runner.teams if t.year == CUR_YEAR - 1]
    if len(prev_year_team) != 1:
        print(f'ERROR: {runner} has {len(prev_year_team)} teams in {CUR_YEAR-1}')
        redirect(url_for('core.school', school_id=school_id))
    prev_year_team = prev_year_team[0]
    print(f' previous year team: {prev_year_team}')

    # remove runner from cur_year_team at old school if he is on it
    cur_year_team = [t for t in runner.teams if t.year == CUR_YEAR]
    if len(cur_year_team) == 1:
        cur_year_team = cur_year_team[0]
        cur_year_team.runners.remove(runner)
        db.session.commit()
        print(f'Removed {runner} from {cur_year_team}')

    # identify team to transfer runner to
    target_team = [
        t for t in school.teams 
        if t.year == CUR_YEAR and t.gender == prev_year_team.gender
    ]
    if len(target_team) != 1:
        print(
            f'ERROR: {school} has does not have {prev_year_team.gender} '
            f'for {CUR_YEAR}')
        redirect(url_for('core.school', school_id=school_id))
    target_team: Team = target_team[0]

    # add runner to target_team
    target_team.runners.append(runner)
    db.session.commit()
    print(f' added {runner} to {target_team}')

    return redirect(url_for('core.school', school_id=school_id))

@celery.task(bind=True)
def async_update_seed_times(self, runner_ids: List[int]):
    t0 = time.time()
    runners:List[Runner] = [Runner.query.get(r_id) for r_id in runner_ids]
    runner_count = len(runners)
    for runner in runners:
        if runner.completed_results():
            runner.update_seed_time()
        else:
            runner.seed_time = 1500000 # default to 25 minutes if no results
            db.session.commit()
    t1 = time.time()
    print(f'\n Update {runner_count} seed times in {round(t1-t0,2)} seconds\n')
    return {'current': runner_count, 'total': runner_count, 'result': 1}

@core.route("/update_all_seed_times")
@core.route("/update_all_seed_times/<int:year>")
@login_required
def update_all_seed_times(year=0):
    """
    Temporary route to update every runner's seed time.

    Return: nothing.  Redirects to home.html when complete
    """
    if year == 0:
        runners = Runner.query.all()
    else:
        all_teams: List[Team] = Team.query.all()
        year_teams = [t for t in all_teams if t.year == year]
        runners = [r for t in year_teams for r in t.runners]

    runner_ids = [runner.id for runner in runners]
    runner_count = len(runner_ids)
    task = async_update_all_seed_times.delay(runner_ids)
    location = url_for('core.taskstatus', task_id=task.id)
    print(location)
    return render_template(
        'updating_seed_times.html', 
        location=location,
        runner_count=f'{runner_count:,.0f}'
    )

@celery.task(bind=True)
def async_update_all_seed_times(self, runner_ids: List[int]):
    t0 = time.time()
    runners = [Runner.query.get(id) for id in runner_ids]
    runner_count = len(runners)
    for indx, runner in enumerate(runners):
        if runner.completed_results():
            runner.update_seed_time()
        else:
            runner.seed_time = 1500000
            db.session.commit()
        self.update_state(
            state='PROGRESS',
            meta={'current': indx, 'total': runner_count}
        )
    t1 = time.time()
    print(f'\nSeed times for {runner_count} updated in {t1-t0} seconds\n')
    return {'current': runner_count, 'total': runner_count, 'result': 1}

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






@celery.task(bind=True)
def async_update_league_standings(self, league_id:int, year:int=CUR_YEAR):
    t0 = time.time()
    LeagueStandingsBuilder(league_id).update_all_team_records(year)
    t1 = time.time()
    print(f'\n updated league standings in {round(t1-t0,2)} seconds\n')
    return {'current': 1, 'total': 1, 'result': 1}

@celery.task(bind=True)
def async_adjust_course(self, course_id:int):
    t0 = time.time()
    CourseAdjuster(course_id).run()
    t1 = time.time()
    print(f'\n adjusted course in {round(t1-t0,2)} seconds\n')
    return {'current': 1, 'total': 1, 'result': 1}


















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

@core.route('/<int:league_id>/calc_league_standings')
@login_required
def calc_league_standings(league_id):
    task = async_update_league_standings.delay(league_id=league_id)
    return redirect(url_for('core.index'))

@celery.task(bind=True)
def async_get_season_summary(self, team_ids):
    t0 = time.time()
    print(f'\n-------------- Starting Season Summary Route --------------')
    self.update_state(
        state='PROGRESS',
        meta={'current': 1,'total': 1}
    )
    teams = []
    for team_id in team_ids:
        teams.append(Team.query.get(team_id))
    ss = {team.gender: team.season_summary() for team in teams}
    t1 = time.time()
    print(f'\n completed route in {int(t1-t0)} seconds\n')
    return {'current': 1, 'total': 1, 'result': ss}

@core.route('/temp_fix')
def temp_fix():
    YearEndEffectCalculator().run()
    # school = School.query.get(70)
    # location = Location.query.get(32)
    # school.locations.append(location)
    # db.session.commit()

    # all_teams = Team.query.all()
    # teams_2022 = [t for t in all_teams if t.year == 2022]
    # misplaced_runners = [r for t in teams_2022 for r in t.runners if r.grad_year == 2022]
    # for runner in misplaced_runners:
    #     print(f'Found {runner} on {runner.current_year_team()}')

    # runner = Runner.query.get(5546)
    # runner.teams.clear()
    # db.session.commit()
    # db.session.delete(runner)
    # db.session.commit()

    # t136 = Team.query.get(136)
    # runner = Runner.query.get(1507)
    # t136.runners.append(runner)

    # # change standard school img filename to be short_name + id
    # core = os.path.dirname(os.path.realpath(__file__))
    # root_path = os.path.dirname(core)
    # root_path = os.path.join(root_path, 'static', 'img')
    # print(root_path)
    # all_schools: List[School] = School.query.all()
    # for school in all_schools:
    #     if school.has_image():
    #         old_fname = os.path.join(root_path, school.img_filename()[4:])
    #         new_fname = os.path.join(root_path, school.new_img_filename()[4:])
    #         os.rename(old_fname, new_fname)
    #         print(f'{old_fname} -> {new_fname}')
    # fnames = os.listdir('hsxc/static/img')
    # print(fnames)

    # db.session.commit()

    return redirect(url_for('core.index'))

@core.route('/normalize_courses')
def normalize_courses():
    t1 = time.time()
    print('\n------------------- starting normalize_courses -------------------')

    update_all_course_adjustments()

    t2 = time.time()
    print(f'\n completed route in {int(t2-t1)} seconds\n')

    return redirect(url_for('core.courses'))

@core.route('/database_anomolies')
def database_anomolies():
    print('\n------------------ starting database_anomolies ------------------')
    team = Team.query.get(501)
    print(team)
    print(team.runners)
    for race in team.races:
        print(race.id, race)

    return redirect(url_for('core.index'))

@core.route('/purge_duplicate_team/<int:team_id>')
def purge_duplicate_team(team_id):
    # remove runners from team
    team = Team.query.get(team_id)
    for runner in team.runners:
        team.runners.remove(runner)
        db.session.commit()

    # remove results from team
    for result in team.results:
        team.results.remove(result)
        db.session.commit()

    # remove team from races
    for race in team.races:
        race.teams.remove(team)
        db.session.commit()

    # delete team
    db.session.delete(team)
    db.session.commit()

    return redirect(url_for('core.database_anomolies'))