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

import random
import markdown
from base64 import b64decode, b64encode
import base64
from dateutil.parser import parse
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES
import ast
import requests
import json
import os
from datetime import datetime
import threading
from sentralify import sentralify
from flask import render_template_string

from main import in_docker, headless, fake_user  # Risky move, but imports variables from main

timers = {}

def decrypt(in_, private_key: str, test=None):
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

    out = None

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

    if out != None:
        return out
    else:
        print('Error: in_ must be a dict or str, not a %s' % type(in_))
        exit()


def cookies_present(http_request):
    """
    A function to check if cookies are present in the user's browser session.

    Args:
        http_request: The request given by the app routing function, contains cookies set in it

    Returns:
        bool: Whether cookies are set or not.
    """

    username = http_request.cookies.get('username')
    password = http_request.cookies.get('private_key')
    secret_key = http_request.cookies.get('secret_key')

    if username != None or password != None or secret_key != None:
        try:
            open(f'users/{username}/config.json', 'r').close()
        except FileNotFoundError:
            print('Error: Cookies were present, but there was no user config found!')
            return False

        return True

    else:
        return False


def load_user_config(http_request, username=None, private_key=None):
    """
    A function that loads the user config using cookies stored in browser, or from credentials passed to the function

    Args:
        http_request: The request given by the app routing function, contains cookies set in it
        username (str, optional): Username for if the cookies are not yet set in the browser. Defaults to None.
        private_key (str, optional): Private key for if the cookies are not yet set in the browser. Defaults to None.

    Returns:
        dict: A dict containing the decrypted user config
    """
    if http_request != None:
        with open(f'users/{http_request.cookies.get("username")}/config.json', 'r') as user_config_file:
            user = json.load(user_config_file)

        user = decrypt(user, http_request.cookies.get('private_key'))
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


def load_user_data(user: dict, private_key: str, secret_key: str, request=None):
    """
    A function that loads the user data using the data in the user dict, and the private key, and secret key

    Args:
        user (dict): The user dict decrypted and returned in the load_user_config function
        private_key (str): The private_key in the browser cookies, but passed directly to this function
        secret_key (str): The secret key for symmetrical encryption in the user data

    Returns:
        dict: The user data, e.g. the timetable, notices, calendar etc.
    """

    try:
        open(f'users/{user["username"]}/data.json', 'rb').close()
    except FileNotFoundError:
        repeat_reload(user['username'], private_key, secret_key)

    do_not_encode = False
    if secret_key == None:
        secret_key = request.cookies.get('secret_key')
        if secret_key != None:
            # Decode the base64-encoded secret_key string to bytes
            secret_key = base64.b64decode(secret_key)
        else:
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

    for day in data['timetable']:
        day['date'] = parse(day['date']).strftime('%a %b %d')

    return data


