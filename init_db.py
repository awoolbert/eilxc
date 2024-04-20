from hsxc import app, db
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, LargeBinary
from flask_session import SqlAlchemySessionInterface

class SessionTable(db.Model):
    id = Column(Integer, primary_key=True)
    session_id = Column(String, unique=True)
    data = Column(LargeBinary)
    expiry = Column(db.DateTime)

    def __init__(self, session_id, data, expiry):
        self.session_id = session_id
        self.data = data
        self.expiry = expiry

with app.app_context():
    db.create_all()
