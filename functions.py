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
from Crypto.Hash import SHA256
from Crypto import Random
from Crypto.Cipher import AES
import requests
import time
import os
from datetime import datetime
import threading
from sentralify import sentralify
from flask import render_template_string
from werkzeug.security import generate_password_hash, check_password_hash
import json
import zlib

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

fake_user = {'username': 'your.name',
             'password': 'your_password',
             'state': 'nsw',
             'base_url': 'caringbahhs',
             'photo_path': 'static/Rick Astley.jpg'}

timers = {}

def user_to_dict(user):
    user_dict = {
        'username': user.username,
        'password': user.password,
        'state': user.state[0],
        'base_url': user.base_url,
        'headless': headless
    }
    return user_dict

def load_user_data(user, request=None):
    """
    A function that loads the user data using the data in the user dict, and the private key, and secret key

    Args:
        user: The user dict decrypted and returned in the load_user_config function

    Returns:
        dict: The user data, e.g. the timetable, notices, calendar etc.
    """

    if type(user) != str:
        username = user.username
    else:
        username = user
    
    try:
        open(f'users/{zlib.adler32(username.encode())}.json', 'rb').close()
    except FileNotFoundError:
        repeat_reload(user)

    with open(f'users/{zlib.adler32(username.encode())}.json', 'r') as data_json:
        data = json.load(data_json)

    for day in data['timetable']:
        day['date'] = parse(day['date']).strftime('%a %b %d')

    return data


def repeat_reload(user, refresh_time=1800, http_request=None, automated=False):
    """
    A function that sets a timer to get new data from Sentral

    Args:
        user: The user
        refresh_time (int, optional): The amount of time between refreshes, in seconds, defaults to 1800
        http_request (_type_, optional): The request from the browser can be used if desired, to grab the private key
        and secret key. Defaults to None.

    """

    global timers

    # If it's between or equal to 17:00 and 05:00 then don't refresh the timetable, to avoid excess stress on Sentral
    # servers
    if not in_docker:
        print('Hour: ' + str(datetime.now().hour))
        print('Is it after or equal to 17: ' + str(17 <= datetime.now().hour))
        print('Is it before or equal to 5: ' + str(datetime.now().hour <= 5))
    if (17 <= datetime.now().hour or datetime.now().hour <= 5) and automated:
        if not in_docker:
            print('Automated and between 17 and 5')
        timers.pop(user.username, None)
        timers[user.username] = threading.Timer(refresh_time, repeat_reload,
                                           [user, refresh_time, http_request, True])
        timers[user.username].start()
        return

    user_dict = user_to_dict(user)

    try:
        data = sentralify(user_dict)
    except Exception as e:
        print('Failed to run sentralify, error below:')
        print(e)
        time.sleep(2)
        data = sentralify(user_dict)

    data['updated'] = datetime.now().strftime('%H:%M %d/%m/%Y')
    for notice in data['notices']:
        try:
            notice['content'] = markdown.markdown((notice['content']))
        except KeyError:
            pass

    with open(f'users/{zlib.adler32(user.username.encode())}.json', 'w') as data_json:
        json.dump(data, data_json)

    try:
        timers[user.username].cancel()
    except KeyError:
        pass

    # 1800.0 for 30 minutes, 600 for 10 minutes
    timers[user.username] = threading.Timer(refresh_time, repeat_reload,
                                       [user, refresh_time, http_request, True])
    timers[user.username].daemon = True  # Setting it to daemon kills the thread if the main thread exits
    timers[user.username].start()


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


def save_user_data(data, user):
    with open(f'users/{zlib.adler32(user.username.encode())}.json', 'w') as data_json:
        json.dump(data, data_json)