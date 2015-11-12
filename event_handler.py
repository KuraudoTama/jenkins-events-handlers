import threading
import logging
import json


class EventHandler(threading.Thread):
    log = logging.getLogger("events.EventHandler")
    
    def __init__(self,event):
        self.event=event.split(None)[0]
        self.data = json.loads(event.lstrip(self.event).lstrip())
        threading.Thread.__init__(self, name="EventHandler for event: <%s>" % event)