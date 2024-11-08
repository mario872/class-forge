"""
Copyright (C) 2024  James Glynn

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see https://www.gnu.org/licenses/gpl-3.0.html.
"""

#################################################################################################
# Imports

from flask import *
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import ics
import pytz
import zlib
from functools import wraps

from functions import *

#################################################################################################
# Variables Setup

users = []  # THIS IS THE VARIABLE FOR ALL USERS SAVED IN CODE, SO NOT AVAILABLE UPON RESTART

headless = False
in_docker = os.environ.get('IN_DOCKER', False)  # Detects if we are testing, or in a production docker container
override = False  # Whether to override to test the production version
skip_login_check = os.environ.get('DISABLE_SECURITY', False) # Skip checking login for offline testing

auto_off = 600  # Whether to automatically turn off the server after a certain period of time, currently 10 minutes (600)

if in_docker or override:
    auto_off = None
    headless = True

if auto_off != None:
    auto_off_timer = threading.Timer(auto_off, lambda: os._exit(1))
    auto_off_timer.daemon = True
    auto_off_timer.start()

if override:
    in_docker = True

timezone_hours_ahead = 10

login_manager = LoginManager()

# A template user to use, when the user is not signed in, used on login screen, tos, etc.
fake_user = {'username': 'your.name',
             'password': 'your_password',
             'state': 'nsw',
             'base_url': 'caringbahhs',
             'photo_path': 'static/Rick Astley.jpg'}

app = Flask(__name__)

app.secret_key = b'5e3cb545c705a0ceb95ac8dcf1d63d5df60cdbaccdf73a6f4cd44a73a5a7528e'
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=14)
app.config['SESSION_COOKIE_SECURE'] = True

login_manager.init_app(app)

################################################################################################
# Classes and Login


class User(UserMixin):
    def __init__(self, username, password, state, base_url):
        self.username = username
        self.password = password
        self.state = state,
        self.base_url = base_url

    def get_id(self):
        return self.username


@login_manager.user_loader
def load_user(user_username):
    for user in users:
        if user['username'] == user_username:
            return User(user_username, user['password'], user['state'], user['base_url'])
    return None


def initial_login_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if current_user.is_authenticated:
            return func(*args, **kwargs)
        else:
            return redirect('/login')
    return decorated_view

#################################################################################################
# Routes for server


@app.route('/')
@initial_login_required
def one():
    return redirect('/dashboard')


@app.route('/login')
def login():
    try:
        message = request.args.get('message')
    except KeyError:
        message = ''

    return render_template('login.jinja', user=fake_user, message=message, weather=get_weather())


@app.route('/login/finish', methods=['POST'])
def finish_login():
    try:
        data = request.form

        if data.get('privacyPolicyCheckbox') and data.get('tosCheckbox'):
            pass
        else:
            return redirect('/login?message=Please+accept+the+privacy+policy+and+the+terms+of+service.')

        username = data['username']
        password = data['password']
        base_url = data['base_url']
        state = data['state']
        remember = data.get('rememberMeCheckbox')

        user = User(username, password, state, base_url)

        user_dict = user_to_dict(user)

        if sentralify(user_dict, check_login=True, timeout=10):
            users.append(user_dict)
            login_user(user, remember=remember)

            with open(f'users/{zlib.adler32(user.username.encode())}.json', 'w') as f:
                f.write('')

            response = make_response(render_template('login_complete.jinja', user=fake_user, weather=get_weather()))

            return response

        else:
            if data.get('privacyPolicyCheckbox') and data.get('tosCheckbox'):
                return redirect('/login?message=Sorry,+those+login+details+are+incorrect')
            else:
                return redirect('/login?message=Sorry,+those+login+details+are+incorrect.\nPlease+accept+the+privacy'
                                '+policy+and+the+terms+of+service.')
    except Exception as r:
        print(r)
        return redirect('/login?message=Sorry,+we+had+an+error+on+our+end,+please+try+signing+in+again.')


