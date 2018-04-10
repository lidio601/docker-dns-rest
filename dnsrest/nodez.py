
# python 3 compatibility
from __future__ import print_function
from future import standard_library
from functools import reduce
standard_library.install_aliases()
from builtins import map
from builtins import str
from builtins import object

# code
from collections import defaultdict, namedtuple

# libs
from dnslib import DNSLabel

NodeLink = namedtuple('NodeLink', 'ipaddress, tag')


class Node(object):
    """
    Stores a tree of domain names with wildcard support
    """

    def __init__(self):
        self._subs = defaultdict()
        self._wildcard = False
        self._addr = []
        self._addr_index = 0

    """
    Main methods
    """

    def get(self, name):
        res = self._get(Node._label(name))

        if res:
            res = [tuple(link) for link in res]

        return res

    def put(self, name, addr, tag=None):
        return self._put(Node._label(name), addr, tag)

    def remove(self, name, tag=None, addr=None):
        return self._remove(Node._label(name), addr, tag)

    def to_dict(self):
        r = defaultdict()

        r[':addr'] = [list(link) for link in self._addr]
        r[':wildcard'] = self._wildcard

        for key, sub in list(self._subs.items()):
            r[key] = sub.to_dict()

        return r

    """
    Private methods
    """

    @staticmethod
    def _label(name):
        return list(DNSLabel(name).label)

    def _get(self, label):

        # recurse over sub domains
        if label:
            part = label.pop()
            sub = self._subs.get(part)
            if sub:
                res = sub._get(label)
                if res:
                    return res

#        if not self._wildcard:
#            return None

        if len(self._addr) == 0:
            return None

        self._addr_index += 1
        self._addr_index %= len(self._addr)

        return self._addr[self._addr_index:] + self._addr[:self._addr_index]

    def _put(self, label, addr, tag=None):
        part = label.pop()
        link = NodeLink(addr, tag)

        if part == '*':
            self._wildcard = True
            self._addr.append(link)
            return

        sub = self._subs.get(part)
        if sub is None:
            sub = Node()
            self._subs[part] = sub

        if not label:
            sub._addr.append(link)
            return

        sub._put(label, addr, tag)

    def _remove(self, label, addr=None, tag=None):
        part = label.pop()
        sub = self._subs.get(part)
        if not label:
            if part == '*':
                tagged = self._tagged_addr(self._addr, tag)
                addr = tagged if not addr else addr
                self._addr = [(a, t) for a, t in self._addr if a not in addr]
                self._wildcard = False if not self._addr else True
                return tagged
            elif sub:
                tagged = self._tagged_addr(sub._addr, tag)
                addr = tagged if not addr else addr
                sub._addr = [(a, t) for a, t in sub._addr if a not in addr]
                return tagged
        elif sub:
            sub._remove(label, addr, tag)
            if sub and sub._is_empty():
                del self._subs[part]

        return []

    def _is_empty(self):
        return not self._subs and not self._addr

    def _tagged_addr(self, addr, tag):
        return set([a for a, t in addr if t == tag or tag is None])
