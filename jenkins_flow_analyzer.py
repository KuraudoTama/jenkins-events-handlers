import threading
import logging
from six.moves import queue as Queue
import yaml
from pyslack import SlackClient
import json

from event_handler import EventHandler


def getFromDict(dataDict, mapList):
    return reduce(lambda d, k: d[k], mapList, dataDict)


class JenkinsFlowAnalyzer(threading.Thread):
    log = logging.getLogger("events.JenkinsFlowAnalyzer")

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
        event_thread = JenkinsFlowHandler(event, self.jenkins_master)
        event_thread.start()
        

class JenkinsFlowHandler(EventHandler):
    log = logging.getLogger("events.JenkinsFlowHandler")

    def __init__(self, event, jenkins_master , config='config.yaml'):
        EventHandler.__init__(self, event)
        self.log.debug('Initialize JenkinsSlackHandler')
        self.config = yaml.load(open(config).read())['jenkins-flow-analyzer']
        self.jenkins_master = jenkins_master
        
    def run(self):
        self.process_event()
                          
    def process_event(self):
        if self.event == 'onFinalized':
            self.log.debug('Ignore this event %s: %s' % (self.event, self.data["build"]["url"]))
            return    
        job_name = self.data.get('name')
        if job_name not in self.config['flows'] or self.event == 'onStarted':
            self.log.debug('Ignore this event %s: %s' % (self.event, self.data["build"]["url"]))
            return
        else:
            self.log.debug('Process this event %s: %s' % (self.event, self.data["build"]["url"]))
            self.process_flow(self.data, self.jenkins_master)
            
    def process_flow(self, data, jenkins_master):
        build_status = data.get('build').get('status')
        if build_status != 'FAILURE':
            self.log.debug('This flow will not be processed')
            return
        
        build_number = data.get('build').get('number')
        build = self.jenkins_master[data.get('name')].get_build(int(build_number))
        build_name = build.name
        console = build.get_console()
        lines = console.split('\n')
        line_number = len(lines)
        index = 0
        failed_jobs = {}
        while index < line_number:
            if lines[index].startswith('[Result] FAILURE'):
                job_name = lines[index - 1].lstrip('[Job Name]').lstrip().rstrip('\n')
                url = lines[index + 1].lstrip('[URL]').lstrip().rstrip('\n')
                failed_jobs[job_name] = url
            index = index + 1
            
        full_url = data.get('build').get('full_url')
        
        if len(failed_jobs) == 0:
            msg = '<%s|%s> failed' % (full_url, build_name)
        else:
            failed_jobs_msg = ''
            for name in failed_jobs:
                failed_jobs_msg = ' '.join([failed_jobs_msg, '<%s|%s>' % (failed_jobs[name], name)])
            msg = '<%s|%s> failed at %s' % (full_url, build_name, failed_jobs_msg)
        
        self.log.debug('Slack message: %s' % msg)
        
        slack_token = self.config['slack']['token']
        slack_botname = self.config['slack']['name']
        slack_channel = self.config['slack']['channel']
        
        slack = SlackClient(slack_token)
           
        slack.chat_post_message(slack_channel, msg, username=slack_botname, mrkdwn=True)
