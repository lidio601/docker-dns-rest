# python 3 compatibility
from __future__ import print_function
from future import standard_library
standard_library.install_aliases()
from builtins import object

# core
from datetime import datetime
import sys


class Logger(object):
    """
    Shared Logger class
    """

    def __init__(self):
        self._process = sys.argv[0]
        self._quiet   = False
        self._verbose = False

    def set_process_name(self, name):
        self._process = name

    def set_quiet(self, quiet):
        self._quiet = True if quiet else False

    def set_verbose(self, verbose):
        self._verbose = True if verbose else False

    def info(self, msg, *args):
        if not self._quiet:
            self._log(msg, *args)

    def debug(self, msg, *args):
        if not self._quiet and self._verbose:
            self._log(msg, *args)

    def error(self, msg, *args):
        self._log(msg, *args)

    def _log(self, msg, *args):
        now = datetime.now().isoformat()
        line = u'%s [%s] %s\n' % (now, self._process, msg % args)
        sys.stderr.write(line)
        sys.stderr.flush()


# global instance
log = Logger()


def init_logger(process=None, quiet=True, verbose=True, logger=log):
    """
    Setup global instance
    """
    if process:
        logger.set_process_name(process)
    if quiet:
        logger.set_quiet(quiet)
    if verbose:
        logger.set_verbose(verbose)
