# external imports
import time
from sqlalchemy import desc
from itertools import combinations
from typing import TYPE_CHECKING, List

# hsxc imports
from hsxc import db
from hsxc.helpers import CUR_YEAR
from .associations import league_managers

if TYPE_CHECKING:
    from .school import School
    from .user import User

class League(db.Model):
    __tablename__ = 'leagues'

    id = db.Column(db.Integer, primary_key = True)
    long_name = db.Column(db.String(64), nullable=False)
    short_name = db.Column(db.String(16), nullable=False)
    schools: List['School'] = db.relationship('School', backref='league', lazy=True)
    managers: List['User'] = db.relationship('User', secondary=league_managers)

    def __init__(self, long_name: str, short_name: str) -> None:
        self.long_name = long_name
        self.short_name = short_name

    def __repr__(self) -> str:
        return f"id:{self.id}, League:{self.long_name} ({self.short_name})"

    def alphabetized_schools(self) -> List['School']:
        return sorted(self.schools, key=lambda x: x.long_name)