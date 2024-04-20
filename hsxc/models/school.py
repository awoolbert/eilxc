# external imports
from os import access, F_OK
from typing import List, TYPE_CHECKING

# hsxc imports
from hsxc import db
from hsxc.helpers import CUR_YEAR
from .associations import school_locations, race_schools, school_coaches
from .league import League
from .team import Team

if TYPE_CHECKING:
    from .runner import Runner
    from .race import Race
    from .location import Location
    from .user import User


class School(db.Model):
    __tablename__ = 'schools'

    leagues = db.relationship(League)

    id:int = db.Column(db.Integer, primary_key=True, autoincrement=True)
    long_name:str = db.Column(db.String(64), nullable=False)
    short_name:str = db.Column(db.String(16), nullable=False)
    primary_color:str = db.Column(db.String(10))
    secondary_color:str = db.Column(db.String(10))
    text_color:str = db.Column(db.String(10))
    city:str = db.Column(db.String(32))
    state_abbr:str = db.Column(db.String(2))
    league_id:int = db.Column(
        db.Integer, db.ForeignKey('leagues.id'), nullable=False
    )

    teams: List[Team] = db.relationship('Team', backref='school', lazy=True)
    coaches: List['User'] = db.relationship('User', secondary=school_coaches)
    races: List['Race'] = db.relationship('Race', backref='host_school', lazy=True)
    locations: List['Location'] = db.relationship('Location', secondary=school_locations)
    all_races: List['Race'] = db.relationship('Race', secondary=race_schools)

    def __init__(
        self, 
        long_name: str, 
        short_name: str, 
        city: str, 
        state_abbr: str, 
        league_id: int,
        primary_color: str, 
        secondary_color: str, 
        text_color: str
    ) -> None:
        max_id = db.session.query(db.func.max(School.id)).scalar()
        self.id = max_id + 1
        self.long_name = long_name
        self.short_name = short_name
        self.city = city
        self.state_abbr = state_abbr
        self.league_id = league_id
        self.primary_color = primary_color
        self.secondary_color = secondary_color
        self.text_color = text_color

    def __repr__(self) -> str:
        return f"{self.short_name}"

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'long_name': self.long_name,
            'short_name': self.short_name,
            'city': self.city,
            'state_abbr': self.state_abbr,
            'league_id': self.league_id,
            'primary_color': self.primary_color,
            'secondary_color': self.secondary_color,
            'text_color': self.text_color
        }

    def current_year_teams(self) -> List['Team']:
        return [team for team in self.teams if team.year == CUR_YEAR]

    def has_current_year_results(self) -> bool:
        for team in self.current_year_teams():
            for race in team.races:
                if race.status == 'complete' and team.has_five_runners(race):
                    return True
        return False

    def get_team(self, year: int, gender: str) -> 'Team':
        return Team.query.filter_by(
            school_id = self.id, 
            year = year, 
            gender = gender.lower()
        ).first()

    def old_img_filename(self) -> str:
        """
        Build the filename of the logo graphic from the school short name.

        Return: string representing the filename
        """
        fname = f'img/{self.short_name}-logo.png'.lower()
        fname = fname.replace(' ', '')
        fname = fname.replace('st.', 'st')
        fname = fname.replace('&', '')
        fname = fname.replace("'", "")
        return fname

    def img_filename(self) -> str:
        """
        Build the filename of the logo graphic from the school short name.

        Return: string representing the filename
        """
        fname = self.short_name.lower()
        for c in [' ', '.', '&', "'", '(', ')', '-']:
            fname = fname.replace(c, '')
        fname = f'img/{fname}-{self.id}-logo.png'

        return fname

    def has_image(self) -> bool:
        return access(f'hsxc/static/{self.img_filename()}', F_OK)

    def all_runners(self) -> List['Runner']:
        """
        Return a list of all runners for the school
        """
        return list(set([r for t in self.teams for r in t.runners]))

    def completed_races(self) -> List['Race']:
        return [r for r in self.all_races if r.status == 'complete']





    def get_team_gender(self) -> int:
        if self.teams:
            return 1 if self.teams[0].gender == 'girls' else 2
        else:
            return 0


