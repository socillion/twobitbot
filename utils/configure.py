#!/usr/bin/env python

import logging
import os
import time

import configobj
import validate

from twisted.python.log import PythonLoggingObserver, ILogObserver

log = logging.getLogger(__name__)


def load_config():
    """
    Load and validate configuration.

    :return: configuration
    :rtype: configobj.ConfigObj
    :raise IOError: if there is an issue reading the configuration file
    """
    # todo arbitrary config files
    # http://www.voidspace.org.uk/python/configobj.html
    # http://www.voidspace.org.uk/python/validate.html
    if os.path.exists('bot.ini'):
        config = configobj.ConfigObj('bot.ini', configspec='confspec.ini')
        log.info("Using config file bot.ini")
    elif os.path.exists('default.ini'):
        config = configobj.ConfigObj('default.ini', configspec='confspec.ini')
        log.info("Using config file default.ini")
    else:
        raise IOError("Could not find config file for bot")

    # validate config now
    val = validate.Validator()
    results = config.validate(val, preserve_errors=True)
    if not results:
        for (section_list, key, reason) in configobj.flatten_errors(config, results):
            if key:
                msg = "CONFIG ERROR: key '%s' in section '%s' failed validation" % (key, ', '.join(section_list))
                if reason:
                    msg += " - %s" % (reason)
                log.error(msg)
            else:
                log.error("CONFIG ERROR: missing section '%s'" % ', '.join(section_list))
        raise IOError("Errors in bot config file")

    return config


def setup_logs(application=None):
    """
    Configure logging for the bot.
    :param application: an application object, if using twistd
    :type application: service.Application
    """
    # todo arbitrary logging file
    obs = PythonLoggingObserver()
    if not application:
        obs.start()
    else:
        application.setComponent(ILogObserver, obs.emit)

    root_logger = logging.getLogger()

    root_logger.setLevel(logging.DEBUG)
    logging.getLogger('twistedpusher.client').setLevel(logging.INFO)

    file_lf = logging.Formatter("%(asctime)s %(levelname)-8s [%(name)s] %(message)s")
    file_lf.converter = time.gmtime
    file_h = logging.FileHandler('bot.log')
    file_h.setFormatter(file_lf)
    root_logger.addHandler(file_h)

    console_lf = logging.Formatter("%(levelname)-8s [%(name)s] %(message)s")
    console_h = logging.StreamHandler()
    console_h.setFormatter(console_lf)
    root_logger.addHandler(console_h)