
# python 3 compatibility
from __future__ import print_function
from future import standard_library
from functools import reduce
standard_library.install_aliases()
from builtins import map
from builtins import str
from builtins import object

# core
from collections import defaultdict
import json

# libs
from gevent import threading

# local
from logger import log
from nodez import Node


class Mapping(object):
    """
    Mapping to link a key to a list of domain names
    A key can be:
    - name:/%s
    - id:/%s
    """
    key = None
    names = []

    def __init__(self, key, names):
        self.key = key
        self.names = [names] if not isinstance(names, list) else names

    def __str__(self):
        return "map %s => %s" % (self.key, self.names)


class Container(object):
    """
    A custom representation of the container data
    coming from Docker api
    """
    id = None
    name = None
    addrs = []

    def __init__(self, container=None):
        if container:
            self.id = container.id
            self.name = container.name
            self.addrs = container.addrs

    def __str__(self):
        return '%s (%s)' % (self.name, self.id[:10] if self.id else None)


class Registry(object):
    """
    Maps a container by id/name to a list of domain names and addresses.
    When the container is started, the list of domain names can be activated,
    and when the container is stopped the list of domain names can be
    deactivated.
    """

    def __init__(self, domain=None):
        self._mappings = defaultdict(set)
        self._active = defaultdict()
        self._domains = Node()
        self._lock = threading.Lock()
        self._domain = domain.lstrip('.') if domain else None

    def __str__(self):
        return json.dumps(self._domains.to_dict(), indent=4, sort_keys=1)

    def dump(self):
        return str(self)

    def _activate(self, names, addr, tag=None):
        # ensure that is a list of addr
        addrs = [addr] if not isinstance(addr, list) else addr

        for name in names:
            for addr in addrs:
                log.info('added %s -> %s key=%s', name.idna(), addr, tag)
                self._domains.put(name, addr, tag)
#        log.debug('tree %s' % self.dump())

    def _deactivate(self, names, addr=None, tag=None):
        # ensure that is a list of addr
        addrs = [addr] if not isinstance(addr, list) else addr

        for name in names:
            if self._domains.get(name):
                addrs = self._domains.remove(name, tag, addrs)
                log.info('removing domains %s -> %s key = %s', name.idna(), addrs, tag)

                if addrs:
                    for addr in addrs:
                        log.info('removed %s -> %s', name.idna(), addr)
#        log.debug('tree %s', self.dump())

    def _get_mapping_by_container(self, container):
        """
        try name and id-based keys
        :param Container container:
        :return:
        """

        # try matching by name
        res = self._mappings.get('name:/%s' % container.name)

        if not res:
            # try matching by id
            res = self._mappings.get('id:/%s' % container.id)

        return res

    def remove(self, key):
        with self._lock:
            old_mapping = self._mappings.get(key)

            if old_mapping:
                log.info('table.remove %s' % old_mapping)
                self._deactivate(old_mapping.names, tag=old_mapping.key)
                self._mappings.pop(old_mapping.key)

    def add(self, key, names):
        """
        Adds a mapping from the given key to a list of names. The names
        will be registered when the container is activated (running) and
        unregistered when the container is deactivated (stopped).
        """

        # first, remove the old names, if any
        self.remove(key)

        with self._lock:
            # persist the mappings
            self._mappings[key] = Mapping(key, names)

            # check if these pertain to any already-active
            # containers and activate the domain names
            for container in list(self._active.items()):
                """
                :var Container container
                """
                if key in ('name:/' + container.name, 'id:/' + container.id):
                    for addr in container.addrs:
                        self._activate(names, addr, tag=key)

    def get(self, key):
        with self._lock:
            mapping = self._mappings.get(key)

            if not mapping:
                log.debug('table.get %s with NoneType' % key)
            else:
                log.info('table.get %s with %s' % (mapping, ", ".join(addr for addr in mapping)))

            if mapping:
                return [n.idna().rstrip('.') for n in mapping.names]

            return []

    def activate_static(self, domain, addr):
        with self._lock:
            log.info('table.activate %s with %s' % (domain, addr))
            self._activate([domain], addr, tag='domain:/%s' % domain)

    def deactivate_static(self, domain, addr):
        with self._lock:
            log.info('table.deactivate %s with %s' % (domain, addr))
            self._deactivate([domain], addr, tag='domain:/%s' % domain)

    def activate(self, container):
        """
        Activate all rules associated with this container
        :param Container container:
        :return:
        """
        with self._lock:
            self._active[container.id] = container

            mapping = self._get_mapping_by_container(container)
            if mapping:
                log.info('setting %s as active' % container)

                key, names = mapping.key, mapping.names
                for addr in container.addrs:
                    self._activate(names, addr, tag=key)

    def deactivate(self, container):
        """
        Deactivate all rules associated with this container
        :param Container container:
        :return:
        """
        with self._lock:
            old_container = self._active.get(container.id)

            if old_container is None:
                return
            else:
                del self._active[container.id]

            # since this container is active, get the old address
            # so we can log exactly which names/addresses
            # are being deactivated
            mapping = self._get_mapping_by_container(container)
            if mapping:
                log.info('setting %s as inactive' % container)
                self._deactivate(mapping.names, tag=mapping.key)

    def resolve(self, name):
        """
        Resolves the address for this name, if any
        :param name:
        :return:
        """
        with self._lock:
            res = self._domains.get(name)
            if res:
                addrs = [a for a, _ in res]
                log.debug('resolved %s -> %s' % (name, ', '.join(addrs)))
                return addrs
            else:
                log.debug('no mapping for %s' % name)

    #
    # Support container renames, newer Docker API versions.
    #
    def rename(self, old_name, new_name):
        if not old_name or not new_name:
            return

        old_name = old_name.lstrip('/')

        old_name = '.'.join((old_name, self._domain))
        new_name = '.'.join((new_name, self._domain))

        old_key = 'name:/%s' % old_name
        new_key = 'name:/%s' % new_name

        with self._lock:
            mapping = self._mappings.pop(old_key)

            if mapping:
                mapping.key = new_key
                self._mappings[new_key] = mapping
                log('renamed (%s -> %s) == %s', old_name, new_name, mapping)
