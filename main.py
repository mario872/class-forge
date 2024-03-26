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

from flask import *
from sentralify import sentralify
import json
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES
import os
import random
import markdown
from base64 import b64decode, b64encode
import threading
from dateutil.parser import parse
from datetime import datetime, timedelta
import ast
from werkzeug.routing import BaseConverter

#################################################################################################
# Variables Setup

headless = True
in_docker = os.environ.get('IN_DOCKER', False) # Detects if we are testing, or in a production docker container
override = False # Whether to override to test production version

auto_off = 600.0 # Whether to automatically turn off the server after a certain period of time, currently 10 minutes

if in_docker or override:
    auto_off = None
    headless = True

if auto_off != None:
    auto_off_timer = threading.Timer(auto_off, lambda: os._exit(1))
    auto_off_timer.daemon = True
    auto_off_timer.start()
    
if override:
    in_docker = True

# A template user to use, when the user is not signed in, used on login screen, tos, etc.
fake_user = {'username': 'your.name',
             'password': 'your_password',
             'state': 'nsw',
             'base_ur': 'caringbahhs',
             'photo_path': 'static/Rick Astley.jpg'}

timers = {} # Used to store all of the timers used to automatically scrape Sentral

app = Flask(__name__)

################################################################################################
# Functions

# Unused regex converter for url routing
class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]

app.url_map.converters['regex'] = RegexConverter

def decrypt(in_, private_key, test=None):
    """
    Used to decrypt every item in a dict, or a str

    Args:
        in_ (dict or str): The encrypted dict / str to be decrypted
        private_key str: The private key sued to decrypt the encrypted dict or str
        test (str, optional): A test str to be decrypted. Defaults to None.

    Returns:
        dict or str: A dict or str, with the decrypted values in it
    """
    
    try:
        private_key = RSA.import_key(private_key.encode())
    except AttributeError:
        private_key = RSA.import_key(private_key)
    
    decrypter = PKCS1_OAEP.new(key=private_key)
    
    if test != None:
        try:
            print(decrypter.decrypt(test.encode(encoding='latin')))
        except ValueError:
            return False
    
    if type(in_) == dict:
        out = {}
        keys = list(in_.keys())
        for key in keys:
            if key != 'photo_path':
                if key != 'secret_key':
                    out[key] = decrypter.decrypt(in_[key].encode(encoding='latin')).decode(encoding='latin')
                else:
                    out[key] = decrypter.decrypt(in_[key].encode(encoding='latin'))
            else:
                out[key] = in_[key]
                
    elif type(in_) == str:
        out = decrypter.decrypt(in_.encode(encoding='latin')).decode(encoding='latin')
        
    #elif type(in_) == bytes:
    #    print(in_)
    #    out = decrypter.decrypt(in_)
    #    out = base64.b64decode(out)
    
    return out

def cookies_present(request):
    """
    A function to check if cookies are present in the user's browser session.

    Args:
        request: The request given by the app routing function, contains cookies set in it

    Returns:
        bool: Whether cookies are set or not.
    """
    
    username = request.cookies.get('username')
    password = request.cookies.get('private_key')
    secret_key = request.cookies.get('secret_key')
    
    if username != None or password != None or secret_key!= None:
        try:
            open(f'users/{username}/config.json', 'r').close()
        except FileNotFoundError:
            print('Error: Cookies were present, but there was no user config found!')
            return False
        
        return True
    
    else:
        return False
    
def load_user_config(request, username=None, private_key=None):
    """
    A function that loads the user config using cookies stored in browser, or from credentials passed to the function

    Args:
        request: The request given by the app routing function, contains cookies set in it
        username (str, optional): Username for if the cookies are not yet set in the browser. Defaults to None.
        private_key (str, optional): Private key for if the cookies are not yet set in the browser. Defaults to None.

    Returns:
        dict: A dict containing the decrypted user config
    """
    if request != None:
        with open(f'users/{request.cookies.get("username")}/config.json', 'r') as user_config_file:
            user = json.load(user_config_file)
            
        user = decrypt(user, request.cookies.get('private_key'))
    else:
        with open(f'users/{username}/config.json', 'r') as user_config_file:
            user = json.load(user_config_file)
            
        user = decrypt(user, private_key, test=user['username'])
        
    if user == False:
            return False
    
    try:
        open(user['photo_path'], 'r').close()
    except FileNotFoundError:
        user['photo_path'] = 'static/unsplash/' + random.choice(os.listdir('static/unsplash/'))
    
    return user

