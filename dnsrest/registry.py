
# python 3 compatibility
from __future__ import print_function
from future import standard_library
from functools import reduce
standard_library.install_aliases()
from builtins import map
from builtins import str
from builtins import object

# core
import json

# libs
from gevent import threading

# local
from logger import log
from nodez import Node


class Mapping(object):

    def __init__(self, names, key):
        self.names = names
        self.key = key


class Registry(object):
    ''''
    Maps a container by id/name to a list of domain names and addresses.
    When the container is started, the list of domain names can be activated,
    and when the container is stopped the list of domain names can be
    deactivated.
    '''

    def __init__(self):
        self._mappings = {}
        self._active = {}
        self._domains = Node()
        self._lock = threading.Lock()

    def add(self, key, names):
        ''''
        Adds a mapping from the given key to a list of names. The names
        will be registered when the container is activated (running) and
        unregistered when the container is deactivated (stopped).
        '''
        # first, remove the old names, if any
        self.remove(key)

        with self._lock:
            # persist the mappings
            self._mappings[key] = Mapping(names, key)

            # check if these pertain to any already-active containers and
            # activate the domain names
            activate = []
            for container in self._active.itervalues():
                if key in ('name:/' + container.name, 'id:/' + container.id):
                    desc = self._desc(container)
                    self._activate(names, container.addr, tag=key)

    def get(self, key):
        with self._lock:
            mapping = self._mappings.get(key)
            if mapping:
                return [n.idna().rstrip('.') for n in mapping.names]
            return []

    def remove(self, key):
        with self._lock:
            old_mapping = self._mappings.get(key)
            if old_mapping:
                self._deactivate(old_mapping.names, tag=old_mapping.key)
                del self._mappings[old_mapping.key]

    def activate_static(self, domain, addr):
        with self._lock:
            self._activate([domain], addr, tag='domain:/%s' % domain)

    def deactivate_static(self, domain, addr):
        with self._lock:
            self._deactivate([domain], addr, tag='domain:/%s' % domain)

    def activate(self, container):
        'Activate all rules associated with this container'
        desc = self._desc(container)
        with self._lock:
            self._active[container.id] = container
            mapping = self._get_mapping_by_container(container)
            if mapping:
                log.info('setting %s as active' % desc)
                key, names = mapping.key, mapping.names
                self._activate(names, container.addr, tag=key)

    def deactivate(self, container):
        'Deactivate all rules associated with this container'
        with self._lock:
            old_container = self._active.get(container.id)
            if old_container is None:
                return
            del self._active[container.id]

            # since this container is active, get the old address so we can log
            # exactly which names/addresses are being deactivated
            desc = self._desc(container)
            mapping = self._get_mapping_by_container(container)
            if mapping:
                log.info('setting %s as inactive' % desc)
                self._deactivate(mapping.names, tag=mapping.key)

    def resolve(self, name):
        'Resolves the address for this name, if any'
        with self._lock:
            res = self._domains.get(name)
            if res:
                addrs = [a for a, _ in res]
                log.debug('resolved %s -> %s' % (name, ', '.join(addrs)))
                return addrs
            else:
                log.debug('no mapping for %s' % name)

    def dump(self):
        return json.dumps(self._domains.to_dict(), indent=4, sort_keys=1)

    def _activate(self, names, addr, tag=None):
        for name in names:
            self._domains.put(name, addr, tag)
            log.info('added %s -> %s key=%s', name.idna(), addr, tag)
        # log.debug('tree %s' % self.dump())

    def _deactivate(self, names, addr=None, tag=None):
        for name in names:
            if self._domains.get(name):
                addrs = self._domains.remove(name, addr, tag)
                if addrs:
                    for addr in addrs:
                        log.info('removed %s -> %s', name.idna(), addr)
        # log.debug('tree %s', self.dump())

    def _get_mapping_by_container(self, container):
        # try name and id-based keys
        res = self._mappings.get('name:/%s' % container.name)
        if not res:
            res = self._mappings.get('id:/%s' % container.id)
        return res

    def _desc(self, container):
        return '%s (%s)' % (container.name, container.id[:10])

    #
    # Support container renames, newer Docker API versions.
    #
    def rename(self, old_name, new_name):
        if not old_name or not new_name:
            return

        old_name = old_name.lstrip('/')
        old_key = 'name:/%s' % old_name
        with self._lock:
            mapping = self._mappings.get(old_key)
            if mapping:
                del self._mappings[old_key]
                new_key = 'name:/%s' % new_name
                self._mappings[new_key] = mapping
                log('renamed (%s -> %s) == %s', old_name, new_name, mapping)