def repeat_reload(username: str, private_key: str, secret_key, refresh_time=1800, http_request=None, automated=False):
    """
    A function that sets a timer to get new data from Sentral

    Args:
        username (str): The user's username
        private_key (str): The user's private key
        secret_key: The user's secret key
        refresh_time (int, optional): The amount of time between refreshes, in seconds, defaults to 1800
        http_request (_type_, optional): The request from the browser can be used if desired, to grab the private key
        and secret key. Defaults to None.

    """

    global timers

    user = load_user_config(http_request=None, username=username, private_key=private_key)

    # If it's between or equal to 17:00 and 05:00 then don't refresh the timetable, to avoid excess stress on Sentral
    # servers
    if not in_docker:
        print('Hour: ' + str(datetime.now().hour))
        print('Is it after or equal to 17: ' + str(17 <= datetime.now().hour))
        print('Is it before or equal to 5: ' + str(datetime.now().hour <= 5))
    if (17 <= datetime.now().hour or datetime.now().hour <= 5) and automated:
        if not in_docker:
            print('Automated and between 17 and 5')
        timers.pop(username, None)
        timers[username] = threading.Timer(refresh_time, repeat_reload,
                                           [username, private_key, secret_key, refresh_time, http_request, True])
        timers[username].start()
        return

    user['headless'] = headless

    try:
        data = sentralify(user)
    except:
        data = load_user_data(user, private_key, secret_key)

    data['updated'] = datetime.now().strftime('%H:%M %d/%m/%Y')
    for notice in data['notices']:
        try:
            notice['content'] = markdown.markdown((notice['content']))
        except KeyError:
            pass

    do_not_encode = False
    if secret_key == None:
        secret_key = http_request.cookies.get('secret_key')
        if secret_key == None:
            try:
                with open(f'users/{user["username"]}/secret_key', 'rb') as secret_key_file:
                    secret_key = secret_key_file.read()
                    do_not_encode = True
                    if not in_docker:
                        print('Secret Key is' + str(secret_key) + 'In repeat_reload.')
            except FileNotFoundError:
                print('Error, I don\'t know what to do here! In repeat_reload')

    try:
        os.remove(f'users/{user["username"]}/secret_key')
    except FileNotFoundError:
        pass

    with open(f'users/{user["username"]}/data.json', 'wb') as data_json:
        padded_data = f'{data}' + ('~' * ((16 - len(f'{data}')) % 16))
        if do_not_encode:
            cipher = AES.new(secret_key, AES.MODE_ECB)
        else:
            cipher = AES.new(secret_key.encode('latin1'), AES.MODE_ECB)
        padded_data = padded_data.encode('ascii')
        padded_data = cipher.encrypt(padded_data)
        padded_data = b64encode(padded_data)
        data_json.write(padded_data)

    try:
        timers[username].cancel()
    except KeyError:
        pass

    # 1800.0 for 30 minutes, 600 for 10 minutes
    timers[username] = threading.Timer(refresh_time, repeat_reload,
                                       [username, private_key, secret_key, refresh_time, http_request, True])
    timers[username].daemon = True  # Setting it to daemon kills the thread if the main thread exits
    timers[username].start()


def format_event(event, event_date):
    """
    Converts the full timestring given by Sentralify on events to a human-readable format

    Args:
        event dict: The event dict to change
        event_date datetime.datetime: The date of the event
    """
    if event['start'] != None:
        event['start'] = event['start'].strftime('%H:%M')
    if event['end'] != None:
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
    # The below is a bit of an eccentric mess.
    # However, I'll try to explain it The 4 opening braces and 4 closing
    # braces, even though Jinja2 requires only two, is because python evaluates {} to be a place to be .format-ted
    # but double braces, negates that behaviour
    return render_template_string("""
           <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <link href="{{{{url_for('static',filename='css/output.css')}}}}" rel="stylesheet">
                <script>
                  if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {{
                    document.documentElement.classList.add('dark')
                  }} else {{
                    document.documentElement.classList.remove('dark')
                  }}

                  // Whenever the user explicitly chooses light mode
                  localStorage.theme = 'light'

                  // Whenever the user explicitly chooses dark mode
                  localStorage.theme = 'dark'

                  // Whenever the user explicitly chooses to respect the OS preference
                  localStorage.removeItem('theme')
                </script>
                {{% include 'partials/header.jinja' with context %}}
            </head>
            <body class="bg-white dark:bg-slate-800">
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
           """.format(markdown_name, markdown_name.title().replace('-', ' ').replace('_', ' '), mrkdown),
                                  user=fake_user, weather=get_weather())


def get_weather():
    """
    A function that gets the weather from weather.jimmyscompany.top

    Returns:
        dict: The weather

    """
    try:
        weather = requests.get('https://weather.jimmyscompany.top/api')
        return json.loads(weather.text)
    except requests.exceptions.ConnectionError:
        weather = {'current': {'temp': 'No Internet'},
                   'daily': [{'weather': [{'icon': "None"}], 'temp': {'max': 'No Internet'}}]}
        return weather

def save_user_data(data, secret_key, username):
    with open(f'users/{username}/data.json', 'wb') as data_json:
        padded_data = f'{data}' + ('~' * ((16 - len(f'{data}')) % 16))
        cipher = AES.new(secret_key.encode('latin1'), AES.MODE_ECB)
        padded_data = padded_data.encode('ascii')
        padded_data = cipher.encrypt(padded_data)
        padded_data = b64encode(padded_data)
        data_json.write(padded_data)