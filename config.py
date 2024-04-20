import os

class Config(object):
    DEBUG = False
    TESTING = False
    UPLOADED_FILES_DEST = 'uploads'
    MAIL_SERVER = 'smtp.googlemail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ['EIL_GMAIL_USERNAME']
    MAIL_PASSWORD = os.environ['EIL_GMAIL_PASSWORD']
    SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    @staticmethod
    def init_app(app):
        pass

class ProductionConfig(Config):
    SECRET_KEY=os.environ['EIL_PROD_SECRET_KEY']

class DevelopmentConfig(Config):
    ENV="development"
    SECRET_KEY=os.environ['EIL_DEV_SECRET_KEY']
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
