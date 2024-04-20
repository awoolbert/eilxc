# system imports
from datetime import datetime
from flask_login import current_user
from typing import Optional

# local imports
from hsxc import db
from hsxc.models import School, Runner, Team, Result, Location, Race, Course


class RaceDataImporter:

    def __init__(self, data:dict) -> None:
        self.data = data
        self.map = {
            'schools'    : {}, # id_in_other_db : object_in_this_db
            'teams'      : {}, # id_in_other_db : object_in_this_db
            'location'   : {}, # id_in_other_db : object_in_this_db
            'course'     : {}, # id_in_other_db : object_in_this_db
            'runners'    : {}, # id_in_other_db : object_in_this_db
            'race'       : {}, # id_in_other_db : object_in_this_db
            'results'    : {}, # id_in_other_db : object_in_this_db
            'host_school': None,
        }

    def build_race_from_file(self) -> Race:
        self._get_or_create_schools()
        self._get_or_create_location()
        self._associate_location_with_school()
        self._get_or_create_course()
        self._associate_course_with_location()
        self._get_or_create_teams()
        self._get_or_create_runners()
        self._create_race()
        self._associate_race_with_schools_and_teams()
        self._create_results()
        return self.map['race'][self.data['race']['id']]

    def _get_or_create_schools(self) -> None:
        print(' mapping or creating schools:')
        for school_dict in self.data['schools']:

            # attempt to find school in db
            school = School.query.filter_by(
                long_name=school_dict['long_name'], 
                short_name=school_dict['short_name'],
                state_abbr=school_dict['state_abbr']
            ).first()
            print(f'  found {school} in database')

            # if school not found, create it
            if school is None:
                school = School(
                    long_name=school_dict['long_name'],
                    short_name=school_dict['short_name'],
                    city=school_dict['city'],
                    state_abbr=school_dict['state_abbr'],
                    league_id = school_dict['league_id'],
                    primary_color = school_dict['primary_color'],
                    secondary_color = school_dict['secondary_color'],
                    text_color = school_dict['text_color'],
                )
                db.session.add(school)
                db.session.commit()
                print(f'  created {school} in database')

            # update map
            self.map['schools'][school_dict['id']] = school

    def _get_or_create_location(self) -> None:
        print(' mapping or creating location:')
        loc_dict = self.data['location']

        # attempt to find location in db
        location = Location.query.filter_by(
            name=loc_dict['name'],
            street_address = loc_dict['street_address'],
            city = loc_dict['city'],
            state_abbr = loc_dict['state_abbr'],
            zip = loc_dict['zip'],
        ).first()
        print(f'  found {location} in database')

        # if location not found, create it
        if location is None:
            location = Location(
                name = loc_dict['name'],
                street_address = loc_dict['street_address'],
                city = loc_dict['city'],
                state_abbr = loc_dict['state_abbr'],
                zip = loc_dict['zip'],
            )
            db.session.add(location)
            db.session.commit()
            print(f'  created {location} in database')

        # update map
        self.map['location'][loc_dict['id']] = location

    def _associate_location_with_school(self) -> None:
        print(' associating location with school:')
        location = self.map['location'][self.data['location']['id']]

        # check if location is already associated with host_school
        host_school = [
            school for school in self.map['schools'].values()
            if location in school.locations
        ]
        if host_school:
            host_school = host_school[0]
            print(f'  {location} already associated with {host_school}')
            return None

        # otherwise attempt to determine host_school and associate location
        # first check if host_school was identified in race data
        host_school_id = self.data['race']['host_school_id']
        if host_school_id is not None:
            host_school = self.map['school'][host_school_id]
            self.map['host_school'] = host_school
            host_school.locations.append(location)
            db.session.commit()
            print(f'  added {location} to {host_school}')
            return None

        # next, attempt to determine host_school from race name
        host_school = None
        race_name = self.data['race']['name']
        if ' at ' in race_name:
            school_str = race_name.split(' at ')[1]
            for school in self.map['school'].values():
                if school.short_name.lower() in school_str.lower():
                    host_school = school
                    break
            if host_school is not None:
                self.map['host_school'] = host_school
                host_school.locations.append(location)
                db.session.commit()
                print(f'  added {location} to {host_school}')
                return None

        # lastly, attempt to determine host_school from location name
        for school in self.map['school'].values():
            has_short_name = (
                school.short_name.lower() in location.name.lower()
            )
            has_long_name = (
                school.long_name.lower() in location.name.lower()
            )
            if has_short_name or has_long_name:
                host_school = school
                break
        if host_school is not None:
            host_school.locations.append(location)
            self.map['host_school'] = host_school
            db.session.commit()
            print(f'  added {location} to {host_school}')
        else:
            print(f'  could not determine host_school for {location}')

    def _get_or_create_course(self) -> None:
        print(' mapping or creating course:')
        course_dict = self.data['course']

        # attempt to find location in db
        course = Course.query.filter_by(
            name = course_dict['name'],
            description = course_dict['description'],
            distance = course_dict['distance'],            
        ).first()
        print(f'  found {course} in database')

        # if location not found, create it
        if course is None:
            course = Location(
                name = course_dict['name'],
                description = course_dict['description'],
                distance = course_dict['distance'],            
            )
            db.session.add(course)
            db.session.commit()
            print(f'  created {course} in database')

        # update map
        self.map['course'][course_dict['id']] = course

    def _associate_course_with_location(self) -> None:
        print(' associating course with location:')
        course = self.map['course'][self.data['course']['id']]
        location = self.map['location'][self.data['location']['id']]

        # check if course is already associated with location
        if course in location.courses:
            print(f'  {course} already associated with {location}')
            return None

        # otherwise associate course with location
        location.courses.append(course)
        db.session.commit()
        print(f'  added {course} to {location}')

    def _get_or_create_teams(self) -> None:
        print(' mapping or creating teams:')
        for team_dict in self.data['teams']:
            # attempt to find team in db
            school = self.map['schools'][team_dict['school_id']]
            team = Team.query.filter_by(
                gender = team_dict['gender'],
                year = team_dict['year'],
                school_id = school.id,
            ).first()
            print(f'  found {team} in database')

            # if team not found, create it
            if team is None:
                team = Team(
                    gender=team_dict['gender'],
                    year=team_dict['year'],
                    school_id=school.id,
                    wins=0,
                    losses=0,
                    league_wins=0,
                    league_losses=0,
                )
                db.session.add(team)
                db.session.commit()
                print(f'  created {team} in database')

            # update map
            self.map['teams'][team_dict['id']] = team

    def _get_or_create_runners(self) -> None:

        def get_runner_id(runner_dict: dict) -> int:
            return runner_dict['id']
        
        def get_team(runner_id: int) -> Team:
            res_dict = next((
                res_dict for res_dict in self.data['results']
                if res_dict['runner_id'] == runner_id
            ))
            team_id = res_dict['team_id']
            return self.map['teams'][team_id]

        def get_runner(runner_dict: dict, team: Team) -> Optional[Runner]:
            # attempt to find runner in db on this team
            runner = next((
                runner for runner in team.runners
                if runner.first_name == runner_dict['first_name']
                and runner.last_name == runner_dict['last_name']
                and runner.grad_year == runner_dict['grad_year']
            ), None)
            if runner is not None:
                print(f'  found {runner} in database')

            # if not found, attempt to find runner in db on previous year's team
            else:
                alt_team = Team.query.filter_by(
                    school_id = team.school.id,
                    gender = team.gender,
                    year = team.year - 1,
                )
                runner = next((
                    runner for runner in alt_team.runners
                    if runner.first_name == runner_dict['first_name']
                    and runner.last_name == runner_dict['last_name']
                    and runner.grad_year == runner_dict['grad_year']
                ), None)
                if runner is not None:
                    print(f'  found {runner} in database', end='')

                    # associate runner with team
                    runner.teams.append(team)
                    db.session.commit()
                    print(f'  and added to {team}')
                    return runner

            return runner

        def create_runner(runner_dict: dict, team: Team) -> Runner:
            runner = Runner(
                first_name = runner_dict['first_name'],
                last_name = runner_dict['last_name'],
                grad_year = runner_dict['grad_year'],
            )
            db.session.add(runner)
            db.session.commit()
            print(f'  created {runner} in database', end='')

            # associate runner with team
            runner.teams.append(team)
            db.session.commit()
            print(f'  and added to {team}')
            return runner

        print(' mapping or creating runners:')

        for runner_dict in self.data['runners']:
            runner_id = get_runner_id(runner_dict)
            team = get_team(runner_id)
            runner = get_runner(runner_dict, team)

            if runner is None:
                runner = create_runner(runner_dict, team)

            self.map['runners'][runner_id] = runner

    def _create_race(self) -> None:
        race_dict = self.data['race']

        # determine next available group_id since this not auto-generated
        group_id = db.session.query(db.func.max(Race.id)).scalar() + 1

        # determine host_school_id
        host_school = self.map['host_school']
        host_school_id = host_school.id if host_school else None

        # create race object
        race = Race(
            group_id = group_id,
            name = race_dict['name'],
            date = datetime.strptime(race_dict['date'], "%Y-%m-%d"),
            gender = race_dict['gender'],
            scoring_type = race_dict['scoring_type'],
            status = race_dict['status'],
            host_school_id = host_school_id,
            location_id = self.map['location'][race_dict['location_id']].id,
            course_id = self.map['course'][race_dict['course_id']].id,
            is_jv = race_dict['is_jv'],
            user_id = current_user.id,
        )
        db.session.add(race)
        db.session.commit()

        self.map['race'][race_dict['id']] = race

    def _associate_race_with_schools_and_teams(self) -> None:
        race = self.map['race'][self.data['race']['id']]

        for _, school in self.map['schools'].items():
            school.races.append(race)
            db.session.commit()

        for _, team in self.map['teams'].items():
            team.races.append(race)
            db.session.commit()

    def _create_results(self) -> None:
        race = self.map['race'][self.data['race']['id']]
        res_dicts = self.data['results']

        for res_dict in res_dicts:
            runner = self.map['runners'][res_dict['runner_id']]
            team = self.map['teams'][res_dict['team_id']]
            time = res_dict['time']
            bib = res_dict['bib']
            place = res_dict['place']
            status = res_dict['status']

            res = Result(
                place=place,
                runner_id=runner.id,
                race_id=race.id,
                team_id=team.id,
                status=status,
                bib=bib,
                time=time,
            )
            db.session.add(res)
            db.session.commit()

            