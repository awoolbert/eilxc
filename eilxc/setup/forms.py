# Form Based Imports
from flask_wtf import FlaskForm
from wtforms import (StringField, DecimalField, SubmitField,
                     IntegerField, SelectField)
from wtforms.validators import DataRequired,Email,EqualTo, Length
from wtforms import ValidationError
from flask_wtf.file import FileField, FileAllowed
import datetime

# User Based Imports
from flask_login import current_user
from eilxc.models import User

class LocationCourseForm(FlaskForm):
    location_name = StringField('Name for this location', validators=[DataRequired()])
    street_number = StringField('Number', validators=[DataRequired()])
    street_name = StringField('Street', validators=[DataRequired()])
    city = StringField('City', validators=[DataRequired()])
    state_abbr = StringField('State', validators=[DataRequired()])
    zip = StringField('Zip', validators=[DataRequired()])
    course_name = StringField('Name of the course (displayed in header of results)', validators=[DataRequired()])
    course_description = StringField('Course Description', validators=[DataRequired()])
    distance = DecimalField('Distance', validators=[DataRequired()])
    submit = SubmitField('Submit')

class CourseForm(FlaskForm):
    course_name = StringField('Name of the course (displayed in header of results)', validators=[DataRequired()])
    course_description = StringField('Course Description', validators=[DataRequired()])
    distance = DecimalField('Distance', validators=[DataRequired()])
    submit = SubmitField('Submit')

class SchoolForm(FlaskForm):
    long_name = StringField('Full Name', validators=[DataRequired()])
    short_name = StringField('Short Name', validators=[DataRequired(), Length(max=11)])
    city = StringField('City', validators=[DataRequired()])
    state_abbr = StringField('State (2-letter code)', validators=[DataRequired(), Length(max=2)])
    primary_color = StringField('Primary Color', validators=[DataRequired()])
    text_color = StringField('Text Color', validators=[DataRequired()])
    league_id = IntegerField('League', validators=[DataRequired()])
    submit = SubmitField('Submit')

class RunnerForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    year = datetime.datetime.today().year
    choices = []
    for i in range(7):
        choices.append((str(year+1+i), str(year+1+i)))
    grad_year = SelectField('Class', choices=choices, validators=[DataRequired()])
    minutes = DecimalField('Mins', validators=[DataRequired()])
    seconds = DecimalField('Secs')
    submit = SubmitField('Add runner')
