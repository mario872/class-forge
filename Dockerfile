# syntax=docker/dockerfile:1

FROM ubuntu:22.04
LABEL maintainer="jamesaglynn10@gmail.com"
LABEL version="0.1"
LABEL description="This is the docker image for better-sentral"

ARG DEBIAN_FRONTEND=noninteractive

RUN apt update
RUN apt install python3-pip python3 tree -y
RUN apt clean

WORKDIR /home/better-sentral/

COPY node_modules /home/better-sentral/node_modules
COPY static /home/better-sentral/static
COPY templates /home/better-sentral/templates
RUN mkdir /home/better-sentral/users
COPY main.py /home/better-sentral/main.py
COPY requirements.txt /home/better-sentral/requirements.txt

RUN tree /home/better-sentral/

RUN python3 -m pip install -r /home/better-sentral/requirements.txt

RUN playwright install
RUN playwright install-deps

EXPOSE 80 443

CMD [ "python3", "/home/better-sentral/main.py"]