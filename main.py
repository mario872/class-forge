from flask import *
from sentralify import sentralify
import json
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from binascii import hexlify
import os

app = Flask(__name__)

def decrypt(in_, private_key, test=None):
    print(f'PRIVATE KEY IN DECRYPT IS {private_key}')
    print(f'ENCODED PRIVATE KEY IN DECRYPT IS {private_key.encode()}')

    private_key = RSA.import_key(private_key.encode())
    
    decrypter = PKCS1_OAEP.new(key=private_key)
    
    if test != None:
        print(decrypter.decrypt(test.encode(encoding='latin')))
    
    print(f'IN is of type {type(in_)}')
    
    if type(in_) == dict:
        out = {}
        print('Now it is ' + str(private_key) + '\nType is ' + str(type(private_key)))
        keys = list(in_.keys())
        for key in keys:
            print('Key is ' + str(key))
            if key != 'photo_path':
                out[key] = decrypter.decrypt(in_[key].encode(encoding='latin')).decode(encoding='latin')
    elif type(in_) == str:
        out = decrypter.decrypt(in_.encode(encoding='latin')).decode(encoding='latin')
    
    return out

@app.route('/')
def one():
    username = request.cookies.get('username')
    password = request.cookies.get('password')
    if username == None or password == None:
        return redirect('/login')
    else:
        return redirect('/dashboard')

@app.route('/login')
def login():
    return render_template('login.jinja')

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
            
        response = make_response(render_template('login_complete.jinja', user=user_config))
        response.set_cookie('username', data['username'], secure=True)
        print(f'PRIVATE KEY IS {private_key.export_key().decode()}')
        response.set_cookie('private_key', private_key.export_key().decode(), secure=True)
            
        return response
    
    else:
        return redirect('/login')

@app.route('/dashboard')
def home():
    with open(f'users/{request.cookies.get("username")}/config.json', 'r') as user_config_file:
        user = json.load(user_config_file)
        
    user = decrypt(user, request.cookies.get('private_key'), test=user['username'])
    return render_template('index.jinja', user=user)

@app.route('/timetable')
def timetable():
    return render_template('timetable.jinja')

@app.route('/notice')
def notice():
    return render_template('notices.jinja')

@app.route('/calendar')
def calendar():
    return render_template('calendar.jinja')

app.run('127.0.0.1', 5000)