def load_user_data(user: dict, private_key: str, secret_key: str):
    """
    A function that loads the user data using the data in the user dict, and the private key, and secret key

    Args:
        user (dict): The user dict decrypted and returned in the load_user_config function
        private_key (str): The private_key in the browser cookies, but passed directly to this function
        secret_key (str): The secret key for symmetrical encryption in the user data

    Returns:
        dict: The user data, eg the timetable, notices, calendar etc.
    """
    
    try:
        open(f'users/{user["username"]}/data.json', 'rb').close()
    except FileNotFoundError:
        repeat_reload(user['username'], private_key, secret_key)
    
    do_not_encode = False
    if secret_key == None:
        secret_key = request.cookies.get('secret_key')
        if secret_key == None:
            try:
                with open(f'users/{user["username"]}/secret_key', 'rb') as secret_key_file:
                    secret_key = secret_key_file.read()
                    if not in_docker:
                        print('Secret Key is ' + str(secret_key))
                    do_not_encode = True
            except FileNotFoundError:
                print('Error, I don\'t know what to do here! In load_user_data.')
    try:
        os.remove(f'users/{user["username"]}/secret_key')
    except FileNotFoundError:
        pass
    
    with open(f'users/{user["username"]}/data.json', 'r') as data_json:
        if do_not_encode:
            cipher = AES.new(secret_key, AES.MODE_ECB)
        else:
            cipher = AES.new(secret_key.encode('latin1'), AES.MODE_ECB)
        padded_data = b64decode(data_json.read())
        padded_data = cipher.decrypt(padded_data)
        padded_data = padded_data.decode('ascii')
        data = padded_data.rstrip('~')
        data = ast.literal_eval(data)
        return data

def repeat_reload(username: str, private_key: str, secret_key, refresh_time=1800, request=None):
    """
    A function that sets a timer to get new data from Sentral

    Args:
        username (str): The user's username
        private_key (str): The usrer's private key
        secret_key (_type_): The user's secret key
        refresh_time (int, optional): The amount of time beween refreshes, in seconds. Defaults to 1800.
        request (_type_, optional): The request from the browser can be used if desired, to grab the private key and secret key. Defaults to None.
    """
    
    global timers
    global add_cookie
    
    user = load_user_config(None, username=username, private_key=private_key)
    
    user['headless'] = headless
    
    data = sentralify(user)
    
    for notice in data['notices']:
        try:
            notice['content'] = markdown.markdown((notice['content']))
        except KeyError:
            pass
    
    do_not_encode = False
    if secret_key == None:
        secret_key = request.cookies.get('secret_key')
        if secret_key == None:
            try:
                with open(f'users/{user["username"]}/secret_key', 'rb') as secret_key_file:
                    secret_key = secret_key_file.read()
                    do_not_encode = True
                    if not in_docker:
                        print('Secret Key is'+ str(secret_key) + 'In repeat_reload.')
            except FileNotFoundError:
                print('Error, I don\'t know what to do here!')
    
    try:
        os.remove(f'users/{user["username"]}/secret_key')
    except FileNotFoundError:
        pass
    
    with open(f'users/{user["username"]}/data.json', 'wb') as data_json:
        padded_data = f'{data}' + ('~' * ((16-len(f'{data}')) % 16))
        if do_not_encode:
            cipher = AES.new(secret_key, AES.MODE_ECB)
        else:
            cipher = AES.new(secret_key.encode('latin1'), AES.MODE_ECB)
        padded_data = padded_data.encode('ascii')
        padded_data = cipher.encrypt(padded_data)
        padded_data = b64encode(padded_data)
        data_json.write(padded_data)
        #json.dump(data, data_json)
    
    try:
        timers[username].cancel()
    except KeyError:
        pass
    
    #1800.0 for 30 minutes, 600 for 10 minutes
    timers[username] = threading.Timer(refresh_time, lambda username=username, private_key=private_key, secret_key=secret_key: repeat_reload(username, private_key, secret_key))
    timers[username].daemon = True # Seting it to daemon kills the thread if the main thread exits
    timers[username].start()

def format_event(event, event_date):
    """
    Converts the full timestring given by Sentralify on events to a human readable format

    Args:
        event dict: The event dict to change
        event_date datetime.datetime: The date of the event
    """
    if event['start'] is not None:
        event['start'] = event['start'].strftime('%H:%M')
    if event['end'] is not None:
        event['end'] = event['end'].strftime('%H:%M')
    event['date'] = event_date.strftime('%d/%m/%Y')
    # If I ever want to add title cleaning then I can test the below comment it out
    # event['title'] = event['title'].replace('Events: ', '')
    
