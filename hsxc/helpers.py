# external imports
from datetime import datetime
from flask import request, url_for
import math
import os
import re
from datetime import datetime
from dateutil import parser
from typing import Optional

# hsxc imports
from hsxc import db,login_manager, app

today = datetime.today()
CUR_YEAR = today.year - 1 if today.month < 8 else today.year
APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(APP_DIR)

def timify(time_in_thousandths, decimals=0) -> str:
    """
    Convert miliseconds to standard MM:SS.ss format.

    Return: string representing the time
    """
    mins = math.floor(time_in_thousandths / 1000 / 60)
    secs = math.floor(time_in_thousandths / 1000 - mins * 60)
    ths = time_in_thousandths - mins * 60 * 1000 - secs * 1000
    frac_secs = math.floor(ths / (10 ** (3-decimals)))
    frac_secs = f".{frac_secs}" if decimals > 0 else ""
    return f"{mins}:{secs:02d}" + frac_secs

def redirect_url(default='index') -> str:
    return request.args.get('next') or request.referrer or url_for(default)

def get_resource_as_string(name, charset='utf-8') -> str:
    with app.open_resource(name) as f:
        return f.read().decode(charset)

def time_str_to_ms(time_str: str) -> int:
    """Converts a time string to milliseconds"""
    if time_str == 'DNF' or time_str == 'DQ':
        return None
    else:
        mins, secs = time_str.split(':')
        return int(int(mins) * 60 * 1000 + float(secs) * 1000)

def date_in_string(input_string) -> Optional[datetime]:
    """Finds a date in a string and returns it as a datetime object (or None)"""

    # Define possible date patterns
    patterns = [
        r'\b(?:\d{1,2}[-/.\s])(?:\d{1,2}[-/.\s])\d{2,4}\b',
        r'\b(?:\d{1,2}\s)?(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|'
        r'May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|'
        r'Nov(?:ember)?|Dec(?:ember)?)\s(?:\d{1,2},\s)?\d{4}\b'
    ]
    
    # Iterate through patterns and search for matches
    for pattern in patterns:
        match = re.search(pattern, input_string)
        if match:
            date_str = match.group()
            return parser.parse(date_str, fuzzy=True)

    # Return None if no matches are found
    return None

app.jinja_env.globals['get_resource_as_string'] = get_resource_as_string
