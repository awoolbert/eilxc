# external imports
from flask import render_template, url_for, flash, redirect
from flask import jsonify, request, Blueprint
from flask_login import login_required, current_user
from flask_mail import Message
from datetime import datetime
from premailer import transform
from typing import List
import time

# hsxc imports
from hsxc import celery, db, mail
from hsxc.models import Team, Race, Result, RaceScore, School, League
from hsxc.helpers import CUR_YEAR
from hsxc.controllers.core.views import async_update_seed_times
from hsxc.controllers.core.views import async_update_league_standings
from hsxc.controllers.race_setup.views import delete_race_by_id
from hsxc.models.race import ResSum
from hsxc.builders.course_normalizer import CourseAdjuster, CourseAdjustment
from hsxc.builders.team_record import TeamRecordBuilder
from hsxc.builders.hypothetical_race_builder import HypotheticalRaceBuilder
from .forms import HypotheticalRaceForm

races = Blueprint('races', __name__)


@races.route("/races", methods=['GET'])
@login_required
def all_races():
    """
    Route to display list of all races

    Return: renders races.html
    """
    races = Race.query.filter_by(status="complete").all()
    races = sorted(races, key=lambda r: (-r.is_jv, r.gender), reverse=True)
    races = sorted(races, key=lambda r: r.name)
    races = sorted(races, key=lambda r: r.date.date(), reverse=True)

    return render_template('races.html', races=races)


@races.route("/<int:race_id>/results")
@login_required
def results(race_id):
    """
    Route to view the results of a race.  Calls the calculate_results function
    and organizes the results to be rendered

    Return: renders results.html, a page organizing and displaying the
            individual results and team results for the race
    """
    print('\n----------------- beginning results --------------------')

    # Calculate the results and store in results object
    race: Race = Race.query.get(race_id)
    print(f"raceName: {race.name_f()}")
    results_summary: ResSum = race.results_summary()

    # determine if user is authorized to change scoring_type
    is_authorized = race.user==current_user or current_user.is_administrator()

    # build list of coaches emails
    email_list = [
        coach.email
        for school in race.schools
        for coach in school.coaches
        if coach != current_user
    ]
    email_list.insert(0, current_user.email)

    # asynchroneously update runner seed times
    runner_ids = [r.runner.id for r in race.results]
    async_update_seed_times.delay(runner_ids=runner_ids)

    # asynchroneously update team records for league standings
    league_ids = {t.school.league.id for t in race.teams}
    for league_id in league_ids:
        async_update_league_standings.delay(
            league_id=league_id, year=race.date.year
        )

    # Render the page
    return render_template(
        'results.html',
        ind_results=results_summary.individual_results,
        race_results=results_summary.race_results,
        race=race,
        win_loss_table=results_summary.win_loss_table,
        user=current_user,
        email_list=email_list,
        is_authorized=is_authorized
    )


@races.route("/email_race_results", methods=['POST'])
@login_required
def email_race_results():
    """
    AJAX route called from results.html to email the results of a race,
    formatted for consumption by email programs.  Receives recipient list
    and race_id from client, calls calculate_results and formats for email

    Return: none. Stores rendering of results_email.html than runs it through
            a premailer before emailing via flask_mail
    """
    try:
        t0 = time.time()
        # Get information that was passed from the client
        client_data = request.get_json()
        recipient_list = client_data['recipients']

        # Alert that route has begun
        print('\n------- email_race_results route beginning -------')

        # Pull race from database
        race = Race.query.get(client_data['race_id'])
        print(f"Attempting to email results of {race.display_name()} "
              f"to {recipient_list}")

        # Calculate the results and store in results object
        results_summary: ResSum = race.results_summary()

        # Prepare message
        subject = f"Race Results: {race.name_f()}"

        msg = Message(
            subject = subject,
            sender = ('New England Prep XC','neprepxc@gmail.com'),
            recipients = recipient_list
        )

        raw_html = render_template(
            'results_email.html',
            ind_results = results_summary.individual_results,
            race_results = results_summary.race_results,
            race = race,
            win_loss_table = results_summary.win_loss_table,
        )

        # Apply premailer transformations to fix formatting and send message
        msg.html = transform(raw_html)

        # send message
        mail.send(msg)
        t1 = time.time()
        print(f"Message sent in {t1-t0} seconds")

        # Pass JSON_received to the frontend
        JSON_received = {'Status':'Received race'}
        return jsonify(JSON_received)

    except Exception as e:
        print("AJAX excepted " + str(e))
        return str(e)


@races.route("/update_scoring_type", methods=['POST'])
@login_required
def update_scoring_type():
    """
    AJAX route called from results.html to change the scoring_type of a race.
    This route is followed on the client side by a refresh of results.html
    which forces a recalculation and re-rendering of the page to allow the
    scoring_type change to take effect

    Return: none. Updates database for the race with the new scoring_type
    """
    try:
        client_data = request.get_json()

        print('\n------- update_scoring_type route beginning -------')

        # race is from databse, while client_data is from front end
        race = Race.query.get(client_data['race_id'])
        print(f"starting DB: race_id:{race.id}, "
              f"name:{race.name}, "
              f"gender:{race.gender}, "
              f"scoring_type:{race.scoring_type}")

        # Set the scoring_type based on the client_data
        race.scoring_type = client_data['scoring_type']

        # Updated the database with client_data
        db.session.commit()
        print(f"ending DB: race_id:{race.id}, "
              f"name:{race.name}, "
              f"gender:{race.gender}, "
              f"scoring_type:{race.scoring_type}")

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

        # Pass JSON_received to the frontend
        JSON_received = {'Status':'Received race'}
        return jsonify(JSON_received)

    except Exception as e:
        print("AJAX excepted " + str(e))
        return str(e)


