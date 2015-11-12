#!/bin/bash
echo "Stop Jenkins-ZMQ-Slack listener"
kill -9 `screen -ls|grep slack_zmq|awk '{print $1}'|awk -F. '{print $1}'`
screen -wipe >/dev/null