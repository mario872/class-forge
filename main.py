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
from datetime import datetime, timedelta
from werkzeug.routing import BaseConverter
import ics
import pytz

from functions import *

#################################################################################################
# Variables Setup

headless = True
in_docker = os.environ.get('IN_DOCKER', False)  # Detects if we are testing, or in a production docker container
override = False  # Whether to override to test the production version
skip_login_check = os.environ.get('DISABLE_SECURITY', False) # Skip checking login for offline testing

auto_off = 600 # Whether to automatically turn off the server after a certain period of time, currently 10 minutes (600)

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

# A template user to use, when the user is not signed in, used on login screen, tos, etc.
fake_user = {'username': 'your.name',
             'password': 'your_password',
             'state': 'nsw',
             'base_ur': 'caringbahhs',
             'photo_path': 'static/Rick Astley.jpg'}

app = Flask(__name__)

################################################################################################
# Functions


class RegexConverter(BaseConverter):  # Unused regex converter for url routing
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]


app.url_map.converters['regex'] = RegexConverter

#################################################################################################
# Routes for server


@app.route('/')
def one():
    if cookies_present(request):
        return redirect('/dashboard')
    else:
        return redirect('/login')


@app.route('/login')
def login():
    try:
        message = request.args.get('message')
    except KeyError:
        message = ''

    return render_template('login.jinja', user=fake_user, message=message, request=request, weather=get_weather())


@app.route('/login/finish', methods=['POST'])
def finish_login():
    try:
        data = request.form

        if data.get('privacyPolicyCheckbox') and data.get('tosCheckbox'):
            pass
        else:
            return redirect('/login?message=Please+accept+the+privacy+policy+and+the+terms+of+service.')

        os.makedirs('users/' + data['username'], exist_ok=True)

        private_key = RSA.generate(2048)
        public_key = private_key.publickey()
        encrypter = PKCS1_OAEP.new(key=public_key)

        username = data['username'].lower().encode(encoding='latin')
        username = encrypter.encrypt(username).decode(encoding='latin')
        password = data['password'].encode(encoding='latin')
        password = encrypter.encrypt(password).decode(encoding='latin')
        base_url = data['base_url'].lower().encode(encoding='latin')
        base_url = encrypter.encrypt(base_url).decode(encoding='latin')
        state = data['state'].encode(encoding='latin')
        state = encrypter.encrypt(state).decode(encoding='latin')
        theme = encrypter.encrypt('dark'.encode(encoding='latin')).decode(encoding='latin')

        user = {'username': data['username'],
                'password': data['password'],
                'base_url': data['base_url'],
                'state': data['state'],
                'headless': headless
                }

        encrypted_user = {'username': username,
                          'password': password,
                          'base_url': base_url,
                          'state': state,
                          'theme': theme,
                          'photo_path': f'user/{data["username"]}"/photo.png'
                        }

        if sentralify(user, check_login=True):
            with open(f'users/{user["username"]}/config.json', 'w') as user_config:
                json.dump(encrypted_user, user_config)

            secret_key = os.urandom(24)

            with open('./users/' + data['username'] + '/secret_key', 'wb') as secret_key_file:
                secret_key_file.write(secret_key)

            response = make_response(render_template('login_complete.jinja', user=fake_user, request=request, weather=get_weather()))
            response.set_cookie('secret_key', base64.b64encode(secret_key).decode('utf-8'))
            response.set_cookie('username', data['username'])
            response.set_cookie('private_key', private_key.export_key().decode())

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
def home():
    if not cookies_present(request):
        return redirect('/login')

    try:
        user = load_user_config(request)
    except ValueError:
        return redirect('/login')

    if not user:
        return redirect('/login')

    try:
        data = load_user_data(user, request.cookies.get('private_key'), request.cookies.get('secret_key'))
    except AttributeError:
        return redirect('/login')

    three_day_timetable = []
    if not datetime.now().weekday() in [0, 4, 5, 6]:
        possible_days = [datetime.now() - timedelta(days=1), datetime.now(), datetime.now() + timedelta(days=1)]
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
        tmp = timers[user['username']]
        message = None
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

    return render_template('index.jinja', user=user, data=data, message=message, tdt=three_day_timetable, today_calendar=events_today, request=request, weather=get_weather(), periods_left=list_periods_left)


@app.route('/timetable')
def timetable():
    if not cookies_present(request):
        return redirect('/login')

    try:
        user = load_user_config(request)
    except ValueError:
        return redirect('/login')

    if not user:
        return redirect('/login')

    data = load_user_data(user, request.cookies.get('private_key'), request.cookies.get('secret_key'))

    return render_template('timetable.jinja', user=user, data=data, request=request, weather=get_weather())


@app.route('/calendar')
def calendar():
    if not cookies_present(request):
        return redirect('/login')

    try:
        user = load_user_config(request)
    except ValueError:
        return redirect('/login')

    if not user:
        return redirect('/login')

    data = load_user_data(user, request.cookies.get('private_key'), request.cookies.get('secret_key'))

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

    return render_template('calendar.jinja', user=user, data=data, weeks=weeks, request=request, weather=get_weather())

1
@app.route('/details')
def details():
    if not cookies_present(request):
        return redirect('/login')

    try:
        user = load_user_config(request)
    except ValueError:
        return redirect('/login')

    if not user:
        return redirect('/login')

    data = load_user_data(user, request.cookies.get('private_key'), request.cookies.get('secret_key'))

    return render_template('details.jinja', user=user, request=request, data=data, weather=get_weather())


@app.route('/reload')
def reload():
    if not cookies_present(request):
        return redirect('/login')

    try:
        user = load_user_config(request)
    except ValueError:
        return redirect('/login')

    repeat_reload(username=user['username'], private_key=request.cookies.get('private_key'), secret_key=request.cookies.get('secret_key'), http_request=request)

    return redirect('/dashboard')


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
def search():
    search_text = request.args.get('text')
    results = []

    if search_text == '':
        return []

    if not cookies_present(request):
        return []

    try:
        user = load_user_config(request)
    except ValueError:
        return []

    if not user:
        return []

    data = load_user_data(user, request.cookies.get('private_key'), request.cookies.get('secret_key'))

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

#################################################################################################
# Main Program / Loop


if __name__ == '__main__':
    if in_docker:
        app.run('0.0.0.0', 5000, use_evalex=False)
    else:
        app.run('0.0.0.0', 5000, debug=True, use_evalex=False)