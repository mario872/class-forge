# syntax=docker/dockerfile:1

FROM python:3.11-slim-bullseye
LABEL maintainer="jamesaglynn10@gmail.com"
LABEL version="0.9"
LABEL description="This is the docker image for better-sentral"

ARG DEBIAN_FRONTEND=noninteractive

WORKDIR /home/better-sentral/

COPY static /home/better-sentral/static
COPY templates /home/better-sentral/templates
RUN mkdir /home/better-sentral/users
COPY main.py /home/better-sentral/main.py
COPY requirements.txt /home/better-sentral/requirements.txt

RUN python3 -m pip install --upgrade -r /home/better-sentral/requirements.txt

RUN python3 -m playwright install
RUN python3 -m playwright install-deps

EXPOSE 80 443

CMD [ "python3", "/home/better-sentral/main.py"]