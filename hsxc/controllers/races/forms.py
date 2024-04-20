# external imports
from flask_wtf import FlaskForm
from wtforms import SelectField, SelectMultipleField
from wtforms.validators import DataRequired

# hsxc imports
from hsxc.helpers import CUR_YEAR

class HypotheticalRaceForm(FlaskForm):
    gender = SelectField(
        'Gender', 
        choices=[('boys', 'Boys'),('girls', 'Girls')], 
        validators=[DataRequired()]
    )
    schools = SelectMultipleField('Schools', coerce=int)  
    scoring_type = SelectField(
        'Scoring Type', 
        choices=[('dual', 'Dual'), ('invitational', 'Invitational')], 
        validators=[DataRequired()]
    )
    times_to_use = SelectField(
        'Times to Use', 
        choices=[
            ('pr_current_year', 'Current Year PR'), 
            ('pr', 'Lifetime PR'), 
            ('seed_time', 'Median of Last 3 Races')], 
        validators=[DataRequired()]
    )