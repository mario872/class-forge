import subprocess
docker_v = 0.9

commands = [f'sudo docker build . -t solderingiron86/better-sentral:{docker_v}',
            f'sudo docker push solderingiron86/better-sentral:{docker_v}']


for command in commands:
    subprocess.run(command.split(' '))


"""
import subprocess
docker_v = float(input('Update to better-sentral_package v: '))

commands = [f'sudo docker stop better-sentral',
            f'sudo docker rm better-sentral',
            f'sudo docker run -d -p 5000:5000 solderingiron86/better-sentral:{str(docker_v)}']
            
for command in commands:
    subprocess.run(command.split(' '))
"""