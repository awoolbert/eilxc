# system imports
import os
import re
import itertools
from fuzzywuzzy import fuzz
from datetime import datetime
from collections import OrderedDict
from typing import List, Dict, Tuple, Union
from collections import namedtuple
from dataclasses import dataclass
from flask_login import current_user
from sqlalchemy import func

# local imports
from hsxc import db
from hsxc.models import School, Runner, Team, Result, Location, Race
from hsxc.models import NonDuplicate
from hsxc.helpers import time_str_to_ms, date_in_string, CUR_YEAR


SimScoreTup = namedtuple('SimScoreTup', ['score', 'runner_id'])

@dataclass
class ResFile:
    """
    Results file uploaded by user, converted to a standardized format.
    """
    fpath: str
    raw_data: List[List[str]] = None
    header: List[str] = None
    data: List[Dict[str,str]] = None
    school_map:Dict[str, int] = None
    runner_map:Dict[int, List[int]] = None
    race_date: datetime = None
    race_name: str = None
    race_gender: str = None
    race_varsity_jv: str = None
    race_scoring_type: str = None
    race_location_id: int = None
    race_course_id: int = None
    race_host_school_id: int = None
    race_id: int = None


class ResFileBuilder:
    """
    Converts uploads of various file types to a standardized ResFile object.
    """
    def __init__(self):
        self.fpath:str = None
        self.ftype:str = None
        self.first_row:int = None
        self.place_col:int = None
        self.raw_data:List[List[str]] = None
        self._col_map:Dict[str,int] = {}
        self.header:List[str] = None
        self.data:List[Dict[str,str]] = []
        self.grad_year_format:str = None
        self.race_date:datetime = None
        self.race_year:int = CUR_YEAR
        self.last_name_col:Dict[int,int] = {} 

    def build_from_file(self, fpath: str) -> ResFile:
        self.fpath = fpath
        self.ftype = fpath.split('.')[-1]
        if self.ftype == 'txt':
            self._load_txt_file()

        self._find_first_result_row()
        self._store_header()
        self._extract_race_date()
        self._determine_grad_year_format()
        self._determine_gender_format()
        self._extract_results()

        return ResFile(
            fpath     = self.fpath,
            raw_data  = self.raw_data,
            header    = self.header,
            race_date = self.race_date,
            data      = self.data
        )
        
    def _load_txt_file(self) -> None:
        with open(self.fpath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        strs_to_remove = ['(c)', '(C)', '©', ' ,']       
        def process_line(line: str):
            for s in strs_to_remove:
                line = line.replace(s, '')
            return line.strip().split()

        raw_data = [process_line(line) for line in lines if line.strip()]
        self.raw_data = raw_data

    def _find_first_result_row(self, 
        required_consecutive_lines: int = 5, 
        first_n_cols: int = 4
    ) -> None:
        """
        Returns index of first line of results.  Also finds column of place.
        """
        def is_valid_sequence(start_index, col_index) -> bool:
            for offset in range(required_consecutive_lines):
                try:
                    value = int(self.raw_data[start_index + offset][col_index])
                except (IndexError, ValueError):
                    return False
                if value != offset + 1:
                    return False
            return True

        for row_index, row in enumerate(self.raw_data):
            for col_index in range(min(first_n_cols, len(row))):
                if is_valid_sequence(row_index, col_index):
                    self.place_col = col_index
                    self.first_row = row_index
                    print(f' first row: {row_index}, place col: {col_index}')
                    print(f' first row: {self.raw_data[row_index]}')
                    return  

    def _store_header(self) -> None:
        """
        Stores header lines in self.header as single string per line (not cols).
        """
        if self.first_row > 0:
            header = [' '.join(row) for row in self.raw_data[:self.first_row]]
            header = [line.strip() for line in header if line.strip()]
        self.header = header

    def _extract_race_date(self) -> None:
        race_date = None

        for line in [self.fpath] + self.header:
            found_dt = date_in_string(line)
            if found_dt:
                race_date = found_dt
                break

        if race_date:
            print(f'race_date: {race_date}')
            self.race_date = race_date
            self.race_year = race_date.year

    def _determine_grad_year_format(self, rows_to_test: int = 10) -> None:
        first_row, race_year = self.first_row, self.race_year # for readability
        lines = self.raw_data[first_row: first_row + rows_to_test]

        years_4d = [str(year) for year in range(race_year, race_year + 8)]
        years_2d = [year[-2:] for year in years_4d]
        grade_nums = [str(grade) for grade in range(7, 13)]
        grade_names = ['SR', 'JR', 'SO', 'FR', '9', '8']
        possible_formats = [years_4d, years_2d, grade_nums, grade_names]

        for this_format in possible_formats:
            if all(any(str(c) in this_format for c in line) for line in lines):
                self.grad_year_format = this_format
                break
        print(f' grad_year format: {self.grad_year_format}')

    def _determine_gender_format(self, rows_to_test: int = 10) -> None:
        first_row = self.first_row
        lines = self.raw_data[first_row: first_row + rows_to_test]
        
        possible_formats = [['M', 'F'], ['Male', 'Female']]

        gender_format = None
        for vals_list in possible_formats:
            if all(any(col in vals_list for col in line) for line in lines):
                gender_format = vals_list
                break

        self.gender_format = gender_format
        print(f' gender format: {self.gender_format}')       

    def _extract_results(self) -> None:
        """
        Extracts data from raw_data and stores in self.data.
        """
        for i in range(self.first_row, len(self.raw_data)):
            line = self.raw_data[i].copy()
            time = self._extract_time(line)

            # break if row has no time
            if not time:
                self._col_map['last_row'] = i - 1
                break
            print(f'working: {line}')
            print(f' time: {time}')

            gender, line = self._extract_and_remove_gender(line)
            grad_year, line = self._extract_and_remove_grad_year(line)
            full_name, line = self._extract_and_remove_name(line)
            place, line = self._extract_and_remove_place(line)
            line = self._remove_remaining_numbers(line)
            school_name = self._extract_school_name(line)

            self.data.append({
                'place': place, 
                'time': time, 
                'first_name': full_name.split()[0],
                'last_name': ' '.join(full_name.split()[1:]),
                'grad_year': grad_year,
                'school': school_name,
                'gender': gender,
            })

    def _extract_time(self, line: List[str]) -> int:
        """
        Extracts time from line.  Returns time in milliseconds.
        """
        MIN_MINS_TO_EXCLUDE_PACE = 13
        for col in line:
            time_pattern = r'\d{1,2}:\d{2}(?:\.\d{1,2})?'
            match = re.search(time_pattern, col)
            if match:
                milliseconds = time_str_to_ms(match.group())
                # ensure we are getting a time and not a pace
                if milliseconds > MIN_MINS_TO_EXCLUDE_PACE * 60 * 1000:
                    return time_str_to_ms(match.group())
        return None

    def _extract_and_remove_gender(self, 
        line: List[str]
    ) -> Tuple[str, List[str]]:
        gender = None
        if self.gender_format is not None:
            for col in line:
                if col in self.gender_format:
                    gender = 'M' if col in self.gender_format[0] else 'F'
                    line.remove(col)
                    break
        print(f' gender: {gender}')
        return (gender, line)

    def _extract_and_remove_grad_year(self, 
        line: List[str]
    ) -> Tuple[int, List[str]]:
        if self.grad_year_format is None:
            return (None, line)
        
        race_year, grad_year_format = self.race_year, self.grad_year_format
        first_val = grad_year_format[0]
        grad_year = None

        # process numerical grades
        if first_val.isnumeric() and first_val == 7:
            for col in line:
                if col in grad_year_format:
                    grad_year = (13 - int(col)) + race_year
                    line.remove(col)
                    break

        # process 4-digit graduation years
        elif first_val.isnumeric() and first_val > 1000:
            for col in line:
                if col in grad_year_format:
                    grad_year = int(col)
                    line.remove(col)
                    break

        # process 2-digit graduation years
        elif first_val.isnumeric() and first_val < 100:
            for col in line:
                if col in grad_year_format:
                    grad_year = int(col) + 2000
                    line.remove(col)
                    break

        # process grade names
        else:
            for col in line:
                if col in grad_year_format:
                    grad_year = grad_year_format.index(col) + 1 + race_year
                    line.remove(col)
                    break

        print(f' grad year: {grad_year}')
        return (grad_year, line)

    def _extract_and_remove_name(self, line: List[str]) -> Tuple[str, List[str]]:
        full_name = None
        name_start = len(line)
        for idx, col in enumerate(line):
            adj_col = self._normalize_str(col)
            if adj_col.isalpha() and idx < name_start:
                name_start = idx
            elif not adj_col.isalpha() and idx > name_start:
                name_end = idx
                full_name = ' '.join(line[name_start:name_end])
                full_name_comma = None

                # switch first and last name if last name is in first column
                if ',' in full_name:
                    split_name = [name.strip() for name in full_name.split(',')]
                    last_name = split_name[0]
                    first_name = ' '.join(split_name[1:])
                    full_name_comma = full_name
                    full_name = first_name + ' ' + last_name
                break
        if full_name:
            line = self._remove_name(line, full_name)
        if full_name_comma:
            line = self._remove_name(line, full_name_comma)
        print(f' name: {full_name}')
        return (full_name, line)

    def _remove_name(self, line: List[str], full_name: str) -> List[str]:
        return [
            c for c in line 
            if c not in full_name and self._normalize_str(c) not in full_name
        ]

    def _normalize_str(self, s: str) -> str:
        CHARS_TO_STRIP = ['.', '*', '-', "'", ',', '&', '(', ')', '’']
        for char_to_remove in CHARS_TO_STRIP:
            s = s.replace(char_to_remove, '')
        return s

    def _extract_and_remove_place(self, line: List[str]) -> Tuple[str, List[str]]:
        place = line[self.place_col]
        if place: 
            line.remove(place)
        print(f' place: {place}')
        return (place, line)

    def _remove_remaining_numbers(self, line: List[str]) -> List[str]:
        strip_chars = ['.', '*', '-', "'", ',', '&', '(', ')']
        stripped_line = []
        for col in line: 
            for strip_char in strip_chars:
                col = col.replace(strip_char, '')
            stripped_line.append(col)
        with_without = zip(line, stripped_line)
        return [c[0] for c in with_without if c[1].isalpha()]

    def _extract_school_name(self, line: List[str]) -> str:
        # school name should be all that remains in line
        school_name = ' '.join(line)
        print(f' school name: {school_name}')
        return school_name


class ResFileProcessor:

    def __init__(self, res_file: ResFile):
        self.res_file = res_file

    def _normalize_string(self, s: str) -> str:
        s = s.lower()
        s = s.replace('(C)', '').replace('(c)', '')  # remove captain symbol
        s = re.sub(r'\W+', ' ', s)  # replace punctuation with single space
        s = re.sub(r'\s+', ' ', s)  # replace multiple spaces with single space
        s = s.strip()  # remove leading/trailing spaces
        return s

    def create_school_map(self) -> ResFile:
        """
        Adds school_map to res_file, a dict of school_strs:school_id(s). If
        the school_str does not closely match any school in the database, the 
        school_str is mapped to an empty list. If the school_str 'exactly' 
        matches a school in the database, the school_str is mapped to 
        the school_id. If school_str somewhat matches a school or 
        schools in the database, the school_str is mapped to a list school_ids
        that are close matches (sorted by similarity score).
        """
        schools:List[School] = School.query.all()
        school_name_tuples = [(s, s.long_name, s.short_name) for s in schools]
        school_strs = list(set([row['school'] for row in self.res_file.data]))
        EXACT_MATCH_THRESHOLD, CLOSE_MATCH_THRESHOLD = 95, 60
        
        school_map = {}
        for s_str in school_strs:    
            school_map[s_str] = []
            norm_s_str = self._normalize_string(s_str)

            # find all schools that are close matches
            for school, long_name, short_name in school_name_tuples:
                norm_long_name = self._normalize_string(long_name)
                norm_short_name = self._normalize_string(short_name)
                sim = max(
                    fuzz.token_set_ratio(norm_s_str, norm_long_name),
                    fuzz.token_set_ratio(norm_s_str, norm_short_name)
                )
                if sim >= CLOSE_MATCH_THRESHOLD:
                    school_map[s_str].append((sim,school.id))

            # sort any close matches by similarity score
            if school_map[s_str]:
                school_map[s_str].sort(key=lambda x: x[0], reverse=True)

                # if only one exact match, replace tuple list with school object
                if school_map[s_str][0][0] >= EXACT_MATCH_THRESHOLD:
                    school_map[s_str] = school_map[s_str][0][1]
                else:
                    # replace tuple list with list of school ids
                    school_map[s_str] = [s[1] for s in school_map[s_str]]

            # if no close matches, include all schools sorted alphabetically
            else:
                all_ids = school_name_tuples.copy()
                all_ids = sorted(all_ids, key=lambda x: x[1])
                school_map[s_str] = [s[0].id for s in all_ids]

        # sort from least to most confident
        def score_entry(smap_entry: tuple) -> tuple:
            is_list = isinstance(smap_entry[1], list)
            len_list = len(smap_entry[1]) if is_list else 0
            s_str = smap_entry[0]
            return (1000 - len_list, s_str)
        school_map = OrderedDict(
            sorted(school_map.items(), key=lambda x: score_entry(x))
        )

        self.res_file.school_map = school_map
        return self.res_file

    def confirm_school_mapping(self, confirmed_map:Dict[str, str]) -> ResFile:
        """
        Updates self.school_map with user responses to school name confirmation.
        Only updates school_map for responses that are numeric, since these
        are the only school_ids that were missing from the original mapping.
        """
        for school_str, user_response in confirmed_map.items():
            if user_response.isnumeric():
                self.res_file.school_map[school_str] = int(user_response)
        return self.res_file

    def set_race_meta_data(self) -> ResFile:
        self._set_gender()         # 'girls', 'boys', or None
        self._set_varsity_jv()     # 'jv', 'varsity', or None
        self._set_location_id()    # list of Location ids
        self._set_name()           # filename, first header row or school names
        self._set_scoring_type()   # 'invitational' or 'dual'
        return self.res_file

    def _set_gender(self) -> None:
        for row in [self.res_file.fpath] + self.res_file.header:
            if 'boys' in row.lower():
                self.res_file.race_gender = 'boys'
                break
            elif 'girls' in row.lower():
                self.res_file.race_gender = 'girls'
                break

    def _set_varsity_jv(self) -> None:
        for row in [self.res_file.fpath] + self.res_file.header:
            if 'jv' in row.lower() or 'junior varsity' in row.lower():
                self.res_file.race_varsity_jv = 'jv'
                break
            elif 'varsity' in row.lower():
                self.res_file.race_varsity_jv = 'varsity'
                break

    def _set_location_id(self) -> None:
        # TODO: replace with a narrower list of possible locations
        all_locs = Location.query.all()

        locs = []  # all reasonable race locations, in order of relevance

        # get a list of locations associated with schools in race
        school_id_list = self.res_file.school_map.values()
        schools = School.query.filter(School.id.in_(school_id_list)).all()
        school_locs = [l for s in schools for l in s.locations if l not in locs]

        if self.res_file.header:
            # attempt to find a location in the header
            SIM_THRESHOLD = 50
            for row in self.res_file.header:
                norm_row = self._normalize_string(row)
                for loc in all_locs:
                    norm_loc = self._normalize_string(loc.name)
                    sim = fuzz.token_set_ratio(norm_row, norm_loc)
                    if sim >= SIM_THRESHOLD:
                        locs.append((sim, loc))
            # if loc(s) found in header, sort by similarity score
            if locs:
                locs.sort(key=lambda x: x[0], reverse=True)
                locs = [loc[1] for loc in locs]

        # append other locations to list
        locs = locs + [loc for loc in school_locs if loc not in locs]
        locs = locs + [loc for loc in all_locs if loc not in locs]
        self.res_file.race_location_id = [l.id for l in locs]

    def _set_name(self) -> None:
        # race name defaults to filename if no better name can be found
        race_name = self.res_file.fpath.split(os.pathsep)[-1].split('.')[0]

        # if more than 5 schools at race, look for name in header
        if self.res_file.header and len(self.res_file.school_map) > 5:
            race_name = self.res_file.header[0]

        # otherwise, create name from school names
        elif len(self.res_file.school_map) <= 5:
            # get a list of locations associated with schools in race
            school_ids = self.res_file.school_map.values()
            loc_ids = self.res_file.race_location_id
            schools:List[School] = [School.query.get(s) for s in school_ids]
            locs:List[Location] = [Location.query.get(l) for l in loc_ids]

            # attempt to identify host school
            host_school = None
            for school in schools:
                if locs[0] in school.locations:
                    host_school = school
                    self.res_file.race_host_school_id = host_school.id
                    break
            if host_school is not None:
                guests = [s for s in schools if s != host_school]
                race_name = ', '.join([s.short_name for s in guests])
                race_name += ' at ' + host_school.short_name
            else:
                race_name = ', '.join([s.short_name for s in schools])

        self.res_file.race_name = race_name

    def _set_scoring_type(self) -> None:
        self.res_file.race_scoring_type = (
            'invitational' if len(self.res_file.school_map) > 5 else 'dual'
        )

    def confirm_race_meta_data(self, meta_data:Dict[str, str]) -> ResFile:
        self._load_meta_data_into_res_file(meta_data)
        self._create_missing_teams()
        return self.res_file

    def _load_meta_data_into_res_file(self, meta_data:Dict[str, str]) -> None:
        self.res_file.race_name = meta_data['Race Name']
        self.res_file.race_gender = meta_data['Gender'].lower()
        self.res_file.race_varsity_jv = meta_data['Varsity or JV'].lower()
        self.res_file.race_scoring_type = (
            'invitational' if meta_data['Scoring']=='Invitational' else 'dual'
        )
        date = date_in_string(meta_data['Date'])
        self.res_file.race_date = date.replace(hour=16, minute=0)
        self.res_file.race_location_id = int(meta_data['Location'])
        self.res_file.race_course_id = int(meta_data['Course'])

    def _create_missing_teams(self) -> None:
        year = self.res_file.race_date.year

        # identify all unique combinations of school and gender
        smap = self.res_file.school_map
        if self.res_file.race_gender == 'both':
            school_gender_list:List[Tuple[str, str]] = list(set(
                (smap[row['school']], row['gender']) 
                for row in self.res_file.data
            ))
        else:
            school_gender_list:List[Tuple[str, str]] = [
                (school_id, self.res_file.race_gender) 
                for school_id in smap.values()
            ]
        
        # identify missing teams and create them
        for school_id, g_str in school_gender_list:
            gender = g_str.replace('M', 'boys').replace('F', 'girls')
            school = School.query.get(school_id)
            team = Team.query.filter_by(
                school_id=school_id, year=year, gender=gender).first()
            if team is None:
                team = Team(gender, year, school.id)
                school.teams.append(team)
                db.session.add(team)
                print(f'Created team {team}')
        db.session.commit()

    def create_runner_map(self) -> ResFile:
        """
        Adds runner_map to res_file, a data idx to runner_id(s). If
        the runner name does not closely match any runner found in the database, 
        the idx is mapped to an empty list. If the runner name 'exactly'
        matches a runner in database, the idx is mapped the runner_id. If the 
        runner name somewhat matches a runner or runners in the database the 
        idx is mapped to a list of runner_ids. The list is sorted by similarity.
        """
        rmap = {
            idx: RunnerMatchFinder(
                name      = f"{row['first_name']} {row['last_name']}",
                gender    = self.res_file.race_gender,
                school_id = self.res_file.school_map[row['school']],
                grad_year = row['grad_year'],
                year      = self.res_file.race_date.year
            ).get_matches()
            for idx, row in enumerate(self.res_file.data)
        }
        rmap = self._ensure_same_exact_match_not_found_twice(rmap)
        rmap = self._ensure_exact_matches_not_in_other_lists(rmap)
        rmap = OrderedDict(sorted(rmap.items(), key=self._sim_score))

        self.res_file.runner_map = rmap
        return self.res_file

    def _ensure_same_exact_match_not_found_twice(self, 
        runner_map: Dict[int, Union[int, List[int]]]
    ) -> Dict[int, Union[int, List[int]]]:
        """
        If a runner is an exact match more than once, make it a choice for both.
        This is unlikely to happen, but covering this corner case just in case
        """
        exact_match_tuples = [
            (idx, runner_id) for idx, runner_id in runner_map.items()
            if isinstance(runner_id, int)
        ]
        if len(exact_match_tuples) > 1:
            for i, this_exact_match_tuple in enumerate(exact_match_tuples[:-1]):
                this_idx, this_runner_id = this_exact_match_tuple
                for j in range(i+1, len(exact_match_tuples)):
                    other_idx, other_runner_id = exact_match_tuples[j]
                    if this_runner_id == other_runner_id:
                        both_runner_ids_list = [this_runner_id, other_runner_id]
                        runner_map[this_idx] = both_runner_ids_list
                        runner_map[other_idx] = both_runner_ids_list
        return runner_map

    def _ensure_exact_matches_not_in_other_lists(self, 
        runner_map: Dict[int, Union[int, List[int]]]
    ) -> Dict[int, Union[int, List[int]]]:
        """
        Removes exact matches from any lists of potential matches
        """
        exact_match_ids = [
            r_list for idx, r_list in runner_map.items()
            if isinstance(r_list, int)
        ]
        for rmap_idx in runner_map:
            if isinstance(runner_map[rmap_idx], list):
                runner_map[rmap_idx] = [
                    r_id for r_id in runner_map[rmap_idx] 
                    if r_id not in exact_match_ids
                ]
        return runner_map

    def _sim_score(self, rmap_items: Tuple[int, Union[int, List[int]]]) -> int:
        idx, matching_id_or_list_of_ids = rmap_items
        first_name = self.res_file.data[idx]['first_name']
        last_name = self.res_file.data[idx]['last_name']
        name = f"{first_name} {last_name}"

        is_exact_match = isinstance(matching_id_or_list_of_ids, int)
        has_no_potential_matches = matching_id_or_list_of_ids == []
        if is_exact_match:
            return 1000
        elif has_no_potential_matches:
            return 0
        else:
            best_match_runner = Runner.query.get(matching_id_or_list_of_ids[0])
            return score_similarity_to_runner(name, best_match_runner)

    def confirm_runner_mapping(self, idx_to_runner_id:Dict[int,int]) -> ResFile:
        """
        Creates runner_map, a map of idx to runner_id
        """
        for idx, runner_id in idx_to_runner_id.items():

            # create new runner if runner_id is None
            if runner_id == None:
                row = self.res_file.data[idx]
                default_year = self.res_file.race_date.year + 4
                new_runner = Runner(
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    grad_year=(
                        row['grad_year'] if row['grad_year'] else default_year
                    ),
                    seed_time=row['time'],
                )
                db.session.add(new_runner)
                self.res_file.runner_map[idx] = new_runner.id
                print(f' created runner {new_runner}')
            else:
                self.res_file.runner_map[idx] = runner_id
        db.session.commit()

        self._ensure_all_runners_on_team()
        return self.res_file

    def _ensure_all_runners_on_team(self) -> None:
        team_year = self.res_file.race_date.year
        r_map = self.res_file.runner_map
        s_map = self.res_file.school_map
        race_gender = self.res_file.race_gender
        for idx, row in enumerate(self.res_file.data):
            runner = Runner.query.get(r_map[idx])
            gender = row['gender'] if row['gender'] else race_gender
            gender = gender.replace('M', 'boys').replace('F', 'girls')
            school:School = School.query.get(s_map[row['school']])
            team = Team.query.filter_by(
                year=team_year, school_id=school.id, gender=gender
            ).first()

            # create team if needed
            if team is None:
                team = Team(gender=gender, year=team_year, school_id=school.id)
                school.teams.append(team)

            # add runner to team if needed
            if runner not in team.runners:
                team.runners.append(runner)
                print(f' added RUNNER:{runner}) to TEAM:{team}')

            self.res_file.data[idx]['team_id'] = team.id
        db.session.commit()

    def finalize_race(self) -> int:
        self._create_race()
        self._add_race_to_schools()
        self._add_race_to_teams()
        self._create_results()
        return self.res_file.race_id

    def _create_race(self) -> None:
        max_group_id = Race.query.with_entities(func.max(Race.group_id)).scalar()
        print(f' race_name: {self.res_file.race_name}')
        this_race = Race(
            user_id=current_user.id,
            date=self.res_file.race_date,
            name=self.res_file.race_name,
            gender=self.res_file.race_gender,
            scoring_type=self.res_file.race_scoring_type,
            status='complete',
            host_school_id=self.res_file.race_host_school_id,
            location_id=self.res_file.race_location_id,
            course_id=self.res_file.race_course_id,
            group_id=max_group_id + 1,
            is_jv = True if self.res_file.race_varsity_jv == 'jv' else False,
        )
        db.session.add(this_race)
        print(f' adding {this_race.name} to db')
        db.session.commit()
        self.res_file.race_id = this_race.id

    def _add_race_to_schools(self) -> None:
        race = Race.query.get(self.res_file.race_id)

        # get all schools in race
        schools = School.query.filter(
            School.id.in_(self.res_file.school_map.values())
        ).all()

        # add race to each school's races
        for school in schools:
            print(f' adding {school} to {race}')
            race.schools.append(school)
            db.session.commit()

    def _add_race_to_teams(self) -> None:
        race = Race.query.get(self.res_file.race_id)

        # determine all teams represented in race
        team_ids = list(set([row['team_id'] for row in self.res_file.data]))
        teams = [Team.query.get(team_id) for team_id in team_ids]

        # add race to each team's races
        for team in teams:
            print(f' adding {race} to {team}')
            team.races.append(race)
            db.session.commit()

    def _create_results(self) -> None:
        for idx, row in enumerate(self.res_file.data):
            result = Result(
                bib=None,
                time=row['time'],
                place=row['place'],
                status='c',
                runner_id=self.res_file.runner_map[idx],
                race_id=self.res_file.race_id,
                team_id=row['team_id'],
            )
            db.session.add(result)
            print(f' created result {result}')
        db.session.commit()


class RunnerMatchFinder:

    def __init__(self, 
        name: str,
        gender: str = None,
        school_id: int = None,
        grad_year: int = None, 
        year: int = None,
        exact_threshold: int = 90,
        close_threshold: int = 55,
    ) -> None:
        self.name = name
        self.gender = gender
        self.school_id = school_id
        self.grad_year = grad_year
        self.year = year
        self.exact_threshold = exact_threshold
        self.close_threshold = close_threshold
        self.similar_runners: Union[int, List[int]] = None

    def get_matches(self) -> Union[int, List[int]]:
        """
        Returns (i) a single runner_id if one exact match, (ii) a list of 
        runner_ids if likely matches (sorted by similarity), or (iii) an empty 
        list if no matches.
        """
        self._set_possible_runners()
        self._score_possible_runners_by_similarity()
        return self._limit_and_sort_possible_runners()
    
    def _set_possible_runners(self) -> None:
        """
        Sets self.possible_runners to a list of runners that are possible
        matches for the runner being searched for.
        """
        runners: List[Runner] = []

        # limit by school if provided
        if self.school_id is not None:
            school: School = School.query.get(self.school_id)
            runners: List[Runner] = school.all_runners()
        else:
            runners = Runner.query.all()

        # limit by gender if provided
        if self.gender is not None:
            runners = [r for r in runners if r.gender == self.gender]

        # limit by grad_year if provided (or by race_year if not provided)
        if self.grad_year is not None:
            runners = [r for r in runners if r.grad_year == self.grad_year]
        elif self.year is not None:
            potential_years = list(range(self.year + 1, self.year + 8))
            runners = [r for r in runners if r.grad_year in potential_years]

        self.possible_runners = runners

    def _score_possible_runners_by_similarity(self) -> None:
        name = self.name
        self.scores: List[SimScoreTup] = [
            SimScoreTup(score_similarity_to_runner(name, runner), runner.id)
            for runner in self.possible_runners
        ]
    
    def _limit_and_sort_possible_runners(self) -> Union[int, List[int]]:
        similars = [r for r in self.scores if r.score >= self.close_threshold]

        # return empty list if no similar runners
        if not similars:
            return similars

        # sort by similarity score
        similars.sort(key=lambda x: x.score, reverse=True)

        # if multiple matches have same score, prefer same first initial
        if len(similars) > 1:
            top_sim_score = similars[0].score
            ties = [r for r in similars if r.score == top_sim_score]
            ties = ties if len(ties) > 1 else []
            target_first_initial = self.name.split()[0][0].lower()
            for tie in ties:
                runner: Runner = Runner.query.get(tie.runner_id)
                has_same_first_initial = (
                    runner.first_name[0].lower() == target_first_initial
                    or runner.nickname[0].lower() == target_first_initial
                )
                if has_same_first_initial:
                    idx = similars.index(tie)
                    similars = [tie] + similars[:idx] + similars[idx+1:]

        # determine exact matches
        exacts = [r for r in similars if r.score >= self.exact_threshold]

        # if no exact matches, return all similar runners
        if not exacts:
            return [r.runner_id for r in similars]
        
        # if one exact match, return that runner else return all exact matches
        if len(exacts) == 1:
            return exacts[0].runner_id
        else:
            return [r.runner_id for r in exacts]


def score_similarity_to_runner(name: str, runner: Runner) -> int:
    def normalize_string(s: str) -> str:
        s = s.lower()
        s = s.replace('(C)', '').replace('(c)', '')  # remove captain symbol
        s = re.sub(r'\W+', ' ', s)  # replace punctuation with single space
        s = re.sub(r'\s+', ' ', s)  # replace multiple spaces with single space
        s = s.strip()  # remove leading/trailing spaces
        return s
    name = normalize_string(name)
    runner_name = f'{runner.first_name} {runner.last_name}'
    runner_name = normalize_string(runner_name)
    return fuzz.token_set_ratio(name, runner_name)

def find_runners_needing_merge() -> List[Tuple[Runner, Runner]]:

    def _normalize_string(s: str) -> str:
        s = s.lower()
        s = s.replace('(C)', '').replace('(c)', '')  # remove captain symbol
        s = re.sub(r'\W+', ' ', s)  # replace punctuation with single space
        s = re.sub(r'\s+', ' ', s)  # replace multiple spaces with single space
        s = s.strip()  # remove leading/trailing spaces
        return s

    needs_merge = []
    all_schools: List[School] = School.query.all()
    for school in all_schools:
        school_runners = [
            r for team in school.teams for r in team.runners
        ]
        combos:List[Tuple[Runner, Runner]] = (
            list(itertools.combinations(school_runners, 2))
        )
        for r1, r2 in combos:
            if r1.id == r2.id:
                continue
            r1_str = f'{r1.first_name} {r1.last_name} {r1.get_gender()}'
            r2_str = f'{r2.first_name} {r2.last_name} {r2.get_gender()}'
            norm_r1_str = _normalize_string(r1_str)
            norm_r2_str = _normalize_string(r2_str)
            sim = fuzz.token_set_ratio(norm_r1_str, norm_r2_str)
            if sim >= 90 and not has_already_been_marked_non_duplicate(r1, r2):
                if (r1, r2) not in needs_merge and (r2, r1) not in needs_merge:
                    needs_merge.append((r1, r2))
                    print(f' {r1} and {r2} need to be merged')
    return needs_merge

def has_already_been_marked_non_duplicate(runner_1:Runner, runner_2:Runner) -> bool:
    """Returns True if runner_1 and runner_2 have already been marked as
    non-duplicates.

    Args:
        runner_1 (Runner): 
        runner_2 (Runner): 

    Returns:
        bool: True if runner_1 and runner_2 have already been marked as
            non-duplicates.
    """
    non_duplicates = NonDuplicate.query.all()
    for nd in non_duplicates:
        if nd.runner1_id == runner_1.id and nd.runner2_id == runner_2.id:
            return True
        if nd.runner1_id == runner_2.id and nd.runner2_id == runner_1.id:
            return True
    return False

def merge_runners(runner_1:Runner, runner_2:Runner) -> None:
    """Merges two runners into one new runner and updates all database entries.
    Combined runner uses name and grad_year from runner_1.

    Args:
        runner1 (Runner): Name and grad_year will be used for new runner
        runner2 (Runner): Will be deleted, all entries to use runner_1
    """
    print(f'Merging {runner_1} and {runner_2}')

    # create new_runner
    combined_runner = Runner(
        first_name=runner_1.first_name,
        last_name=runner_1.last_name,
        grad_year=runner_1.grad_year,
        seed_time=(runner_1.seed_time + runner_2.seed_time) / 2
    )
    db.session.add(combined_runner)
    db.session.commit()

    # Update results
    for runner in [runner_1, runner_2]:
        Result.query.filter_by(runner_id=runner.id).update(
            {'runner_id': combined_runner.id}
        )

    # Add new_runner to all teams
    for runner in [runner_1, runner_2]:
        for team in runner.teams:
            if combined_runner not in team.runners:
                team.runners.append(combined_runner)
                print(f'Added {combined_runner} to {team}')

    # Delete the second runner
    for runner in [runner_1, runner_2]:
        db.session.delete(runner)
        db.session.flush()

    db.session.commit()

def transfer_runner_to_new_school(runner_id: int, school_id: int) -> None:
    runner = Runner.query.get(runner_id)
    school = School.query.get(school_id)

    # find previous_year_team of runner
    prev_year_team = [t for t in runner.teams if t.year == CUR_YEAR-1]
    if len(prev_year_team) != 1:
        print(f'ERROR: {runner} has {len(prev_year_team)} teams in {CUR_YEAR-1}')
        return
    prev_year_team = prev_year_team[0]

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
        return
    target_team = target_team[0]

    # add runner to target_team
    target_team.runners.append(runner)
    db.session.commit()
    print(f'Added {runner} to {target_team}')

    return


