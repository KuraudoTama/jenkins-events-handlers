#!/bin/bash

echo -e "zombie kr\nverbos on" > ~/.screenrc

echo "Start Jenkins-ZMQ-Slack listener"
screen -S slack_zmq /root/cd_py_env/bin/python run_service.py