# external imports
from typing import List, Dict, Tuple, Set, Optional
from statistics import median, mean, stdev
from dataclasses import dataclass

# hsxc imports
from hsxc import db
from hsxc.models.race import Race
from hsxc.models.course import Course
from hsxc.models.runner import Runner
from hsxc.models.result import Result
from hsxc.helpers import CUR_YEAR, timify

MIN_RUNNERS_REQUIRED = 20
MAX_RUNNERS_USED = 5000
MIN_COURSES_REQUIRED = 4
YEARS = [y for y in range(2019, CUR_YEAR+1)]

@dataclass
class RunnerDiff:
    """
    Dataclass for storing data about a runner's performance on two courses
    in a given year.  Differences are defined to be percentage differences.
    """
    runner: Runner
    year: int
    diff: float
    diff_f: str
    course_median: int
    other_median: int
    course_median_f: str
    other_median_f: str
    course_results: List[Result]
    other_results: List[Result]

@dataclass
class CourseDiff:
    """
    Dataclass for storing data about a course's results relative to another.
    The difference is calculated as the lower bound of the 95% confidence
    interval based on the winsorized distribution of runner diffs.
    """
    other_course: Course
    diff: float
    diff_f: str
    runner_diffs: List[RunnerDiff]
    num_runners: int = None

@dataclass
class CourseAdjustment:
    """
    Dataclass for storing data about a course's overall adjustment, which is
    the median of all course diffs.
    """
    course: Course
    adj: float
    adj_f: str
    course_diffs: List[CourseDiff]

    def __str__(self) -> str:
        return (
            f'course: {self.course}, '
            f'adjustment: {int(self.adj/1000)} secs, '
            f'course comparisons: {len(self.course_diffs)}, '
            f'runners per comparison: {MIN_RUNNERS_REQUIRED}'
        )


