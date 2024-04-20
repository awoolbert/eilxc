# external imports
from sqlalchemy import desc
from typing import TYPE_CHECKING, List

# hsxc imports
from hsxc import db
from .associations import school_locations

if TYPE_CHECKING:
    from .school import School
    from .course import Course
    from .race import Race

class Location(db.Model):
    __tablename__ = 'locations'

    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(32))
    street_address = db.Column(db.String(64))
    city = db.Column(db.String(32))
    state_abbr = db.Column(db.String(2))
    zip = db.Column(db.String(5))
    courses: List['Course'] = db.relationship('Course', back_populates='location')
    races: List['Race'] = db.relationship('Race', backref='location', lazy=True)
    schools: List['School'] = db.relationship('School', secondary=school_locations)

    def __init__(self, name, street_address, city, state_abbr, zip):
        max_id = Location.query.order_by(desc(Location.id)).first().id
        self.id = max_id + 1
        self.name = name
        self.street_address = street_address
        self.city = city
        self.state_abbr = state_abbr
        self.zip = zip

    def __repr__(self):
        return (f"id:{self.id}  {self.name}")

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'street_address': self.street_address,
            'city': self.city,
            'state_abbr': self.state_abbr,
            'zip': self.zip
        }

    def address(self) -> str:
        return f'{self.street_address}, {self.city}, {self.state_abbr} {self.zip}'


