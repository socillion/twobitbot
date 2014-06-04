#!/usr/bin/env python

import logging

from twisted.application import service
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet import reactor

from twobitbot.bot import TwoBitBotFactory
from twobitbot.utils import configure

log = logging.getLogger("twobitbot")


class BotSvc(service.Service):
    name = 'TwoBitBotService'

    def __init__(self, config=None):
        self.config = config
        self.irc = None

    def startService(self):
        if not self.config:
            try:
                self.config = configure.load_config()
            except IOError as e:
                log.critical("Problem loading config: {0}".format(e), exc_info=True)
        self.irc = TwoBitBotFactory(self.config)

        log.info("Starting bot service.")
        from twisted.internet import reactor
        # TODO ssl irc connection
        reactor.connectTCP(self.config['server'], self.config['server_port'], self.irc)

    def stopService(self):
        log.info("Stopping bot service.")


application = service.Application("TwoBitBot")
configure.setup_logs(application)


svc = BotSvc()
svc.setServiceParent(application)