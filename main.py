from flask import *
from sentralify import sentralify
import json
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES
from binascii import hexlify
import os
import random
import markdown
from base64 import b64decode, b64encode
from bs4 import BeautifulSoup
from threading import Timer 
from dateutil.parser import parse
from datetime import datetime, timedelta
import ast

fake_user = {'username': 'your.name',
             'password': 'your_password',
             'state': 'nsw',
             'base_ur': 'caringbahhs',
             'photo_path': 'https://img.apmcdn.org/768cb350c59023919f564341090e3eea4970388c/square/72dd92-20180309-rick-astley.jpg'}

timers = {}

headless = True

app = Flask(__name__)

def decrypt(in_, private_key, test=None):
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
    username = request.cookies.get('username')
    password = request.cookies.get('private_key')
    
    if username != None or password != None:
        try:
            open(f'users/{username}/config.json', 'r').close()
        except FileNotFoundError:
            print('Error: Cookies were present, but there was no user config found!')
            return False
        
        return True
    
    else:
        return False
    
def load_user_config(request, username=None, private_key=None):
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
    try:
        open(f'users/{user["username"]}/data.json', 'rb').close()
    except FileNotFoundError:
        repeat_reload(user['username'], private_key, secret_key)
    
    with open(f'users/{user["username"]}/data.json', 'r') as data_json:
            cipher = AES.new(secret_key.encode('latin1'), AES.MODE_ECB)
            padded_data = b64decode(data_json.read())
            padded_data = cipher.decrypt(padded_data)
            padded_data = padded_data.decode('ascii')
            data = padded_data.rstrip('~')
            data = ast.literal_eval(data)
            return data

def repeat_reload(username: str, private_key: str, secret_key, refresh_time=1800):
    global timers
    
    print('TIMER WENT OFF!')
    user = load_user_config(None, username=username, private_key=private_key)
    
    user['headless'] = headless
    
    data = sentralify(user)
    
    for notice in data['notices']:
        try:
            notice['content'] = markdown.markdown((notice['content']))
        except KeyError:
            pass
    
    with open(f'users/{user["username"]}/data.json', 'wb') as data_json:
        padded_data = f'{data}' + ('~' * ((16-len(f'{data}')) % 16))
        cipher = AES.new(secret_key.encode('latin1'), AES.MODE_ECB)
        padded_data = padded_data.encode('latin1')
        padded_data = cipher.encrypt(padded_data)
        padded_data = b64encode(padded_data)
        data_json.write(padded_data)
        #json.dump(data, data_json)
    
    print('The timer stopped going off.')
    
    try:
        timers[username].cancel()
        print('Cancelled the previous timer!')
    except KeyError:
        pass
    
    #1800.0 for 30 minutes, 600 for 10 minutes
    timers[username] = Timer(float(refresh_time), lambda username=username, private_key=private_key, secret_key=secret_key: repeat_reload(username, private_key, secret_key))
    timers[username].start()

def format_event(event, event_date):
    if event['start'] is not None:
        event['start'] = event['start'].strftime('%H:%M')
    if event['end'] is not None:
        event['end'] = event['end'].strftime('%H:%M')
    event['date'] = event_date.strftime('%d/%m/%Y')
    # Assuming title cleaning is not needed for now, comment it out
    # event['title'] = event['title'].replace('Events: ', '')

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

    return render_template('login.jinja', user=fake_user, message=message)

@app.route('/login/finish', methods=['POST'])
def finish_login():
    data = request.form
    
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
            
        response = make_response(render_template('login_complete.jinja', user=fake_user))
        response.set_cookie('secret_key', secret_key.decode('latin1'), secure=True)
        response.set_cookie('username', data['username'], secure=True)
        response.set_cookie('private_key', private_key.export_key().decode(), secure=True)
        
        return response
    
    else:
        return redirect('/login?message=Sorry,+those+login+details+are+incorrect')

@app.route('/dashboard')
def home():    
    if not cookies_present(request):
        return redirect('/login')
    
    user = load_user_config(request)
    
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

    """
    for event in data['calendar']:
        event_date = parse(event['date'])
        
        if not weekend and event_date.day == today.day and event_date.month == today.month:
            # Today's events
            print(event_date.day, event_date.month, today.day, today.month)
            format_event(event, event_date)
            events_today.append(event)
        elif weekend:
            offset_days = 1 if weekend == 6 else 2
            if event_date.day == (today + timedelta(days=offset_days)).day and event_date.month == (today + timedelta(days=offset_days)).month:
                # Weekend events
                print(event_date.day, event_date.month, today.day, today.month)
                format_event(event, event_date)
                events_today.append(event)
    """
    for event in data['calendar']:
        event_date = parse(event['date'])
        
        if event_date.day == today.day and event_date.month == today.month:
            # Today's events
            format_event(event, event_date)
            events_today.append(event)
    
    return render_template('index.jinja', user=user, data=data, message=message, tdt=three_day_timetable, today_calendar=events_today)

@app.route('/timetable')
def timetable():
    if not cookies_present(request):
        return redirect('/login')
    
    user = load_user_config(request)
    
    if not user:
        return redirect('/login')
    
    data = load_user_data(user, request.cookies.get('private_key'), request.cookies.get('secret_key'))
    
    return redirect('/dashboard')
    
    return render_template('timetable.jinja', user=user, data=data)

@app.route('/notices')
def notices():
    if not cookies_present(request):
        return redirect('/login')
    
    user = load_user_config(request)
    
    if not user:
        return redirect('/login')
    
    return redirect('/dashboard')
    
    return render_template('notices.jinja', user=user)

@app.route('/calendar')
def calendar():
    if not cookies_present(request):
        return redirect('/login')
    
    user = load_user_config(request)
    
    if not user:
        return redirect('/login')
    
    return redirect('/dashboard')
    
    return render_template('calendar.jinja', user=user)

@app.route('/details')
def details():
    if not cookies_present(request):
        return redirect('/login')
    
    user = load_user_config(request)
    
    if not user:
        return redirect('/login')
    
    return redirect('/dashboard')
    
    return render_template('details.jinja', user=user)

@app.route('/reload')
def reload():
    if not cookies_present(request):
        return redirect('/login')
    
    user = load_user_config(request)
    
    repeat_reload(username=user['username'], private_key=request.cookies.get('private_key'), secret_key=request.cookies.get('secret_key'))
    
    return redirect('/dashboard')
    
if __name__ == '__main__':
    app.run('0.0.0.0', 5000, use_evalex=False)