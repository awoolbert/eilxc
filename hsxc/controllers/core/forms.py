# external imports
from flask_wtf import FlaskForm
from wtforms import (StringField, DecimalField, SubmitField, SelectField)
from wtforms.validators import DataRequired

# hsxc imports

class RunnerForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    grad_year = SelectField('Class', validators=[DataRequired()])
    minutes = DecimalField('Mins', validators=[DataRequired()])
    seconds = DecimalField('Secs')
    submit = SubmitField('Add runner')

    def __init__(self, choices, *args, **kwargs):
        super(RunnerForm, self).__init__(*args, **kwargs)
        self.grad_year.choices = [(str(c),str(c)) for c in choices]
