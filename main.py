from flask import *
from sentralify import sentralify
import json
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from binascii import hexlify
import os
import random

fake_user = {'username': 'your.name',
             'password': 'your_password',
             'state': 'nsw',
             'base_ur': 'caringbahhs',
             'photo_path': 'https://img.apmcdn.org/768cb350c59023919f564341090e3eea4970388c/square/72dd92-20180309-rick-astley.jpg'}

app = Flask(__name__)

def decrypt(in_, private_key, test=None):
    private_key = RSA.import_key(private_key.encode())
    
    decrypter = PKCS1_OAEP.new(key=private_key)
    
    if test != None:
        print(decrypter.decrypt(test.encode(encoding='latin')))
    
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
    password = request.cookies.get('password')
    if username != None or password != None:
        return True
    else:
        return False
    
def load_user_config(request):
    with open(f'users/{request.cookies.get("username")}/config.json', 'r') as user_config_file:
        user = json.load(user_config_file)
        
    user = decrypt(user, request.cookies.get('private_key'), test=user['username'])
    
    try:
        open(user['photo_path'], 'r').close()
    except FileNotFoundError:
        user['photo_path'] = 'static/unsplash/' + random.choice(os.listdir('static/unsplash/'))
    
    return user

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
            'headless': False
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
    
    return render_template('index.jinja', user=user)

@app.route('/timetable')
def timetable():
    if not cookies_present(request):
        return redirect('/login')
    
    user = load_user_config(request)
    
    return render_template('timetable.jinja', user=user)

@app.route('/notice')
def notices():
    if not cookies_present(request):
        return redirect('/login')
    
    user = load_user_config(request)
    
    return render_template('notices.jinja', user=user)

@app.route('/calendar')
def calendar():
    if not cookies_present(request):
        return redirect('/login')
    
    user = load_user_config(request)
    
    return render_template('calendar.jinja', user=user)

@app.route('/reload')
def reload():
    if not cookies_present(request):
        return redirect('/login')
    
    user = load_user_config(request)
    
    user['headless'] = False
    
    data = sentralify(user)
    
    return render_template('index.jinja', user=user, data=data)
    

app.run('127.0.0.1', 5000)