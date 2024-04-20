# external imports

# hsxc imports
from hsxc import db

class SessionTable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String, unique=True)
    data = db.Column(db.LargeBinary)
    expiry = db.Column(db.DateTime)

    def __init__(self, session_id, data, expiry):
        self.session_id = session_id
        self.data = data
        self.expiry = expiry