@races.route("/<int:race_id>/active")
@login_required
def active(race_id):
    """
    Route for the actual running and timing of a race

    Return: render active.html
    """
    # create dictionary with race information
    race = Race.query.get(race_id)

    # if race is already completed, go to results
    if race.status == 'complete':
        return redirect(url_for('races.results', race_id=race.id))

    # get the participants for this race
    results = (Result.query.filter_by(race_id=race_id)
                           .order_by(Result.place).all())

    # determine if race is using bibs
    using_bibs = not all([res.bib is None for res in results])
    print(f"using_bibs: {using_bibs}")

    # render the template
    return render_template('active.html',
                            race=race,
                            runners=results,
                            using_bibs=using_bibs)


@races.route("/update_race_state", methods=['POST'])
@login_required
def update_race_state():
    """
    AJAX route called from active.html to update database with the current
    state of the race including: start_time, finish times (if any), current
    user-sorted order of the runners, etc.  This is called any time a change
    is made to results (e.g., the race is started, a finish is recorded, the
    order of runners is changed, etc.).  This real-time updating of the
    database ensures that a client-side refresh or disconnect will not lose
    any information.

    Return: none. Updates database including the race object and corresponding
            results objects.
    """
    try:
        client_data = request.get_json()
        print(f"\nStarting AJAX route: update_race_state for \
                race:{client_data['race_id']}")

        # Get the current race object from database
        race = Race.query.get(client_data['race_id'])

        # Set the status based on the client data
        race.status = client_data['race_status']

        # Set the date of the race to the official start time from client
        date = datetime.fromtimestamp(client_data['start_time']/1000.0)
        print(f"Setting date/start_time to {date}")
        race.date = date

        # Loop through participants from client and update results
        for p in client_data['participants']:
            res = Result.query.get(p['result_id'])
            res.place = p['place']
            res.time = p['time'] if 'time' in p else None

        # commit changes to database
        db.session.commit()

        # If the race is complete, change status, updated seed_times and
        # delete runners without times from results
        runners = []
        if race.status == 'complete':
            for res in race.results:
                if res.time:
                    res.status = 'c'
                    db.session.commit()
                    runners.append(res.runner)
                else:
                    db.session.delete(res)

            # update seed times of runners in this race on background worker
            runner_ids = [runner.id for runner in runners]
            async_update_seed_times.delay(runner_ids=runner_ids)

            # update league standings on background worker
            if race.scoring_type != 'invitational':
                leagues = {
                    team.school.league
                    for team in race.teams
                    if team.school.league != 3
                }
                for league in leagues:
                    async_update_league_standings.delay(
                        league_id=league.id, year=CUR_YEAR
                    )

        # commit changes to database
        db.session.commit()

        # Pass JSON_received to the frontend
        JSON_received = {'Status':'Received raceState'}
        return jsonify(JSON_received)

    except Exception as e:
        print("AJAX excepted " + str(e))
        return str(e)


@races.route("/<int:race_id>/reset_race_to_ready")
@login_required
def reset_race_to_ready(race_id):
    """
    Temporary route to move race back to ready position

    Return: render active.html
    """
    # Get the race from the database
    race = Race.query.get(race_id)

    race.status = 'ready'
    for res in race.results:
        res.time = None
        res.place = res.runner.seed_time

    db.session.commit()

    return redirect(url_for('races.active', race_id=race_id))

@races.route("/force_update_race_scores_table")
@login_required
def update_race_scores_table():
    print('---------------- starting update_race_scores_table ----------------')
    all_teams = Team.query.all()

    # get ids for all races currently in the race_score table
    race_ids_processed = list(set([r.race_id for r in RaceScore.query.all()]))

    # remove any rows corresponding to 'invitational' races
    races_processed = [Race.query.get(id) for id in race_ids_processed]
    invitational_ids = [
        race.id for race in races_processed if race.scoring_type=='invitational' 
    ]
    for id in invitational_ids:
        rows_deleted = RaceScore.query.filter_by(race_id = id).all()
        for row in rows_deleted:
            db.session.delete(row)
            db.session.commit()
            print(f"Deleted {row} from race_score table with race_id {id}")

    # call results_summary() on each race (wich scores race, adding to table)
    for team in all_teams:
        for race in team.races:
            if (race.scoring_type=='invitational'
                or race.is_jv):
                continue
            res_sum = race.results_summary()

    return redirect(url_for('core.index'))   


@races.route("/hypothetical_race", methods=['GET', 'POST'])
@login_required
def hypothetical_race():
    form = HypotheticalRaceForm()
    all_leagues: List[League] = League.query.all()

    choice_list = [
        (school.id, f'{league.short_name:<6}: {school.long_name}') 
        for league in all_leagues for school in league.schools
    ]
    choice_list.sort(key=lambda x: x[1])
    form.schools.choices = choice_list

    if not form.validate_on_submit():
        return render_template('hypothetical_race.html', form=form)

    gender = form.gender.data
    scoring_type = form.scoring_type.data
    times_to_use = form.times_to_use.data
    schools: List[School] = [
        School.query.get(school_id) for school_id in form.schools.data
    ]

    race = HypotheticalRaceBuilder(
        gender, times_to_use, scoring_type, schools
    ).build()
    race_id = race.id
    delete_race_from_database_after_pause.delay(
        race_id=race.id, user_id=current_user.id
    )
    return redirect(url_for('races.results', race_id=race_id))   

@celery.task(bind=True)
def delete_race_from_database_after_pause(self, 
    race_id:int, 
    user_id:int
) -> None:
    import time
    time.sleep(30)
    delete_race_by_id(race_id=race_id, user_id=user_id)
    return None