@app.route('/dashboard')
@login_required
def home():
    user = current_user

    try:
        data = load_user_data(user)
    except AttributeError:
        return redirect('/login')

    three_day_timetable = []
    if not datetime.now().weekday() in [0, 4, 5, 6]:
        possible_days = [datetime.now(), datetime.now() + timedelta(days=1), datetime.now() + timedelta(days=2)]
    else:
        if datetime.now().weekday() == 0:
            possible_days = [datetime.now() - timedelta(days=3), datetime.now(), datetime.now() + timedelta(days=1)]
        elif datetime.now().weekday() == 4:
            possible_days = [datetime.now() - timedelta(days=1), datetime.now(), datetime.now() + timedelta(days=3)]
        elif datetime.now().weekday() == 5:
            possible_days = [datetime.now() - timedelta(days=1), datetime.now() + timedelta(days=2), datetime.now() + timedelta(days=3)]
        elif datetime.now().weekday() == 6:
            possible_days = [datetime.now() - timedelta(days=2), datetime.now() + timedelta(days=1), datetime.now() + timedelta(days=2)]

    for day in data['timetable']:
        for pday in possible_days:
            if parse(day['date']).day == pday.day:
                three_day_timetable.append(day)

    try:
        tmp = timers[user.username]
        message = request.args.get('message')
    except KeyError:
        message = 'Automatic reloading is not enabled, please press the fetch timetable button.'

    events_today = []

    today = datetime.now()
    weekend = today.weekday() in [5, 6]

    for event in data['calendar']:
        event_date = parse(event['date'])

        if not weekend:
            if event_date.day == today.day and event_date.month == today.month:
                # Today's events
                format_event(event, event_date)
                events_today.append(event)
        else:
            if today.weekday() == 5:
                if event_date.day == (today + timedelta(days=2)).day and event_date.month == (today + timedelta(days=2)).month:
                    # Weekend events
                    format_event(event, event_date)
                    events_today.append(event)
            elif today.weekday() == 6:
                if event_date.day == (today + timedelta(days=1)).day and event_date.month == (today + timedelta(days=1)).month:
                    # Weekend events
                    format_event(event, event_date)
                    events_today.append(event)

    # Most of the code below is from another GitHub repository I made: https://github.com/mario872/Period-Left-Counter
    ics_timetable = data['ics']
    ics_timetable = ics_timetable.split('\n')

    ics_timetable.pop(1)  # This gets rid of annoying formatting errors in the ICS timetable from Sentral
    ics_timetable.pop(2)

    ics_timetable = '\n'.join(ics_timetable)

    ics_timetable = ics.Calendar(ics_timetable)

    periods = list(ics_timetable.events)
    periods = sorted(periods)

    possible_names = []
    periods_left = {}

    timedatelist = []
    for item in periods:
        if not item.name in possible_names:
            possible_names.append(item.name)
        if (datetime.fromisoformat(str(item.end))+timedelta(hours=timezone_hours_ahead)).replace(tzinfo=None) < datetime.now():
            pass
        else:
            timedatelist.append((datetime.fromisoformat(str(item.end))+timedelta(hours=timezone_hours_ahead)).replace(tzinfo=None))

    timedatelist = sorted(timedatelist)
    for i in range(len(periods) - len(timedatelist), len(periods)):
        for item in possible_names:
            if item == periods[i].name:
                try:
                    periods_left[item] += 1
                except KeyError:
                    periods_left[item] = 1

    list_periods_left = []

    for key in list(periods_left.keys()):
        list_periods_left.append({'name': key, 'periods_left': periods_left[key]})

        return render_template('index.jinja', user=user_to_dict(user), data=data, message=message, tdt=three_day_timetable, today_calendar=events_today, weather=get_weather(), periods_left=list_periods_left)


@app.route('/timetable')
@login_required
def timetable():
    user = current_user

    data = load_user_data(user)

    return render_template('timetable.jinja', user=user_to_dict(user), data=data, weather=get_weather())


