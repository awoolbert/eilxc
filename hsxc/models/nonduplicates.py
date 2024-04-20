# external imports

# hsxc imports
from hsxc import db

class NonDuplicate(db.Model):
    __tablename__ = 'non_duplicates'
    id = db.Column(db.Integer, primary_key=True)
    runner1_id = db.Column(db.Integer, db.ForeignKey('runners.id'), nullable=False)
    runner2_id = db.Column(db.Integer, db.ForeignKey('runners.id'), nullable=False)

    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    def __init__(self, runner1_id, runner2_id):
        self.runner1_id = runner1_id
        self.runner2_id = runner2_id