def render_markdown_page(markdown_name: str):
    """
    Takes the name of a markdown file, and returns a template to render on the page

    Args:
        markdown_name str: The name of the markdown file, without .md suffix
    """
    
    mrkdown = markdown.markdown(open(f'./static/markdown/{markdown_name}.md', 'r').read())
    # The below is a bit of a weird mess, but I'll try to explain it
    # The 4 opening braces and 4 closing braces, even though Jinja2 reuires only two, is because python evaluates {} to be a place to be .format-ted but double braces, negates that behaviour
    return render_template_string("""
           <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <link href="{{{{url_for('static',filename='css/output.css')}}}}" rel="stylesheet">
                {{% include 'partials/header.jinja' with context %}}
            </head>
            <body>
                <!-- Start of {0}.jinja -->
            <header class="bg-white shadow">
                <div class="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
                <h1 class="text-3xl font-bold tracking-tight text-gray-900">{1}</h1>
                </div>
            </header>

            <article class="prose prose-slate m-6 p-2 mx-auto max-w-7xl">{2}</article>

            <!-- End of {0}.jinja -->
            {{% include 'partials/footer.jinja' with context %}}
            </body>
            </html>
           """.format(markdown_name, markdown_name.title().replace('-', ' ').replace('_', ' '), mrkdown), user=fake_user)

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

    return render_template('login.jinja', user=fake_user, message=message, request=request)

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
                        'photo_path': f'user/{data["username"]}"/photo.png'
                        }
        
        if sentralify(user, check_login=True) == True:
            with open(f'users/{user["username"]}/config.json', 'w') as user_config:
                json.dump(encrypted_user, user_config)
                
            secret_key = os.urandom(24)
            
            with open('./users/' + data['username'] + '/secret_key', 'wb') as secret_key_file:
                secret_key_file.write(secret_key) 
            
            response = make_response(render_template('login_complete.jinja', user=fake_user, request=request))
            response.set_cookie('secret_key', secret_key.decode('latin1'), secure=True)
            response.set_cookie('username', data['username'], secure=True)
            response.set_cookie('private_key', private_key.export_key().decode(), secure=True)
            
            return response
        
        else:
            if data.get('privacyPolicyCheckbox') and data.get('tosCheckbox'):
                return redirect('/login?message=Sorry,+those+login+details+are+incorrect')
            else:
                return redirect('/login?message=Sorry,+those+login+details+are+incorrect.\nPlease+accept+the+privacy+policy+and+the+terms+of+service.')
    except:
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
    
    data = load_user_data(user, request.cookies.get('private_key'), request.cookies.get('secret_key'))
    
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
                
    
    return render_template('index.jinja', user=user, data=data, message=message, tdt=three_day_timetable, today_calendar=events_today, request=request)

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
    
    return render_template('timetable.jinja', user=user, data=data, request=request)

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
    
    #return redirect('/dashboard')
    
    data = load_user_data(user, request.cookies.get('private_key'), request.cookies.get('secret_key'))
    
    # Organise calendar list by date
    data['calendar'] = sorted(data['calendar'], key=lambda x: parse(x['date']))
    
    # Get number of weeks from calendar list
    total_days = parse(data['calendar'][-1]['date']) - parse(data['calendar'][0]['date'])
    weeks = (total_days.days // 7) + 1 # Day one is a monday, last day is a friday, makes one week less than it should be
    
    # Put each day into it's own list
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
    
    # Put each week into it's own list in data['calendar']
    per_week_calendar = []
    current_week = [] # Current week calendar
    days_in_week = [0, 1 , 2, 3, 4]
    last_day_in_week = -1
    for y in range(len(per_day_calendar)): # Total number of days in per_day_calendar
        # If it is a valid weekday of school, and it is greater than the last recorded day of the week, that means we're still in the same week as before
        if parse(per_day_calendar[y][0]['date']).weekday() in days_in_week and parse(per_day_calendar[y][0]['date']).weekday() > last_day_in_week:
            current_week.append(per_day_calendar[y])
            last_day_in_week = parse(per_day_calendar[y][0]['date']).weekday()
        else:
            per_week_calendar.append(current_week)
            current_week = [per_day_calendar[y]]
            last_day_in_week = parse(per_day_calendar[y][0]['date']).weekday()
            
    per_week_calendar.append(current_week)
    current_week = [per_day_calendar[y]]
    last_day_in_week = parse(per_day_calendar[y][0]['date']).weekday()
    
    data['calendar'] = per_week_calendar
      
    return render_template('calendar.jinja', user=user, data=data, weeks=weeks, request=request)

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
    
    return render_template('details.jinja', user=user, request=request, data=data)

@app.route('/reload')
def reload():
    if not cookies_present(request):
        return redirect('/login')
    
    try:
        user = load_user_config(request)
    except ValueError:
        return redirect('/login')
    
    repeat_reload(username=user['username'], private_key=request.cookies.get('private_key'), secret_key=request.cookies.get('secret_key'), request=request)
    
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
# Main Program / Loop

if __name__ == '__main__':
    if in_docker:
        app.run('0.0.0.0', 5000, use_evalex=False)
    else:
        app.run('0.0.0.0', 5000, debug=True, use_evalex=False)