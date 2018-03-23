
# python 3 compatibility
from __future__ import print_function
from future import standard_library
standard_library.install_aliases()

# core
import unittest, sys, mock
from builtins import object
from dnsrest.registry import Mapping, Container, Registry
from dnslib import DNSLabel

from dnsrest.logger import log, init_logger

init_logger("test", False, True)

TEST_KEY = "containera"
TEST_NAMES = ["foo", "foo.docker"]
TEST_ID = "0123456"
TEST_NAME = TEST_KEY
TEST_NAMES2 = [DNSLabel(name) for name in TEST_NAMES]
TEST_ADDR = "127.0.0.11"
TEST_ADDRS = [TEST_ADDR]


class RegistryTest(unittest.TestCase):

    def test_mapping(self):
        mapping = Mapping(TEST_KEY, TEST_NAMES)

        self.assertEquals(mapping.key, TEST_KEY)
        self.assertEquals(mapping.names, TEST_NAMES)
        self.assertIsNotNone(str(mapping))

    def test_container(self):
        foo = object()
        foo.id = TEST_ID
        foo.name = TEST_NAME
        foo.addrs = TEST_ADDRS
        container = Container(foo)

        self.assertEquals(container.id, TEST_ID)
        self.assertEquals(container.name, TEST_NAME)
        self.assertEquals(container.addrs, TEST_ADDRS)
        self.assertIsNotNone(str(container))

    def test_registry_base(self):
        reg = Registry()

        self.assertIsNotNone(str(reg))
        self.assertIsNotNone(reg.dump())

    def test_registry_activate(self):
        reg = Registry()

        for name in TEST_NAMES:
            self.assertIsNone(reg._domains.get(name))

        log.info("Adding %s" % TEST_ADDR)
        reg._activate(TEST_NAMES2, TEST_ADDR, TEST_KEY)
        for name in TEST_NAMES:
            self.assertIsNotNone(reg._domains.get(name))

        log.info("Removing %s" % TEST_ADDR)
        reg._deactivate(TEST_NAMES2, TEST_ADDR, TEST_KEY)
        print(reg.dump())
        for name in TEST_NAMES:
            print("name", name)
            self.assertIsNone(reg._domains.get(name))


if __name__ == '__main__':
    unittest.main()
