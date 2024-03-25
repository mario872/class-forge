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

import subprocess
docker_v = 0.21

commands = [f'sudo docker build . -t solderingiron86/better-sentral:{docker_v}',
            f'sudo docker run --name better-sentral-{docker_v} -p 5000:5000 solderingiron86/better-sentral:{docker_v}',
            f'sudo docker push solderingiron86/better-sentral:{docker_v}',
            f'sudo docker rm better-sentral-{docker_v}']


for command in commands:
    subprocess.run(command.split(' '))