# python 3 compatibility
from __future__ import print_function
from future import standard_library

standard_library.install_aliases()
from builtins import str

# libs
from dnslib import A, DNSHeader, DNSRecord, QTYPE, RR
from gevent.resolver_ares import Resolver
from gevent.server import DatagramServer

from logger import log

DNS_RESOLVER_TIMEOUT = 3.0


def contains(txt, *subs):
    return any(s in txt for s in subs)


class DnsServer(DatagramServer):
    """
    Answers DNS queries against the registry, falling back to the recursive
    resolver (if present).
    """

    def __init__(self, bindaddr, registry, dns_servers=None):
        DatagramServer.__init__(self, bindaddr)
        self._registry = registry
        self._resolver = None
        if dns_servers:
            log.info("[namesrv] starting with failover resolver %s", dns_servers)
            self._resolver = Resolver(servers=dns_servers,
                                      timeout=DNS_RESOLVER_TIMEOUT, tries=1)

    def handle(self, data, peer):
        rec = DNSRecord.parse(data)
        addrs = None
        auth = False
        if rec.q.qtype in (QTYPE.A, QTYPE.AAAA, QTYPE.ANY):
            addrs = self._registry.resolve(rec.q.qname.idna()) or set()

            if addrs:
                auth = True

                # answer AAAA queries for existing A records
                # with an successful but empty result
                if rec.q.qtype == QTYPE.AAAA:
                    addrs = None
                else:
                    log.debug("[namesrv] resolved %s to %s", rec.q.qname.idna(), addrs)
            else:
                addr = self._resolve('.'.join(rec.q.qname.label))
                if addr:
                    addrs.add(addr)
                    log.debug("[namesrv] externally resolved %s to %s", rec.q.qname.idna(), addrs)

            if addrs:
                addrs = list(addrs)

        self.socket.sendto(self._reply(rec, auth, addrs), peer)

    def _reply(self, rec, auth, addrs=None):
        reply = DNSRecord(DNSHeader(id=rec.header.id, qr=1, aa=auth, ra=bool(self._resolver)), q=rec.q)
        if addrs:
            if not isinstance(addrs, list):
                addrs = [addrs]

            for addr in addrs[0:15]:
                reply.add_answer(RR(rec.q.qname, QTYPE.A, rdata=A(addr)))

        return reply.pack()

    def _resolve(self, name):
        if not self._resolver:
            log.info("DnsServer._resolve is not set")
            return None

        try:
            return self._resolver.gethostbyname(name)
        except Exception as e:
            # socket.gaierror as e:
            if not contains(str(e), 'ETIMEOUT', 'ENOTFOUND'):
                log.error("Exception in DnsServer._resolve", e)
            return None
