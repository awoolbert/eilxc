# Configuration
import os
from celery import Celery
from flask import Flask, request, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_session import Session
from sqlalchemy.orm.attributes import QueryableAttribute
from flask_uploads import UploadSet, configure_uploads, TEXT, DATA
from config import Config
import sys

app = Flask(__name__)
@app.before_request
def enforce_https():
    if request.headers.get('X-Forwarded-Proto') == 'http':
        return redirect(request.url.replace('http://', 'https://'))


environment_configuration = os.environ['CONFIGURATION_SETUP']
app.config.from_object(environment_configuration)
app.config['SESSION_TYPE'] = 'sqlalchemy'
app.config['SESSION_SQLALCHEMY_TABLE'] = 'session_table'
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'],
                          backend=app.config['CELERY_RESULT_BACKEND'],
                          task_serializer='json')
files = UploadSet('files', TEXT + DATA)
configure_uploads(app, files)
print(f"Environment: {app.config['ENV']}")
print(f"Celery: {app.config['CELERY_BROKER_URL']}")
print(f"Debug: {app.config['DEBUG']}")
print(f"Secret key: {app.config['SECRET_KEY']}")

# connect database
db = SQLAlchemy(app)
Migrate(app,db)

# configure login
login_manager = LoginManager()
login_manager.init_app(app)

# set view when users need to login.
login_manager.login_view = "users.login"
mail = Mail(app)

Session(app)

# *****************************************************************************
# Blueprint Configuration: enable Blueprint to organize modular code
# *****************************************************************************
from hsxc.controllers.core.views import core
from hsxc.controllers.db_admin.views import db_admin
from hsxc.controllers.users.views import users
from hsxc.controllers.races.views import races
from hsxc.controllers.race_setup.views import race_setup
from hsxc.controllers.race_upload.views import race_upload
from hsxc.controllers.errors.handlers import errors

app.register_blueprint(core)
app.register_blueprint(db_admin)
app.register_blueprint(users)
app.register_blueprint(races)
app.register_blueprint(race_setup)
app.register_blueprint(race_upload)
app.register_blueprint(errors)
