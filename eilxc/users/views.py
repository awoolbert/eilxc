from flask import render_template, url_for, flash, redirect, request, Blueprint
from flask_login import login_user, current_user, logout_user, login_required
from eilxc import db, mail
from werkzeug.security import generate_password_hash,check_password_hash
from eilxc.models import (User, League, School, Runner, Team, Course,
                          Race, Result, Participant, Location)
from eilxc.users.forms import (RegistrationForm, LoginForm, UpdateUserForm,
                               RequestResetForm, ResetPasswordForm)
from eilxc.helpers import *
from flask_mail import Message
from sqlalchemy import collate, update
import csv, datetime
from datetime import datetime

users = Blueprint('users', __name__)


@users.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    # limit this route to administrators
    if not current_user.is_administrator():
        return redirect(url_for('core.index'))
    form = RegistrationForm()

    # get full list of schools and alphabetize
    schools = School.query.all()
    schools = sorted(schools, key=lambda s: s.long_name)

    if form.validate_on_submit():
        school_id = int(form.school.data)
        if school_id != 0:
            school = School.query.get(school_id)
        user = User(first_name = form.first_name.data,
                    last_name = form.last_name.data,
                    email=form.email.data,
                    password=form.password.data)

        # add newly created user
        db.session.add(user)
        db.session.commit()

        # affiliate user with school if one was selected
        if school_id != 0:
            school.coaches.append(user)
            db.session.commit()

        #
        flash(f'Account successfully created for {form.email.data}', 'success')
        send_welcome_email(user)
        flash(f'An email has been sent to {form.email.data} with instructions to set the password', 'info')
        return redirect(url_for('users.home'))

    return render_template('register.html', form=form, schools=schools)


@users.route('/userlist', methods=['GET'])
@login_required
def user_list():
    if not current_user.is_administrator():
        return redirect(url_for('core.index'))

    users = User.query.all()
    users = sorted(users, key=lambda u: '0' if len(u.schools_coached) != 1
                                            else u.schools_coached[0].long_name)

    return render_template('users.html', users=users)


@users.route('/home', methods=['GET'])
@login_required
def home():
    cu_id = current_user.id
    data = {
        cat: (Race.query.filter_by(user_id=cu_id,status=cat)
                        # .order_by(Race.group_id.desc(), Race.name)
                        .all())
        for cat in ['new', 'setup', 'bib', 'ready', 'active', 'complete']
    }

    for cat in data:
        data[cat] = sorted(data[cat], key=lambda r: r.display_name())
        data[cat] = sorted(data[cat], key=lambda r: r.reverse_date(),
                           reverse=True)

    return render_template('home.html', data=data)


@users.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('core.index'))

    form = LoginForm()

    if form.validate_on_submit():
        # Grab the user from our User Models table
        user = User.query.filter_by(email=form.email.data).first()

        # https://stackoverflow.com/questions/2209755/python-operation-vs-is-not
        if user is not None:
            if user.check_password(form.password.data):
                #Log in the user
                login_user(user, remember=form.remember.data)
                print(f"{user.first_name} {user.last_name} has logged in")

                # If a user was trying to visit a page that requires a login
                # flask saves that URL as 'next'.
                next = request.args.get('next')

                # So let's now check if that next exists, otherwise we'll go to
                # the welcome page.
                if next == None or not next[0]=='/':
                    next = url_for('core.index')

                flash(f'{user.display_name()} successfully logged in.', 'success')
                return redirect(next)
            else:
                flash('Login Unsuccessful.  Please check email and password', 'danger')
        else:
            flash('Login Unsuccessful.  Please check email and password', 'danger')


    return render_template('login.html', form=form)


@users.route("/logout")
def logout():
    print(f"{current_user.display_name()} is now logged out")
    flash(f'{current_user.display_name()} successfully logged out.', 'success')
    logout_user()
    return redirect(url_for('core.index'))


def send_reset_email(user):
    print('starting send_reset_email')
    token = user.get_reset_token()
    print('got token')
    msg = Message('Password Reset RequestC',
                  sender=('New England Prep XC',
                            'neprepxc@gmail.com'),
                  recipients=[user.email])
    msg.body = f'''Visit the following link to reset your password:

{url_for('users.reset_token', token=token, _external=True)}

If you did not make this request then simply ignore this email and no changes will be made
    '''
    mail.send(msg)


def send_welcome_email(user):
    token = user.get_reset_token()
    msg = Message('Welcome to NE Prep XC',
                  sender = ('New England Prep XC',
                            'neprepxc@gmail.com'),
                  recipients=[user.email])
    msg.body = f'''Welcome to New England Prep Cross-Country Race manager!

Please visit the following link to set your password:

{url_for('users.set_token', token=token, _external=True)}

    '''
    mail.send(msg)


@users.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('core.index'))
    form = RequestResetForm()
    if form.validate_on_submit():
        print('-----------------------------------------------')
        print('received valid form')
        user = User.query.filter_by(email=form.email.data).first()
        print(f'found {user}, sending email')
        send_reset_email(user)
        print('email sent')
        flash('An email has been sent with instructions to reset your password',
              'info')
        return redirect(url_for('users.login'))

    return render_template('reset_request.html', form=form)


@users.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('core.index'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('users.reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.password_hash = generate_password_hash(form.password.data)
        db.session.commit()
        flash(f'The password for {user.email} has been updated', 'success')
        return redirect(url_for('users.login'))

    return render_template('reset_token.html', form=form)


@users.route("/set_password/<token>", methods=['GET', 'POST'])
def set_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('core.index'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('users.set_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.password_hash = generate_password_hash(form.password.data)
        db.session.commit()
        flash(f'The password for {user.email} has been set. Please login using this password', 'success')
        return redirect(url_for('users.login'))

    return render_template('set_token.html', form=form)


@users.route("/schools")
def schools():
    if not current_user.is_administrator():
        return redirect(url_for('core.index'))

    school_list = School.query.all()
    school_list = sorted(
        school_list, key=lambda s: (s.league.short_name, s.long_name)
    )

    return render_template('schools.html', school_list=school_list)


@users.route("/courses")
def courses():
    if not current_user.is_administrator():
        return redirect(url_for('core.index'))

    course_list = Course.query.all()
    return render_template('courses.html', course_list=course_list)


@users.route("/runners")
def runners():
    if not current_user.is_administrator():
        return redirect(url_for('core.index'))

    runners = Runner.query.all()

    runners = sorted(
        runners, key=lambda r: (r.school_name(), r.gender_code(), r.seed_time)
    )

    return render_template('runners.html', runners=runners)


@users.route("/current_runners")
def current_runners():
    if not current_user.is_administrator():
        return redirect(url_for('core.index'))

    year = datetime.today().year
    runners = Runner.query.all()
    runners = [r for r in runners if r.grad_year > year]

    runners = sorted(
        runners, key=lambda r: (r.school_name(), r.gender_code(), r.seed_time)
    )

    return render_template('runners.html', runners=runners)


@users.route("/temporary", methods=['GET', 'POST'])
def temporary():
    return render_template('index.html')
