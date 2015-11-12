# jenkins-events-handlers

This project listens on the ZMQ events from [zmq-event-publisher](https://git.openstack.org/cgit/openstack-infra/zmq-event-publisher) to perform various actions upon custom rules.

## How to Setup

<TODO>

Make up your own configuration:

```
cp config.yaml.sample config.yaml
vim config.yaml
```

The next section will describe how to compose this file

Start the service, the service will be running in a screen called "slack_zmq" that you can detach and attach at any time:

```
./start_listener.sh
```

You may also stop the service using `stop_listener.sh` and restart it using `restart_listener.sh`

## Compose config.yaml

### Configure the ZMQ Publish Address of the Jenkins Master

The ZMQ publish address can be configured with one line as a top element in the YAML file:

```ruby
zmq-address: 'tcp://<your jenkins master>:5555'
```

### Configure the Jenkins Master Information

The Jenkins master information is described with 3 lines of YAML code, an example:

```ruby
jenkins_url: http://<your jenkins master>:8080/
jenkins_username: Joshua
jenkins_password: passw0rd
```

### Enable the Event Handlers

For now there are 2 handlers in this project, jenkins-flow-analyzer(`jenkins_flow_analyzer.py`) and jenkins-slack-publisher(`jenkins_slack_publisher.py`), you may enable one or both in the `handlers` section:

```ruby
handlers:
  - jenkins-flow-analyzer
  - jenkins-slack-publisher
```

### Configure jenkins-slack-publisher

The configuration of jenkins-slack-publisher is described in `jenkins-slack-publisher` top element.

Configure the name, token, and as-user (if true, the bot will be displayed as a human user of the token) of the bots in `bots`.

Configure the rules in the `rules` section. Each rule consists of 4 parts:

* name-pattern: should be a Python regex to match the Jenkins job names
* match-any: a "key" path to match the data in the event, the event will be handled if any entry is matched
* bot: the bot name to publish the event
* channel: the channel to publish the event

A event from zmq-event-publisher is like:

```
{"name":"Build_VM","url":"job/Build_VM/","build":{"full_url":"http://<jenkins_url>:8080/job/Build_VM/2357/","number":2357,"phase":"FINISHED","status":"FAILURE","url":"job/Build_VM/2357/","parameters":{"index":"36"},"node_name":"","host_name":"192.168.122.1"}}
```

So if you want to match the host_name in the example above, you should write the rule like:

```ruby
      match-any:
        - build.parameters.host_name: '192.168.122.1'
```

The code will search for the value using the path `build->parameters->host_name` upon the event.

A sample configuration:

```ruby
jenkins-slack-publisher:
  bots:
    - name: bot-joshua
      token: '<your slack token>'
      as-user: true
    - name: bot-delivery
      token: '<your slack token>'
  rules:
    - name-pattern: '^\Flow_(Deploy|Update|Refresh|Deployment|Destroy)$'
      match-any:
        - build.parameters.index: '26'
        - build.parameters.index: '32'
        - build.parameters.index: '48'
      bot: bot-joshua
      channel: '#test-everything'

    - name-pattern: '^Build_(Baremetal|VM)$'
      match-any:
        - build.parameters.index: '36'
        - build.parameters.index: '48'
      bot: bot-joshua
      channel: '#test-everything'

    - name-pattern: '^\Flow_Pipeline_(Refresh|Update)$'
      bot: bot-delivery
      channel: '#deliver-everything'
```

### Configure jenkins-flow-analyzer (Optional)

__Important Note__: This handler only applies to the flow jobs used in ICOS since there is some special logic in the flows so that the handler can analyze.

The configuration of jenkins-flow-analyzer is described in `jenkins-flow-analyzer` top element.

Configure the name, token, channel and as-user (if true, the bot will be displayed as a human user of the token) in `slack`.

Configure the Jenkins build flows in the `flows` section.

```ruby
jenkins-flow-analyzer:
  slack:
    name: bot-joshua
    token: '<your slack token>'
    channel: '#test-everything'
    as-user: true
  flows:
    - Flow_Deploy
    - Flow_Update
    - Flow_Refresh
```

### A Working Sample

```ruby
zmq-address: 'tcp://<your jenkins master>:5555'

jenkins_url: http://<your jenkins master>:8080/
jenkins_username: Joshua
jenkins_password: passw0rd

handlers:
  - jenkins-flow-analyzer
  - jenkins-slack-publisher

bots:
  - name: bot-joshua
    token: '<your slack token>'

jenkins-flow-analyzer:
  slack:
    name: bot-joshua
    token: '<your slack token>'
    channel: '#test-everything'
    as-user: true
  flows:
  - Flow_Deploy
  - Flow_Update
  - Flow_Refresh

jenkins-slack-publisher:
  bots:
    - name: bot-joshua
      token: '<your slack token>'
      as-user: true
    - name: bot-delivery
      token: '<your slack token>'
  rules:
    - name-pattern: '^\Flow_(Deploy|Update|Refresh|Deployment|Destroy)$'
      match-any:
        - build.parameters.index: '26'
        - build.parameters.index: '32'
        - build.parameters.index: '48'
      bot: bot-joshua
      channel: '#test-everything'

    - name-pattern: '^Build_(Baremetal|VM)$'
      match-any:
        - build.parameters.index: '36'
        - build.parameters.index: '48'
      bot: bot-joshua
      channel: '#test-everything'

    - name-pattern: '^\Flow_(Refresh|Update)$'
      bot: bot-delivery
      channel: '#deliver-everything'
```

## Limitations and Future Plans

### Limitations

Currently this service has the following limitations:

* Only one Jenkins master is supported.
* The configuration file can only be named as `config.yaml`.
* The jenkins-flow-analyzer is not applicable for general Jenkins build flow analysis.
* The architecture is not flexible enough for easy extension

### Future Plans

* Using Slack WebSocket instead of APIs to reduce communication cost.
* Support multiple Jenkins masters.
* Refactor the architecture to support easier extension/integration.
