import threading
import logging
import json
import re
from subprocess import call
import time
import os

import yaml
from PIL import Image

from six.moves import queue as Queue
from pyslack import SlackClient
from event_handler import EventHandler


def getFromDict(dataDict, mapList):
    return reduce(lambda d, k: d[k], mapList, dataDict)


def format_timedelta(timedelta):
    digit_hours, remainder = divmod(timedelta.seconds, 3600)
    digit_minutes, digit_seconds = divmod(remainder, 60)

    hours = str(digit_hours)
    if len(hours) == 1:
        hours = '0' + hours
    minutes = str(digit_minutes)
    if len(minutes) == 1:
        minutes = '0' + minutes
    seconds = str(digit_seconds)
    if len(seconds) == 1:
        seconds = '0' + seconds

    if timedelta.days == 0:
        return '%s:%s:%s' % (hours, minutes, seconds)
    else:
        return '%s d, %s:%s:%s' % (timedelta.days, hours, minutes, seconds)


class JenkinsSlackPublisher(threading.Thread):
    log = logging.getLogger("events.JenkinsSlackPublisher")

    def __init__(self, name, jenkins_master):
        threading.Thread.__init__(self, name=name)
        self.queue = Queue.Queue()
        self.name = name
        self._stopped = False
        self.jenkins_master = jenkins_master

    def run(self):
        self.log.debug('Handler %s Starts Handling Events' % self.name)
        while not self._stopped:
            event = self.queue.get()
            if not event:
                continue
            self.handle_event(event)

    def stop(self):
        self._stopped = True
        self.queue.put(None)

    def submit_event(self, event):
        if self._stopped:
            raise StoppedException("Handler %s is no longer running"
                                   % self.name)
        self.queue.put(event)

    def handle_event(self, event):
        event_thread = JenkinsSlackHandler(event, self.jenkins_master)
        event_thread.start()


class JenkinsSlackHandler(EventHandler):
    log = logging.getLogger("events.JenkinsSlackHandler")

    def __init__(self, event, jenkins_master, config='config.yaml'):
        EventHandler.__init__(self, event)
        self.log.debug('Initialize JenkinsSlackHandler')
        total_config = yaml.load(open(config).read())
        self.config = total_config['jenkins-slack-publisher']
        self.jenkins_user = total_config['jenkins_username']
        self.jenkins_password = total_config['jenkins_password']
        self.jenkins_master = jenkins_master

    def run(self):
        self.process_event()

    def process_event(self):
        job_name = self.data.get('name')

        if self.event == 'onFinalized':
            self.log.debug('Ignore this event %s: %s' % (self.event, self.data["build"]["url"]))
            return

        for rule in self.config['rules']:
            # If job name does not match the pattern
            # Go to the next
            if not re.match(rule['name-pattern'], job_name):
                continue

            # Set the initial match flag to 'True'
            match = True

            if rule.get('match-any'):
                match = False
                for any in rule.get('match-any'):
                    key = any.keys()[0]
                    value = any.values()[0]
                    if getFromDict(self.data, key.split('.')) == value:
                        match = True
                        break

            if match is True:
                self.log.debug('Process this event %s against %s' % (self.event, self.data["build"]["url"]))
                self.process_rule(rule)
            else:
                self.log.debug('This event %s: %s does not match rule "%s"' % (self.event,
                                                                               self.data["build"]["url"],
                                                                               rule))

    def process_rule(self, rule):
        self.log.debug('Processing rules')
        bot_name = rule['bot']
        token = None
        as_user = False
        for bot in self.config['bots']:
            if bot['name'] == bot_name:
                token = bot['token']
                as_user = bot['as-user']
                break

        if token is not None:
            self.post_message(token, rule['channel'], bot_name, as_user, self.data, self.jenkins_master)
        else:
            self.log.debug('Bot %s not found' % bot_name)

    def post_message(self, token, channel, bot_name, as_user, data, jenkins_master):
        slack = SlackClient(token)

        full_url = data.get('build').get('full_url')
        job_name = data.get('name')
        build_number = data.get('build').get('number')
        build_status = data.get('build').get('status')
        build_phase = data.get('build').get('phase')

        build = jenkins_master[job_name].get_build(int(build_number))

        build_name = build.name
        msg = None
        attachments = dict()
        attachments['thumb_url'] = 'http://jenkins-ci.org/sites/default/files/images/headshot.png'
        if build_phase == 'STARTED':
            build_cause = build.get_causes()[0]['shortDescription']
            msg = '%s, %s' % (build_phase, build_cause)
            attachments['color'] = '#439FE0'
        elif build_phase == 'COMPLETED':
            build_duration = format_timedelta(build.get_duration())
            msg = '%s %s after %s' % (build_phase, build_status, build_duration)
            if build_status == 'SUCCESS':
                attachments['color'] = 'good'
            elif build_status == 'FAILURE':
                attachments['color'] = 'danger'
                attachments['thumb_url'] = \
                    'http://www.tikalk.com/assets/default/oops-jenkins-cfc3e6aa03f67ba5dea069dd21a4fe08.png'
            elif build_status == 'UNSTABLE':
                attachments['color'] = 'warning'
            else:
                attachments['color'] = '#439FE0'
        else:
            msg = '%s %s' % (build_phase, build_status)

        attachments['title'] = build_name
        attachments['title_link'] = full_url
        attachments['text'] = msg

        self.log.debug('Slack message: %s %s' % (msg, str(attachments)))
        slack.chat_post_message(channel,
                                '',
                                username=bot_name,
                                as_user=as_user,
                                attachments=json.JSONEncoder().encode([attachments]))

        if build_status == 'FAILURE':
            self.log.debug('Posting snapshot for %s/console' % full_url)
            self.post_screenshot(slack, channel, build_name, '%s/%s' % (full_url, '/console'),
                                 user=self.jenkins_user, password=self.jenkins_password,
                                 output='screenshot-%s.jpg' % int(time.time()))

    def post_screenshot(self, slack, channel, build_name, full_url, user=None, password=None, output='output.jpg'):
        self.log.debug('Capturing screenshot to %s' % output)
        ret_code = call(['casperjs', 'capture.js',
                         '--url=%s' % full_url, '--juser=%s' % user, '--jpwd=%s' % password,
                         '--out=%s' % output])
        if ret_code != 0:
            self.log.error('Capture screenshot for %s failed' % full_url)
            return

        im_load = Image.open(output)
        if im_load.size[1] > 2000:
            height = 2000
        else:
            height = im_load.size[1]

        im_upload = im_load.crop((0, im_load.size[1] - height, im_load.size[0], im_load.size[1]))
        file_name = 'upload-%s.jpg' % int(time.time())
        im_upload.save(file_name)
        self.log.debug('Uploading screenshot %s' % file_name)
        slack.file_upload([channel], file=file_name, title=build_name)
        self.log.debug('Removing images: %s, %s' % (output, file_name))
        os.remove(output)
        os.remove(file_name)
