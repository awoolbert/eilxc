# external imports
from flask_login import UserMixin
from werkzeug.security import generate_password_hash,check_password_hash
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from typing import List

# hsxc imports
from hsxc import db, login_manager, app
from .associations import league_managers, school_coaches


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key = True)
    first_name = db.Column(db.String(32))
    last_name = db.Column(db.String(32))
    email = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    leagues_managed = db.relationship('League', secondary=league_managers)
    schools_coached = db.relationship('School', secondary=school_coaches)
    setups = db.relationship('Race', backref='user', lazy=True)

    def __init__(self, first_name, last_name, email, password):
        current_max_id = db.session.query(db.func.max(User.id)).scalar()
        self.id: int = current_max_id + 1 if current_max_id else 1
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.password_hash = generate_password_hash(password)

    def check_password(self,password) -> bool:
        return check_password_hash(self.password_hash,password)

    def get_reset_token(self, expires_sec=1800):
        s = Serializer(app.config['SECRET_KEY'], expires_sec)
        return s.dumps({'user_id': self.id}).decode('utf-8')

    def is_administrator(self) -> bool:
        return True if self.id == 1 else False

    def races_ready_to_start(self) -> list:
        return [race for race in self.setups if race.status == 'ready']

    def races_in_setup(self) -> list:
        return [
            race for race in self.setups
            if race.status != 'complete'
            and race.status != 'ready'
        ]

    def display_name(self) -> str:
        return f'{self.first_name} {self.last_name}'

    @staticmethod
    def verify_reset_token(token) -> 'User':
        s = Serializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token)['user_id']
        except:
            return None
        return User.query.get(user_id)

    def __repr__(self):
        return f"id:{self.id}, email:{self.email}"

