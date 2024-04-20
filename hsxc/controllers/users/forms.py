# Form Based Imports
from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, SubmitField,
                     SelectField, BooleanField)
from wtforms.validators import DataRequired,Email,EqualTo, Length
from wtforms import ValidationError
from flask_wtf.file import FileField, FileAllowed

# User Based Imports
from flask_login import current_user
from hsxc.models import User, School




class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Log In')


class RegistrationForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    choices = [('0', 'Select a School')]

    schools = School.query.all()
    schools = sorted(schools, key=lambda s: s.long_name)
    for s in schools:
        choices.append((str(s.id), s.long_name))
    school = SelectField('School Affiliation', choices=choices, validators=[DataRequired()])

    email = StringField('Email', validators=[DataRequired(),Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    pass_confirm = PasswordField('Confirm password', validators=[DataRequired(), EqualTo('password', message='Passwords Must Match')])
    submit = SubmitField('Register')

    def validate_email(self, field):
        # Check if not None for that user email!
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('That email address is already registered')

class UpdateUserForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(),Email()])
    submit = SubmitField('Update')

    def validate_email(self, field):
        # Check if not None for that user email!
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('That email address is already registered')

class RequestResetForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(),Email()])
    submit = SubmitField('Request Password Reset')

    def validate_email(self, field):
        # Check if not None for that user email!
        if User.query.filter_by(email=field.data).first() is None:
            raise ValidationError('There is no account with that email address.')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])
    pass_confirm = PasswordField('Confirm password', validators=[DataRequired(), EqualTo('password', message='Passwords Must Match')])
    submit = SubmitField('Reset Password')
