
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
from dnsrest.registry import PREFIX_NAME

init_logger("test", False, True)

TEST_KEY = "containera"
TEST_KEY2 = "containerb"
TEST_NAMES = ["foo", "foo.docker"]
TEST_ID = "0123456"
TEST_NAME = TEST_KEY
TEST_NAMES2 = [DNSLabel(name) for name in TEST_NAMES]
TEST_ADDR = "127.0.0.11"
TEST_ADDRS = [TEST_ADDR]
TEST_DOMAIN = "docker"


class RegistryTest(unittest.TestCase):

    def test_mapping(self):
        """
        base test for Mapping class
        """
        mapping = Mapping(TEST_KEY, TEST_NAMES)

        self.assertEquals(mapping.key, TEST_KEY)
        self.assertEquals(mapping.names, TEST_NAMES)
        self.assertIsNotNone(str(mapping))

    def test_container(self):
        """
        base test for Container class
        """
        foo = object()
        foo.id = TEST_ID
        foo.name = TEST_NAME
        foo.addrs = TEST_ADDRS

        container = Container(foo)

        self.assertEquals(container.id, TEST_ID)
        self.assertEquals(container.name, TEST_NAME)
        self.assertEquals(container.addrs, TEST_ADDRS)
        self.assertIsNotNone(str(container))

    def test_registry_base_class(self):
        """
        test Registry generic methods
        """

        reg = Registry()

        self.assertIsNotNone(str(reg))
        self.assertIsNotNone(reg.dump())

    def test_registry_domains(self):
        """
        test activate / deactivate functionality:
        this is to map a domain name to a particular address
        you can inspect the DNS tree with print(reg.dump())
        """

        reg = Registry()

        for domainName in TEST_NAMES:
            self.assertIsNone(reg._domains.get(domainName))

        log.info("Adding %s", TEST_ADDR)
        reg._activate(TEST_NAMES2, TEST_ADDR, TEST_KEY)
        for domainName in TEST_NAMES:
            self.assertIsNotNone(reg._domains.get(domainName))

        log.info("Removing %s", TEST_ADDR)
        reg._deactivate(TEST_NAMES2, TEST_ADDR, TEST_KEY)
        log.debug(reg.dump())
        for domainName in TEST_NAMES:
            log.debug("name %s", domainName)
            self.assertIsNone(reg._domains.get(domainName))

    def test_registry_mappings(self):
        """
        test add / remove functionality:
        this is to map a container name/id to a set of domain names
        """

        reg = Registry()

        log.info("Adding mapping %s => %s", TEST_KEY, TEST_NAMES)
        reg.add(PREFIX_NAME + TEST_KEY, TEST_NAMES)
        self.assertIsNotNone(reg._mappings.get(PREFIX_NAME + TEST_KEY))

        log.info("Removing mapping %s => %s", TEST_KEY, TEST_NAMES)
        reg.remove(PREFIX_NAME + TEST_KEY)
        self.assertIsNone(reg._mappings.get(PREFIX_NAME + TEST_KEY))

    def test_registry_mappings_get(self):
        """
        test get functionality:
        this is to get a list of dns domain mapped
        to the specified key (container id / name)
        """

        reg = Registry()

        log.info("Removing mapping %s => %s", TEST_KEY, TEST_NAMES)
        names = reg.get(PREFIX_NAME + TEST_KEY)
        self.assertEqual([], names)

        log.info("Adding mapping %s => %s", TEST_KEY, TEST_NAMES)
        reg.add(PREFIX_NAME + TEST_KEY, TEST_NAMES)
        names = reg.get(PREFIX_NAME + TEST_KEY)
        self.assertEqual(TEST_NAMES, names)

    def test_registry_domains_static(self):
        """
        test activate_static / deactivate_static functionality:
        this is to map a domain name to a particular address
        through the REST Api
        """

        reg = Registry()

        for domainName in TEST_NAMES:
            self.assertIsNone(reg._domains.get(domainName))

        log.info("Adding static %s", TEST_ADDR)
        reg.activate_static(TEST_NAMES2[0], TEST_ADDR)
        self.assertIsNotNone(reg._domains.get(TEST_NAMES[0]))

        log.info("Removing static %s", TEST_ADDR)
        reg.deactivate_static(TEST_NAMES2[0], TEST_ADDR)
        log.debug(reg.dump())
        self.assertIsNone(reg._domains.get(TEST_NAMES[0]))

    def test_registry_active(self):
        """
        test activate / deactivate functionality:
        this is to activate / deactivate all mapping
        related to the specified container
        """

        reg = Registry()

        foo = object()
        foo.id = TEST_ID
        foo.name = TEST_NAME
        foo.addrs = TEST_ADDRS
        container = Container(foo)

        self.assertIsNone(reg._active.get(container.id))

        log.info("Activating container %s", container.name)
        reg.activate(container)
        self.assertIsNotNone(reg._active.get(container.id))

        log.info("Deactivating container %s", container.name)
        reg.deactivate(container)
        self.assertIsNone(reg._active.get(container.id))

    def test_registry_resolve(self):
        """
        test resolve method
        """

        reg = Registry()

        log.info("Adding %s", TEST_ADDR)
        reg._activate(TEST_NAMES2, TEST_ADDR, TEST_KEY)

        for name in TEST_NAMES:
            addrs = reg.resolve(name)
            log.debug('resolve %s result %s', name, addrs)
            self.assertIsNotNone(addrs)
            self.assertEqual(addrs, [TEST_ADDR])

        addrs = reg.resolve("foo.it")
        self.assertIsNone(addrs)

    def test_mapping_rename(self):
        """
        test rename functionality:
        this is to update mapping when a container change name
        """

        reg = Registry()

        self.assertIsNone(reg._mappings.get(PREFIX_NAME + TEST_KEY))
        self.assertIsNone(reg._mappings.get(PREFIX_NAME + TEST_KEY2))

        log.info("Adding mapping %s => %s", TEST_KEY, TEST_NAMES)
        reg.add(PREFIX_NAME + TEST_KEY, TEST_NAMES)
