from eilxc import db,login_manager, app
from datetime import datetime
from werkzeug.security import generate_password_hash,check_password_hash
from flask_login import UserMixin
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from operator import itemgetter
import math
import requests


def timify(time_in_thousandths, decimals=0):
    """
    Convert miliseconds to standard MM:SS.ss format.

    Return: string representing the time
    """
    mins = math.floor(time_in_thousandths / 1000 / 60)
    fmins = f"{mins}"
    secs = math.floor(time_in_thousandths / 1000 - mins * 60)
    fsecs = f"{secs}" if secs >= 10 else f"0{secs}"
    ths = time_in_thousandths - mins * 60 * 1000 - secs * 1000
    pwr = 3 - decimals
    frac_secs = math.floor(ths / (10 ** pwr))
    ffrac_secs = f"{frac_secs}"
    return f"{fmins}:{fsecs}{'.' if decimals > 0 else ''}{ffrac_secs if decimals > 0 else ''}"


def redirect_url(default='index'):
    return request.args.get('next') or request.referrer or url_for(default)


def reverse_runners(runners):
    """
    Reverses a list of runners

    Return: reversed list
    """
    retlist = []
    rlen = len(runners)
    for i in range(rlen):
        retlist.append(runners[rlen-1-i])
    return retlist


def get_resource_as_string(name, charset='utf-8'):
    with app.open_resource(name) as f:
        return f.read().decode(charset)

app.jinja_env.globals['get_resource_as_string'] = get_resource_as_string
