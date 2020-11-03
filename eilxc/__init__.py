# Configuration

import os
from celery import Celery
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from sqlalchemy.orm.attributes import QueryableAttribute
from config import Config

app = Flask(__name__)
environment_configuration = os.environ['CONFIGURATION_SETUP']
app.config.from_object(environment_configuration)
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'],
                          backend=app.config['CELERY_RESULT_BACKEND'],
                          task_serializer='json')
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

# *****************************************************************************
# Blueprint Configuration: enable Blueprint to organize modular code
# *****************************************************************************
from eilxc.core.views import core
from eilxc.users.views import users
from eilxc.races.views import races
from eilxc.setup.views import setup
from eilxc.errors.handlers import errors

app.register_blueprint(core)
app.register_blueprint(users)
app.register_blueprint(races)
app.register_blueprint(setup)
app.register_blueprint(errors)
