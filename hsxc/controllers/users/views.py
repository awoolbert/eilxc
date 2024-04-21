from flask import Blueprint, render_template, url_for, flash, redirect, request 
from flask_login import login_user, logout_user, login_required, current_user
from premailer import transform
from hsxc import db, mail
from werkzeug.security import generate_password_hash
from hsxc.models import User, League, School, Runner, Team, Course, Race, Location
from hsxc.controllers.users.forms import RegistrationForm, LoginForm
from hsxc.controllers.users.forms import RequestResetForm, ResetPasswordForm
from hsxc.helpers import CUR_YEAR
from flask_mail import Message
from typing import List

users = Blueprint('users', __name__)


@users.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('core.index'))

    form = LoginForm()

    if not form.validate_on_submit():
        return render_template('login.html', form=form)

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
            if next == None or not next[0]=='/':
                next = url_for('core.index')

            ftxt = f'Welcome back, {user.display_name()}!'
            flash(ftxt, 'success')
            return redirect(next)
        else:
            ftxt = 'Login Unsuccessful. Please check email and password'
            flash(ftxt, 'danger')
    else:
        ftxt = 'Login Unsuccessful. Please check email and password'
        flash(ftxt, 'danger')


@users.route("/logout")
def logout():
    print(f"{current_user.display_name()} is now logged out")
    flash(f'{current_user.display_name()} successfully logged out.', 'success')
    logout_user()
    return redirect(url_for('core.index'))


@users.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    # limit this route to administrators
    if not current_user.is_administrator():
        return redirect(url_for('core.index'))
    form = RegistrationForm()

    # get full list of schools and alphabetize
    schools: List[School] = School.query.all()
    schools = sorted(schools, key=lambda s: s.long_name)

    # if this is the original request, render the template
    if not form.validate_on_submit():
        return render_template('register.html', form=form, schools=schools)

    school_id = int(form.school.data)
    if school_id != 0:
        school = School.query.get(school_id)
    user = User(
        first_name=form.first_name.data,
        last_name=form.last_name.data,
        email=form.email.data,
        password=form.password.data
    )

    # add newly created user
    db.session.add(user)
    db.session.commit()

    # affiliate user with school if one was selected
    if school_id != 0:
        school.coaches.append(user)
        db.session.commit()
    flash(f'Account successfully created for {form.email.data}', 'success')

    send_welcome_email(user)
    flash_txt = (
        f'An email has been sent to {form.email.data} with instructions '
        f'to set the password'
    )
    flash(flash_txt, 'info')

    return redirect(url_for('users.home'))

def send_welcome_email(user: User):
    token = user.get_reset_token()
    school: School = user.schools_coached[0]
    msg = Message(
        subject = 'Welcome to NE Prep XC',
        sender = ('New England Prep XC', 'neprepxc@gmail.com'),
        recipients = [user.email]
    )

    raw_html = render_template(
        'coach_welcome_email.html',
        user = user,
        reset_link = url_for('users.set_token', token=token, _external=True),
        school = school
    )

    # Apply premailer transformations to fix formatting and send message
    msg.html = transform(raw_html)

    # send message
    mail.send(msg)


@users.route('/user_list', methods=['GET'])
# @login_required
def user_list():
    if not current_user.is_administrator():
        return redirect(url_for('core.index'))

    def sort_by_school_if_only_one(user: User) -> str:
        if len(user.schools_coached) == 1:
            return user.schools_coached[0].long_name
        else:
            return user.last_name
    users = User.query.all()
    users = sorted(users, key=sort_by_school_if_only_one, reverse=True)

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





def send_reset_email(user):
    print('starting send_reset_email')
    token = user.get_reset_token()
    print('got token')
    msg = Message('Password Reset Request',
                  sender=('New England Prep XC',
                            'neprepxc@gmail.com'),
                  recipients=[user.email])
    msg.body = f'''Visit the following link to reset your password:

{url_for('users.reset_token', token=token, _external=True)}

If you did not make this request then simply ignore this email and no changes will be made
    '''
    mail.send(msg)


@users.route("/<int:user_id>/delete_user", methods=['GET', 'POST'])
def delete_user(user_id: int):
    # limit this route to administrators
    if not current_user.is_administrator():
        return redirect(url_for('core.index'))

    user: User = User.query.get(user_id)
    if user is None:
        flash(f'User with id {user_id} not found', 'danger')
        return redirect(url_for('users.user_list'))
    
    # clear schools coached
    user.schools_coached = []
    db.session.commit()

    # clear leagues_managed
    user.leagues_managed = []
    db.session.commit()

    # delete user
    db.session.delete(user)
    db.session.commit()

    return redirect(url_for('core.index'))


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


# @users.route("/courses")
# def courses():
#     if not current_user.is_administrator():
#         return redirect(url_for('core.index'))

#     course_list = Course.query.all()
#     return render_template('courses.html', course_list=course_list)


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

    isl_schools: List[School] = (
        League.query.filter_by(short_name='ISL').first().schools
    )
    cur_teams: List[Team] = [
        school.get_team(CUR_YEAR, gender) 
        for school in isl_schools 
        for gender in ['boys', 'girls']
    ]
    cur_teams = [t for t in cur_teams if t is not None]
    runners = [r for team in cur_teams for r in team.runners]

    runners = sorted(
        runners, key=lambda r: (r.school_name(), r.gender_code(), r.seed_time)
    )

    return render_template('runners.html', runners=runners)


@users.route("/temporary", methods=['GET', 'POST'])
def temporary():
    if not current_user.is_administrator():
        return redirect(url_for('core.index'))

    d3g: Race = Race.query.get(266)
    d3b: Race = Race.query.get(267)

    pairs = []
    for res in d3g.results:
        runner: Runner = res.runner
        other = [r for r in runner.results if r.race.date.year == 2019 and r != res]
        if other:
            other = other[0]
            pct_inc = int((res.adj_time()/other.adj_time()-1)*1000)
            pairs.append((pct_inc, res.adj_time_f(), other.adj_time_f()))

    for res in d3b.results:
        runner: Runner = res.runner
        other = [r for r in runner.results if r.race.date.year == 2019 and r != res]
        if other:
            other = other[0]
            pct_inc = int((res.adj_time()/other.adj_time()-1)*1000)
            pairs.append((pct_inc, res.adj_time_f(), other.adj_time_f()))

    pairs = sorted(pairs, key=lambda p: p[0])
    for pair in pairs:
        print(pair)



    return redirect(url_for('core.index'))