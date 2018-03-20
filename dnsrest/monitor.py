
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

# local
from dnsrest.logger import init_logger, log

RE_VALIDNAME = re.compile('[^\w\d.-]')


Container = namedtuple('Container', 'id, name, running, addrs')


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
            # If a container has been started by docker-compose, it is registered
            # under <service>.<project>.<domain>, as well as under <name>.<domain>.
            for rec in self._inspect(container['Id'], container):
                if rec.running:
                    self._registry.add('name:/' + rec.name, [DNSLabel(rec.name)])
                    self._registry.activate(rec)

        # read the docker event stream and update the name table
        for raw in events:
            evt = json.loads(raw)

            # Looks like in Docker 1.10 we can get events of type "Network"
            # that I am assuming are a result of the new network features added in this release.
            # These network events cause dockerdn to crash. Let's just ignore them.
            if evt.get('Type', 'container') != 'container':
                print("Skipped event: " + str(evt))
                continue

            cid = evt.get('id')
            if cid is None:
                print ("Skipped event: " + str(evt))
                continue

            status = evt.get('status')
            if status not in ('start', 'die', 'rename'):
                print("Skipped event: " + str(evt))
                continue

            try:
                for rec in self._inspect(cid):
                    if status == 'start':
                        self._registry.add('name:/' + rec.name, [DNSLabel(rec.name)])
                        self._registry.activate(rec)

                    elif status == 'rename':
                        old_name = get(evt, 'Actor', 'Attributes', 'oldName')
                        new_name = get(evt, 'Actor', 'Attributes', 'name')
#                        old_name = '.'.join((old_name, self._domain))
#                        new_name = '.'.join((new_name, self._domain))
                        self._registry.rename(old_name, new_name)

                    else:
                        self._registry.deactivate(rec)
            except Exception as e:
                log('Error: %s', e)

    def _get_names(self, name, labels):
        names = [RE_VALIDNAME.sub('', name).rstrip('.')]

        labels = labels or {}
        instance = int(labels.get('com.docker.compose.container-number', 1))
        service = labels.get('com.docker.compose.service')
        project = labels.get('com.docker.compose.project')

        if all((instance, service, project)):
            names.append('%d.%s.%s' % (instance, service, project))

            # the first instance of a service is available without number
            # prefix
            if instance == 1:
                names.append('%s.%s' % (service, project))

        return ['.'.join((name, self._domain)) for name in names]

    def _inspect(self, cid, data):
        # get full details on this container from docker
        rec = self._docker.inspect_container(cid)

        id = get(rec, 'Id')

        labels = get(rec, 'Config', 'Labels')

        state = get(rec, 'State', 'Running')

        # ensure name is valid, and append our domain
        name = get(rec, 'Name')
        if not name:
            return None
#        name = RE_VALIDNAME.sub('', name).rstrip('.')

        # commented since phensley/docker-dns/commit/1ee3a2525f58881c52ed50e849ab5b7e43f56ec3
#        name += '.' + self._domain

        networks = get(rec, 'NetworkSettings', 'Networks')
        ipaddress = [value['IPAddress'] for value in networks.values()]

#        # default
#        ipaddress = [get(rec, 'NetworkSettings', 'IPAddress')]
#
#        # fallback in case of docker-compose with custom network
#        if not ipaddress:
#            network = get(data, 'HostConfig', 'NetworkMode')
#            ipaddress = get(data, 'NetworkSettings', 'Networks', network, 'IPAddress')

        if not ipaddress:
            raise Exception("Unable to retrieve container ip address - %s" % cid)

        # TODO: what if we have a container connected in multiple networks?

        # 'id, name, running, addr'
        return [Container(id, name, state, ipaddress) for name in self._get_names(name, labels)]
