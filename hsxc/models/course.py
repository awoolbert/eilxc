# external imports
from sqlalchemy import desc
from typing import TYPE_CHECKING, List

# hsxc imports
from hsxc import db

if TYPE_CHECKING:
    from .race import Race
    from .location import Location
    from .result import Result

class Course(db.Model):
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key = True)
    name: str = db.Column(db.String(32))
    description = db.Column(db.Text)
    distance = db.Column(db.Float)
    adj = db.Column(db.Float, default=0.0)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    location: 'Location' = db.relationship('Location', back_populates='courses', uselist=False)
    races: List['Race'] = db.relationship('Race', backref='course', lazy=True)

    def __init__(self, name, description, distance, location_id):
        max_id = Course.query.order_by(desc(Course.id)).first().id
        self.id = max_id + 1
        self.name = name
        self.description = description
        self.distance = distance
        self.location_id = location_id

    def __repr__(self):
        return (f"id:{self.id} {self.name}")

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'distance': self.distance,
            'location_id': self.location_id
        }

    def meters(self) -> str:
        return f'{int(self.distance * 1000):,}'

    def miles(self) -> float:
        return self.distance * 0.621371

    def is_championship_course(self) -> bool:
        return (
            'championship' in self.name.lower() 
            or 'championship' in self.description.lower()
        )

    def adj_f(self) -> str:
        prefix = '+' if self.adj > 0 else '-'
        val = f'{abs(self.adj):.1%}'
        return f'{prefix}{val}'
    
    def results(self) -> List['Result']:
        return [res for race in self.races for res in race.results]