class CourseAdjuster:
    def __init__(self, course_id: int) -> None:
        self.course = Course.query.get(course_id)

    def run(self) -> Optional[CourseAdjustment]:
        # get a list of all other courses
        other_courses: List[Course] = [
            c for c in Course.query.all() 
            if c.id != self.course.id and not c.is_championship_course()
        ]
        print(f' comparing {self.course} to {len(other_courses)} other courses')

        # find all course diffs for courses with sufficient number of runners
        course_diffs: List[CourseDiff] = [
            self._calc_course_diff(other_course) 
            for other_course in other_courses
        ]
        course_diffs = [diff for diff in course_diffs if diff is not None]
        course_diffs = sorted(course_diffs, key=lambda x: x.diff)

        print(f' found {len(course_diffs)} courses with sufficient data')
        if len(course_diffs) < MIN_COURSES_REQUIRED: 
            # set adjustment to 0 because insufficient data
            adjustment = 0
            adjustment_f = f'N/A (insufficient data)'

        else:
            # calculate adjustment
            adjustment = median([diff.diff for diff in course_diffs])
            adj_prefix = 'Add' if adjustment > 0 else 'Subtract'
            adjustment_f = f'{adj_prefix} {round(abs(adjustment)*100,2)}%'

        # update database
        self.course.adj = adjustment
        db.session.commit()

        # force 0 adjustment for championship courses
        if self.course.is_championship_course():
            self.course.adj = 0
            adjustment_f = f'No Adjustment Made for Championship Course'
            db.session.commit()

        return CourseAdjustment(
            course=self.course,
            adj=adjustment,
            adj_f=adjustment_f,
            course_diffs=course_diffs
        )

    def _calc_course_diff(self, other_course:Course) -> Optional[CourseDiff]:
        # get races run on this course by year
        races: List[Race] = Race.query.filter_by(course_id=self.course.id).all()
        races_by_year: Dict[int, List[Race]] = {
            year: [r for r in races if r.date.year == year] for year in YEARS
        }

        # get all unique (runner, year) tuples for runners who ran this course
        runners: Set[Tuple[Runner, int]] = {
            (res.runner, year) 
            for year, race_list in races_by_year.items() 
            for race in race_list 
            for res in race.results
        }

        # get list of runner diffs for all runners who ran both courses
        runner_diffs: RunnerDiff = [
            self._calc_runner_diff(runner, other_course, year)
            for runner, year in runners
        ]
        runner_diffs = [diff for diff in runner_diffs if diff is not None]

        # abort if not enough runners
        if len(runner_diffs) < MIN_RUNNERS_REQUIRED: return None

        # limit to top runners (by time on this course)
        runner_diffs = sorted(runner_diffs, key=lambda x: x.course_median)
        runner_diffs = runner_diffs[0:MAX_RUNNERS_USED]

        # sort runner_diffs by diff
        runner_diffs = sorted(runner_diffs, key=lambda x: x.diff)

        # winsorize data to exclude bizarre outliers which might skew data
        num_to_cut = int(len(runner_diffs) * 0.05)
        if num_to_cut > 0:
            runner_diffs = runner_diffs[num_to_cut:-num_to_cut]

        # calc z_score given distribution of differences
        mean_diff = mean([diff.diff for diff in runner_diffs])
        stdev_diffs = stdev([diff.diff for diff in runner_diffs])
        num_runners = len(runner_diffs)
        z_score = stdev_diffs / num_runners**0.5

        # calc course diff, use bound of 95% confidence interval closest to 0
        coeff = -1 if mean_diff > 0 else 1
        course_diff = mean_diff + coeff * min(abs(mean_diff), 1.96 * z_score)

        # create formatted course diff for display
        prefix = '+' if course_diff > 0 else '-' if course_diff < 0 else ''
        diff_f = f'{prefix}{round(abs(course_diff)*100,2)}%'

        return CourseDiff(
            other_course=other_course,
            diff=course_diff,
            diff_f=diff_f,
            runner_diffs=runner_diffs,
            num_runners=num_runners,
        ) 

    def _calc_runner_diff(
        self, 
        runner: Runner, 
        other_course:Course,
        year: int
    ) -> Optional[RunnerDiff]:

        # get results on this course
        course_results: List[Result] = [
            res for res in runner.completed_results()
            if res.race.course == self.course and res.race.date.year == year
        ]
        if not course_results: return None

        # get results on other course
        other_results: List[Result] = [
            res for res in runner.completed_results()
            if res.race.course == other_course and res.race.date.year == year
        ]
        if not other_results: return None

        # use median times if there are multiple results
        course_median = median([res.pace for res in course_results])
        other_median = median([res.pace for res in other_results])
        course_median_str = timify(course_median)
        other_median_str = timify(other_median)

        # calculate diff
        diff = other_median / course_median - 1
        diff_f = f"{'+' if diff > 0 else '-'}{round(abs(diff)*100,2)}%"

        return RunnerDiff(
            runner=runner,
            year=year,
            diff=diff,
            diff_f=diff_f,
            course_median=course_median,
            other_median=other_median,
            course_median_f=course_median_str,
            other_median_f=other_median_str,
            course_results=course_results,
            other_results=other_results
        )


def update_all_course_adjustments() -> Dict[int, int]:
    # perform all calculations
    all_courses: List[Course] = Course.query.all()
    adjusters: Dict[Course, CourseAdjustment] = {
        course: CourseAdjuster(course.id).run()
        for course in all_courses
    }

    # report on reuslts
    for course, adj in adjusters.items():
        if adj is None: continue
        print(f'{course}: {adj.adj_f}')

    return {
        course.id: adj.adj if adj is not None else 0 
        for course, adj in adjusters.items()
    }


class YearEndEffectCalculator:

    def __init__(self) -> None:
        self.all_races: List[Race] = Race.query.all()

    def run(self) -> None:
        for year in self._get_all_potential_years():
            self._calc_year_end_effect(year)
        pass

    def _get_all_potential_years(self) -> List[int]:
        years = {race.date.year for race in self.all_races}
        years = sorted(list(years))
        return years
    
    def _calc_year_end_effect(self, year: int) -> None:
        race_matches = self._get_reg_season_races_on_champ_course(year)
        # determine number of days between races
        # calculate estimate year-end effect
        pass

    def _get_reg_season_races_on_champ_course(self, 
        year: int
    ) -> Dict[Race, List[Race]]:
        races: List[Race] = [r for r in self.all_races if r.date.year == year]
        c_races = [race for race in races if race.is_championship()]
        r_races = [race for race in races if race not in c_races]
        c_courses: List[Course] = list({race.course for race in c_races})
        race_matches = [
            {'course': course,
             'c_races': [r for r in c_races if r.course == course],
             'r_races': [r for r in r_races if r.course == course]} 
            for course in c_courses
        ]
        race_matches = [
            c_dict for c_dict in race_matches if c_dict['r_races']
        ]
        print('\n', year)
        print(race_matches)
        return race_matches