@app.route('/calendar')
@login_required
def calendar():
    user = current_user
    data = load_user_data(user)

    # Organise calendar list by date
    data['calendar'] = sorted(data['calendar'], key=lambda x: parse(x['date']))

    # Get number of weeks from calendar list
    total_days = parse(data['calendar'][-1]['date']) - parse(data['calendar'][0]['date'])
    weeks = (total_days.days // 7) + 1  # Day one is a monday, last day is a friday, makes one week less than it
                                        # should be

    # Put each day into its own list
    per_day_calendar = []
    current_day_list = []
    current_day = parse(data['calendar'][0]['date'])

    for x in range(len(data['calendar'])):
        if parse(data['calendar'][x]['date']).day == current_day.day and parse(data['calendar'][x]['date']).month == current_day.month:
            current_day_list.append(data['calendar'][x])

        else:
            per_day_calendar.append(current_day_list)
            current_day_list = [data['calendar'][x]]
            current_day = parse(data['calendar'][x]['date'])

    per_day_calendar.append(current_day_list)

    # Put each week into its own list in data['calendar']
    per_week_calendar = []
    current_week = []  # Current week calendar
    days_in_week = [0, 1, 2, 3, 4]
    last_day_in_week = -1
    for y in range(len(per_day_calendar)):  # Total number of days in per_day_calendar
        # If it is a valid weekday of school, and it is greater than the last recorded day of the week, that means
        # we're still in the same week as before
        if parse(per_day_calendar[y][0]['date']).weekday() in days_in_week and parse(per_day_calendar[y][0]['date']).weekday() > last_day_in_week:
            current_week.append(per_day_calendar[y])
            last_day_in_week = parse(per_day_calendar[y][0]['date']).weekday()
        else:
            per_week_calendar.append(current_week)
            current_week = [per_day_calendar[y]]
            last_day_in_week = parse(per_day_calendar[y][0]['date']).weekday()

    per_week_calendar.append(current_week)

    data['calendar'] = per_week_calendar

    return render_template('calendar.jinja', user=user_to_dict(user), data=data, weeks=weeks, weather=get_weather())


@app.route('/details')
@login_required
def details():
    user = current_user
    data = load_user_data(user)

    return render_template('details.jinja', user=user_to_dict(user), data=data, weather=get_weather())


@app.route('/reload')
@login_required
def reload():
    user = current_user

    repeat_reload(user=user, http_request=request)

    return redirect('/dashboard?message=Warning%20lots%20of%20features%20are%20still%20broken%20and%20may%20not%20be%20fixed%20anytime%20soon')


@app.route('/privacy_policy')
def privacy_policy():
    return render_markdown_page('privacy-policy')


@app.route('/tos')
def tos():
    return render_markdown_page('terms-of-service')


@app.route('/how_it_works')
def how_it_works():
    return render_markdown_page('how-it-works')

#################################################################################################
# API Methods

@app.route('/search')
@login_required
def search():
    user = current_user

    search_text = request.args.get('text')
    results = []

    if search_text == '':
        return []

    if not user:
        return []

    data = load_user_data(user)

    # This duplicates Week A for use in the /search route, if this isn't here,
    # it won't work for if it's the end of the week
    #extra_week = []
    #for day in range(5):
    #    extra_week.append(data['timetable'][day])
    #    extra_week[day]['date'] = (parse(extra_week[day]['date']) + timedelta(days=7)).strftime('%c')

    #print(extra_week)

    #for day in data['timetable']:
    #    data['timetable'].append(day)
    #print(data['timetable'][0]['date'])
    #print(data['timetable'][5]['date'])
    #print(data['timetable'][10]['date'])
    raw_periods = []
    for day in data['timetable']:
        for period in day['periods']:
            period['time'] = datetime(parse(day['date']).year, parse(day['date']).month, parse(day['date']).day,
                                      int(period['start'].split(':')[0]), int(period['start'].split(':')[1]))
            if period['full_name'] != None and period['time'] >= datetime.now():
                raw_periods.append(period)

    for period in raw_periods:
        if search_text.lower() in period['full_name'].lower():
            results.append(f'{period["full_name"]}: {period["time"].strftime("%a %b %-d %H:%M")}')

    #del results
    #del data
    #del extra_week

    return results
"""
@app.route('/reminders/add')
def add_reminder():
    if not cookies_present(request):
        return [{'name': 'Error, no cookies present!', 'due': '2085'}]

    try:
        user = load_user_config(request)
    except ValueError:
        return [{'name': 'Error, no cookies present!', 'due': '2085'}]

    if not user:
        return [{'name': 'Error, no cookies present!', 'due': '2085'}]

    data = load_user_data(user, request.cookies.get('private_key'), request.cookies.get('secret_key'))

    data['reminders'].append({'name': request.args.get('name'), 'due': request.args.get('due')})

    save_user_data(data, request.cookies.get('secret_key'), user['username'])


@app.route('/reminders/get')
def get_reminders():
    if not cookies_present(request):
        return [{'name': 'Error, no cookies present!', 'due': '2085'}]

    try:
        user = load_user_config(request)
    except ValueError:
        return [{'name': 'Error, no cookies present!', 'due': '2085'}]

    if not user:
        return [{'name': 'Error, no cookies present!', 'due': '2085'}]

    data = load_user_data(user, request.cookies.get('private_key'), request.cookies.get('secret_key'))
"""
#################################################################################################
# Main Program / Loop


if __name__ == '__main__':
    if in_docker:
        app.run('0.0.0.0', 5000, use_evalex=False)
    else:
        app.run('0.0.0.0', 5000, debug=True, use_evalex=False)