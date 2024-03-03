import subprocess
docker_v = 0.5

commands = [f'sudo docker build . -t solderingiron86/better-sentral:{docker_v}',
            f'sudo docker push solderingiron86/better-sentral:{docker_v}']


for command in commands:
    subprocess.run(command.split(' '))