#        log.debug('_mapping %s' % reg._mappings)
        self.assertIsNotNone(reg._mappings.get(PREFIX_NAME + TEST_KEY))
        self.assertIsNone(reg._mappings.get(PREFIX_NAME + TEST_KEY2))

        log.info("Removing mapping %s => %s", TEST_KEY, TEST_NAMES)
        reg.rename(TEST_KEY, TEST_KEY2)
        self.assertIsNone(reg._mappings.get(PREFIX_NAME + TEST_KEY))
        self.assertIsNotNone(reg._mappings.get(PREFIX_NAME + TEST_KEY2))

    def test_domain(self):
        """
        test suffix domain functionality:
        """

        reg = Registry(TEST_DOMAIN)

        self.assertIsNone(reg._mappings.get(PREFIX_NAME + TEST_KEY + "." + TEST_DOMAIN))
        self.assertIsNone(reg._mappings.get(PREFIX_NAME + TEST_KEY2 + "." + TEST_DOMAIN))

        log.info("Adding mapping %s => %s", TEST_KEY, TEST_NAMES)
        reg.add(PREFIX_NAME + TEST_KEY, TEST_NAMES)
        log.debug('_mapping %s' % reg._mappings)
        self.assertIsNotNone(reg._mappings.get(PREFIX_NAME + TEST_KEY + "." + TEST_DOMAIN))
        self.assertIsNone(reg._mappings.get(PREFIX_NAME + TEST_KEY2 + "." + TEST_DOMAIN))

        log.info("Removing mapping %s => %s", TEST_KEY, TEST_NAMES)
        reg.rename(TEST_KEY, TEST_KEY2)
        self.assertIsNone(reg._mappings.get(PREFIX_NAME + TEST_KEY + "." + TEST_DOMAIN))
        self.assertIsNotNone(reg._mappings.get(PREFIX_NAME + TEST_KEY2 + "." + TEST_DOMAIN))


if __name__ == '__main__':
    unittest.main()
