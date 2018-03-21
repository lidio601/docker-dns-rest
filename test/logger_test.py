
# python 3 compatibility
from __future__ import print_function
from future import standard_library
standard_library.install_aliases()

# core
import unittest, sys, mock

from dnsrest.logger import Logger

PROCESS_NAME = "mytestproc"


class LoggerTest(unittest.TestCase):

    def test_default_values(self):
        log = Logger()
        self.assertEquals(log._process, sys.argv[0])
        self.assertFalse(log._quiet)
        self.assertFalse(log._verbose)

    def test_set_process_name(self):
        log = Logger()
        self.assertEquals(log._process, sys.argv[0])
        log.set_process_name(PROCESS_NAME)
        self.assertEquals(log._process, PROCESS_NAME)

    def test_set_quiet(self):
        log = Logger()
        self.assertFalse(log._quiet)
        self.assertFalse(log._verbose)

        log.set_quiet(True)
        self.assertTrue(log._quiet)
        self.assertFalse(log._verbose)

        log.set_quiet(False)
        self.assertFalse(log._quiet)
        self.assertFalse(log._verbose)

    def test_set_verbose(self):
        log = Logger()
        self.assertFalse(log._quiet)
        self.assertFalse(log._verbose)

        log.set_verbose(True)
        self.assertFalse(log._quiet)
        self.assertTrue(log._verbose)

        log.set_verbose(False)
        self.assertFalse(log._quiet)
        self.assertFalse(log._verbose)

    @mock.patch('sys.stderr.write')
    def test_info(self, mocker):
        log = Logger()

        log.set_quiet(True)
        self.assertTrue(log._quiet)
        self.assertFalse(log._verbose)

        log.info("test")
        sys.stderr.write.assert_not_called()

        log.set_quiet(False)
        self.assertFalse(log._quiet)
        self.assertFalse(log._verbose)

        log.info("test")
        sys.stderr.write.assert_called_once()

    @mock.patch('sys.stderr.write')
    def test_debug(self, mocker):
        log = Logger()

        log.set_verbose(False)
        log.set_quiet(False)
        self.assertFalse(log._verbose)
        self.assertFalse(log._quiet)

        log.debug("test")
        sys.stderr.write.assert_not_called()

        log.set_verbose(False)
        log.set_quiet(True)
        self.assertFalse(log._verbose)
        self.assertTrue(log._quiet)

        log.debug("test")
        sys.stderr.write.assert_not_called()

        log.set_verbose(True)
        log.set_quiet(True)
        self.assertTrue(log._verbose)
        self.assertTrue(log._quiet)

        log.debug("test")
        sys.stderr.write.assert_not_called()

        log.set_verbose(True)
        log.set_quiet(False)
        self.assertTrue(log._verbose)
        self.assertFalse(log._quiet)

        log.debug("test")
        sys.stderr.write.assert_called_once()


if __name__ == '__main__':
    unittest.main()
