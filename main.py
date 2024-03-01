from flask import *
from sentralify import sentralify
import json
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from binascii import hexlify
import os
import random
import markdown
from bs4 import BeautifulSoup
from threading import Timer
import urllib
from base64 import urlsafe_b64encode, urlsafe_b64decode

fake_user = {'username': 'your.name',
             'password': 'your_password',
             'state': 'nsw',
             'base_ur': 'caringbahhs',
             'photo_path': 'https://img.apmcdn.org/768cb350c59023919f564341090e3eea4970388c/square/72dd92-20180309-rick-astley.jpg'}

timers = {}

app = Flask(__name__)

def md_to_text(md):
    html = markdown.markdown(md)
    soup = BeautifulSoup(html, features='html.parser')
    return soup.get_text()

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
                out[key] = decrypter.decrypt(in_[key].encode(encoding='latin')).decode(encoding='latin')
            else:
                out[key] = in_[key]
    elif type(in_) == str:
        out = decrypter.decrypt(in_.encode(encoding='latin')).decode(encoding='latin')
    
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
            
        user = decrypt(user, request.cookies.get('private_key'), test=user['username'])
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

def load_user_data(user):
    with open(f'users/{user["username"]}/data.json', 'r') as data_json:
        data = json.load(data_json)

    return data

def repeat_reload(username, private_key):
    global timers
    
    print('TIMER WENT OFF!')
    user = load_user_config(None, username=username, private_key=private_key)
    
    user['headless'] = True
    
    data = sentralify(user)
    
    for notice in data['notices']:
        try:
            notice['text'] = md_to_text(notice['text'])
        except KeyError:
            pass
    
    with open(f'users/{user["username"]}/data.json', 'w') as data_json:
        json.dump(data, data_json)
    
    print('The timer stopped going off.')
    
    try:
        timers[username].cancel()
    except KeyError:
        pass
    
    timers[username] = Timer(1800.0, lambda username=username, private_key=private_key: repeat_reload(username, private_key))
    timers[username].start()

@app.route('/')
def one():
    if cookies_present(request):
        return redirect('/dashboard')
    else:
        return redirect('/login')
    
@app.route('/login')
def login():
    return render_template('login.jinja', user=fake_user)

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
            'headless': True
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
            
        response = make_response(render_template('login_complete.jinja', user=fake_user))
        response.set_cookie('username', data['username'], secure=True)
        response.set_cookie('private_key', private_key.export_key().decode(), secure=True)
            
        return response
    
    else:
        return redirect('/login')

@app.route('/dashboard')
def home():    
    if not cookies_present(request):
        return redirect('/login')
    
    user = load_user_config(request)
    
    if not user:
        return redirect('/login')
    
    data = load_user_data(user)
    
    lorem_ipsum = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed volutpat libero volutpat purus condimentum pellentesque. Donec lobortis ipsum et lacus facilisis tempor. Curabitur efficitur velit eget enim tincidunt ullamcorper. Donec ornare purus quis lacinia ultricies. Morbi fringilla dolor non ex laoreet, a rutrum ipsum bibendum. '
    
    return render_template('index.jinja', user=user, data=data, lorem_ipsum=lorem_ipsum)

@app.route('/timetable')
def timetable():
    if not cookies_present(request):
        return redirect('/login')
    
    user = load_user_config(request)
    
    if not user:
        return redirect('/login')
    
    return render_template('timetable.jinja', user=user)

@app.route('/notices')
def notices():
    if not cookies_present(request):
        return redirect('/login')
    
    user = load_user_config(request)
    
    if not user:
        return redirect('/login')
    
    return render_template('notices.jinja', user=user)

@app.route('/calendar')
def calendar():
    if not cookies_present(request):
        return redirect('/login')
    
    user = load_user_config(request)
    
    if not user:
        return redirect('/login')
    
    return render_template('calendar.jinja', user=user)

@app.route('/reload')
def reload():
    """
    try:
        username = request.args['username']
        private_key = request.args['state'] # To throw off hackers, probably won't work
        
        UandP = {'username': username, 'private_key': private_key}
        
        Timer(10.0, lambda UandP=UandP: redirect(f'/reload?username={UandP["username"]}&state={UandP["private_key"]}')).start()
        url_present = True
        print('We got a reload by Timer!')
    except KeyError:
        url_present = False
    
    if not url_present:
        if not cookies_present(request):
            return redirect('/login')
    
        user = load_user_config(request)
    
    else:
        print(urllib.parse.unquote_plus(request.args['state']))
        user = load_user_config(None, username=request.args['username'], private_key=urllib.parse.unquote_plus(request.args['state'].decode(encoding='latin')))
    
    if not user:
        return redirect('/login')
    
    user['headless'] = True
    
    data = sentralify(user)
    
    for notice in data['notices']:
        try:
            notice['text'] = md_to_text(notice['text'])
        except KeyError:
            pass
    
    with open(f'users/{user["username"]}/data.json', 'w') as data_json:
        json.dump(data, data_json)
    
    if not url_present:
        return redirect('/dashboard')
    else:
        return
    """
    
    if not cookies_present(request):
        return redirect('/login')
    
    user = load_user_config(request)
    
    repeat_reload(username=user['username'], private_key=request.cookies.get('private_key'))
    
    return redirect('/dashboard')
    
if __name__ == '__main__':
    app.run('0.0.0.0', 5000, use_evalex=False)