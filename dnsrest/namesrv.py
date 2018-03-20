# libs
from dnslib import A, DNSHeader, DNSRecord, QTYPE, RR
from gevent import socket
from gevent.resolver_ares import Resolver
from gevent.server import DatagramServer

DNS_RESOLVER_TIMEOUT = 3.0


def contains(txt, *subs):
    return any(s in txt for s in subs)


class DnsServer(DatagramServer):
    '''
    Answers DNS queries against the registry, falling back to the recursive
    resolver (if present).
    '''

    def __init__(self, bindaddr, registry, dns_servers=None):
        DatagramServer.__init__(self, bindaddr)
        self._registry = registry
        self._resolver = None
        if dns_servers:
            self._resolver = Resolver(servers=dns_servers,
                                      timeout=DNS_RESOLVER_TIMEOUT, tries=1)

    def handle(self, data, peer):
        rec = DNSRecord.parse(data)
        addr = None
        auth = False
        if rec.q.qtype in (QTYPE.A, QTYPE.AAAA):
            addr = self._registry.resolve(rec.q.qname.idna())
            if addr:
                auth = True
            else:
                addr = self._resolve('.'.join(rec.q.qname.label))
        self.socket.sendto(self._reply(rec, auth, addr), peer)

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
            return None
        try:
            return self._resolver.gethostbyname(name)
        except socket.gaierror, e:
            msg = str(e)
            if not contains(msg, 'ETIMEOUT', 'ENOTFOUND'):
                print msg
