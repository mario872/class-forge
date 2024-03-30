# syntax=docker/dockerfile:1

FROM python:3.11-slim-bullseye
LABEL maintainer="jamesaglynn10@gmail.com"
LABEL version="0.23"
LABEL description="This is the docker image for class-forge"

ENV IN_DOCKER true

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update
RUN apt-get install -yq tzdata
RUN ln -fs /usr/share/zoneinfo/Australia/Sydney /etc/localtime
RUN dpkg-reconfigure -f noninteractive tzdata

ENV TZ="Australia/Sydney"

WORKDIR /home/class-forge/

COPY static /home/class-forge/static
COPY templates /home/class-forge/templates
RUN mkdir /home/class-forge/users
COPY main.py /home/class-forge/main.py
COPY requirements.txt /home/class-forge/requirements.txt

RUN python3 -m pip install --upgrade -r /home/class-forge/requirements.txt

RUN python3 -m playwright install
RUN python3 -m playwright install-deps

EXPOSE 80 443

CMD [ "python3", "/home/class-forge/main.py"]
