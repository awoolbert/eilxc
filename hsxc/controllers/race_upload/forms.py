# external imports
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import SubmitField

class UploadForm(FlaskForm):
    file = FileField("", validators=[
        FileRequired(),
        FileAllowed(['csv', 'txt', 'pdf'], 'Only CSV, TXT and PDF files allowed')
    ])
    submit = SubmitField('Submit')

class RaceImportForm(FlaskForm):
    file = FileField("", validators=[
        FileRequired(),
        FileAllowed(['json'], 'Only json files allowed')
    ])
    submit = SubmitField('Submit')
