
# python 3 compatibility
from __future__ import print_function
from future import standard_library
from functools import reduce
standard_library.install_aliases()
from builtins import object

# core
from collections import namedtuple
from dnslib import DNSLabel
import json
import re

# local
from dnsrest.logger import log
from dnsrest.registry import PREFIX_NAME

RE_VALIDNAME = re.compile('[^\w\d.-]')
RE_ENVVAR = re.compile('(.*)=(.*)')

Container = namedtuple('Container', 'id, name, running, addrs, names')


def get(d, *keys):
    empty = {}
    return reduce(lambda d, k: d.get(k, empty), keys, d) or None


class DockerMonitor(object):
    """
    Reads events from Docker and activates/deactivates container domain names
    """

    def __init__(self, client, registry, domain=None):
        self._docker = client
        self._registry = registry
        self._domain = domain.lstrip('.') if domain else None

    def bootstrap(self):
        """
        At startup
        """
        containers = self._docker.containers()
        containers = list(containers)
        log.info("[monitor] [%d] containers found", len(containers))

        self._inspect_containers(containers)

    def run(self):
        """
        When new events are triggered within Docker
        we read those and update the registry
        """
        # start the event poller, but don't read from the stream yet
        events = self._docker.events()
        #events = list(events)
        #log.debug("[%d] events found", len(events))

        self._inspect_events(events)

    def _inspect_containers(self, containers):
        """
        inspect a list of containers
        and add the relative DNS records
        :param containers: list
        :return:
        """
        # bootstrap by activating all running containers
        for container in containers:
            try:
                # If a container has been started by docker-compose, it is registered
                # under <service>.<project>.<domain>, as well as under <name>.<domain>.
                # get full details on this container from docker
                record = self._docker.inspect_container(container['Id'])

                dnsrecords = self._inspect(record, container)
            except Exception as e:
                log.error('[monitor] error: %s', e)
                continue

            log.debug("[monitor] [%d] dnsrecords found for container %s", len(dnsrecords), record)

            for rec in dnsrecords:
                log.debug("[monitor] adding map due to record %s\n%s",
                         rec, '\n'.join(["\t\t\t\t\t\t\t\t\t\t\t\t\t- %s -> %s" % (r.idna(), rec.name) for r in rec.names]))
                self._registry.add(self._registry.get_mapping_key(name=rec.name), rec.names)

                if rec.running:
                    log.debug("[monitor] activating map due to record %s\n%s",
                             rec, '\n'.join(["\t\t\t\t\t\t\t\t\t\t\t\t\t- %s -> %s" % (r.idna(), rec.name) for r in rec.names]))
                    self._registry.activate(rec)

    def _inspect_events(self, events):
        """
        When new events come from Docker
        :return:
        """
        # read the docker event stream and update the name table
        for raw in events:
            try:
                evt = json.loads(raw)
            except Exception as err:
                log.error('[monitor] error while decoding Docker event: %s due %s', raw, err)

            # Looks like in Docker 1.10 we can get events of type "Network"
            # that I am assuming are a result of the new network features added in this release.
            # These network events cause dockerdn to crash. Let's just ignore them.
            etype = evt.get('Type', 'container')
            if etype != 'container':
                log.debug("[monitor] skipped event due wrong type: [type=%s] %s", evt.get('Type'), evt)
                continue

            cid = evt.get('id')
            if cid is None:
                log.debug("[monitor] skipped event due missing id: [type=%s] %s", evt.get('Type'), evt)
                continue

            status = evt.get('status')
            if status not in ('start', 'die', 'rename'):
                log.debug("[monitor] skipped event due wrong status: [status=%s] %s", evt.get('status'), evt)
                continue

            log.info("[monitor] got Docker event [type=%s] [status=%s] [cid=%s]", etype, status, cid)

            # get full details on this container from docker
            record = self._docker.inspect_container(cid)

            try:
                dnsrecords = self._inspect(record)
            except Exception as e:
                log.error('[monitor] error: %s', e)
                dnsrecords = []

            for rec in dnsrecords:
                if status == 'start':
                    self._registry.add('name:/' + rec.name, rec.names)
                    self._registry.activate(rec)

                elif status == 'rename':
                    old_name = get(evt, 'Actor', 'Attributes', 'oldName')
                    new_name = get(evt, 'Actor', 'Attributes', 'name')
                    self._registry.rename(old_name, new_name)

                elif status == 'die':
                    self._registry.deactivate(rec)

    def _get_names(self, name, labels):
        """
        Inspect the container
        :param name:
        :param labels:
        :return:
        """
        names = [RE_VALIDNAME.sub('', name).rstrip('.')]

        labels = labels or {}
        instance = int(labels.get('com.docker.compose.container-number', 1))
        service = labels.get('com.docker.compose.service')
        project = labels.get('com.docker.compose.project')

        if all((instance, service, project)):
            # If a container has been started by docker-compose, it is registered
            # under <service>.<project>.<domain>, as well as under <name>.<domain>.
            names.append('%d.%s.%s' % (instance, service, project))

            # the first instance of a service is available
            # without a number prefix
            if instance == 1:
                names.append('%s.%s' % (service, project))

        if self._domain:
            names = ['.'.join((name, self._domain)) for name in names]

        return names

    def _inspect(self, rec, data=None):
        id = get(rec, 'Id')

        envs = get(rec, 'Config', 'Env')

        # Support nginx-proxy VIRTUAL_HOST
        # environment variable to automatically
        # configure domains
        # VIRTUAL_HOST=foo.bar.com
        # VIRTUAL_HOST=*.bar.com
        virtualhosts = []
        try:
            for line in envs:
                match = RE_ENVVAR.match(line)
                if match and match.groups()[0] == "VIRTUAL_HOST":
                    virtualhosts = match.groups()[1].split(",")
                    virtualhosts = list(map(lambda x: x.strip() if x else x, virtualhosts))
                    break
        except Exception as e:
            log.error("[monitor] error while evaluating VIRTUAL_HOST env var due to %s", e)

        labels = get(rec, 'Config', 'Labels')

        state = get(rec, 'State', 'Running')

        # ensure name is valid, and append our domain
        name = get(rec, 'Name')
        if name:
            name = RE_VALIDNAME.sub('', name).rstrip('.')

        # commented since phensley/docker-dns/commit/1ee3a2525f58881c52ed50e849ab5b7e43f56ec3
        if self._domain:
            name = '.'.join((name, self._domain))

        ipaddress = None

        # try to support multiple ip addresses
        networks = get(rec, 'NetworkSettings', 'Networks')
        if networks:
            ipaddress = [value['IPAddress'] for value in networks.values()]

        # default
        if not ipaddress:
            ipaddress = get(rec, 'NetworkSettings', 'IPAddress')
            ipaddress = [ipaddress] if ipaddress else ipaddress

        # fallback in case of docker-compose with custom network
        if not ipaddress and data:
            network = get(data, 'HostConfig', 'NetworkMode')
            ipaddress = get(data, 'NetworkSettings', 'Networks', network, 'IPAddress')

        if not ipaddress:
            ipaddress = []
#            raise Exception("Unable to retrieve container ip address", cid)

        elif ipaddress is not list:
            ipaddress = [ipaddress]

        # TODO: what if we have a container connected in multiple networks?

        names = [DNSLabel(name)]
        if virtualhosts:
            names += [DNSLabel(hostname) for hostname in virtualhosts]

        # 'id, name, running, addr'
        return [Container(id, name, state, ipaddress, names) for name in self._get_names(name, labels)]
