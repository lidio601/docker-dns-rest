
# python 3 compatibility
from __future__ import print_function
from future import standard_library
from functools import reduce
standard_library.install_aliases()
from builtins import map
from builtins import str
from builtins import object

# core
from collections import namedtuple
from dnslib import DNSLabel
import json
import re


RE_VALIDNAME = re.compile('[^\w\d.-]')


Container = namedtuple('Container', 'id, name, running, addr')


def get(d, *keys):
    empty = {}
    return reduce(lambda d, k: d.get(k, empty), keys, d) or None


class DockerMonitor(object):

    '''
    Reads events from Docker and activates/deactivates container domain names
    '''

    def __init__(self, client, registry):
        self._docker = client
        self._registry = registry

    def run(self):
        # start the event poller, but don't read from the stream yet
        events = self._docker.events()

        # bootstrap by activating all running containers
        for container in self._docker.containers():
            rec = self._inspect(container['Id'], container)
            if rec.running:
                self._registry.add('name:/' + rec.name, [DNSLabel(rec.name)])
                self._registry.activate(rec)

        # read the docker event stream and update the name table
        for raw in events:
            evt = json.loads(raw)
            cid = evt.get('id')
            if cid is None:
                print ("Skipped event: " + str(evt))
                continue
            status = evt.get('status')
            if status in ('start', 'die'):
                try:
                    rec = self._inspect(cid)
                    if rec:
                        if status == 'start':
                            self._registry.add('name:/' + rec.name, [DNSLabel(rec.name)])
                            self._registry.activate(rec)
                        else:
                            self._registry.deactivate(rec)
                except Exception, e:
                    print (str(e))

    def _inspect(self, cid, container):
        # get full details on this container from docker
        rec = self._docker.inspect_container(cid)

        # ensure name is valid, and append our domain
        name = get(rec, 'Name')
        if not name:
            return None
        name = RE_VALIDNAME.sub('', name).rstrip('.')

        # default
        ipAddress = get(rec, 'NetworkSettings', 'IPAddress')

        # fallback in case of docker-compose with custom network
        if not ipAddress:
            networkName = get(container, 'HostConfig', 'NetworkMode')
            ipAddress = get(container, 'NetworkSettings', 'Networks', networkName, 'IPAddress')

        if not ipAddress:
            raise Exception("Unable to retrieve container ip address - %s" % cid)

        # 'id, name, running, addr'
        return Container(
            get(rec, 'Id'),
            name,
            get(rec, 'State', 'Running'),
            ipAddress
        )

