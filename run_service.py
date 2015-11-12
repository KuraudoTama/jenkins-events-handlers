import zmq
import threading
import logging
import json
import yaml
import jenkinsapi
import requests
requests.packages.urllib3.disable_warnings()
logging.getLogger("requests").setLevel(logging.WARNING)

from jenkins_slack_publisher import JenkinsSlackPublisher
from jenkins_flow_analyzer import JenkinsFlowAnalyzer


STATUS_MAP = {"SUCCESS": "success",
              "FAILURE": "failure",
              "ABORTED": "aborted"
              }


class StoppedException(Exception):
    pass


class DuplicatedException(Exception):
    pass


def setup_logging():
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(name)s: '
                               '%(message)s')


class ConfigInfo(object):
    def getattr(self, attr):
        try:
            return self.__getattribute__(attr)
        except:
            return None


class ZMQListener(threading.Thread):
    log = logging.getLogger('events.ZMQListener')

    def __init__(self, name, config_file):
        """
        @param name: the name of the zmq
        @param config_file: the config file path
        """
        threading.Thread.__init__(self, name=name)
        self.config = yaml.load(open(config_file).read())
        
        self.addr = self.config['zmq-address']
        self.name = name
        self._context = zmq.Context()
        self.socket = self._context.socket(zmq.SUB)
        self._stopped = False
        self.handlers=[]
        
        for name in self.config['handlers']:
            if name == 'jenkins-slack-publisher':
                jenkins_master = jenkinsapi.jenkins.Jenkins(self.config['jenkins_url'],
                                                            username=self.config['jenkins_username'],
                                                            password=self.config['jenkins_password'])
                self.handlers.append(JenkinsSlackPublisher('jenkins-slack-publisher', jenkins_master))
            if name == 'jenkins-flow-analyzer':
                jenkins_master = jenkinsapi.jenkins.Jenkins(self.config['jenkins_url'],
                                                            username=self.config['jenkins_username'],
                                                            password=self.config['jenkins_password'])
                self.handlers.append(JenkinsFlowAnalyzer('jenkins-flow-analyzer', jenkins_master))

    def run(self):
        self._setup_socket()
        
        for handler in self.handlers:
            handler.start()
        self.log.debug('ZMQListener %s Starts Listening' % self.name)
        while not self._stopped:
            event = self.socket.recv()
            for handler in self.handlers:
                handler.submit_event(event)
            self.log.debug(event)

    def stop(self):
        self._stopped = True
        if self._context:
            self.log.debug('ZMQListener %s Stops Listening' % self.name)
            self._context.destroy()

    def _setup_socket(self):
        self.log.debug('Setup Socket for ZMQListener %s' % self.name)
        self.socket.connect(self.addr)
        self.socket.setsockopt(zmq.SUBSCRIBE, '')


if __name__ == "__main__":
    setup_logging()
    service = ZMQListener('jenkins_zmq', 'config.yaml')
    service.start()
