#!/usr/bin/env python

import logging
import sys

from twisted.internet import reactor, stdio
from twisted.protocols import basic

from twobitbot.utils import configure
from twobitbot.botresponder import BotResponder
from twobitbot.bitstampwatcher import BitstampWatcher

log = logging.getLogger("termbot")

# Terminal environment for testing
# Resources:
# https://twistedmatrix.com/documents/current/core/examples/stdiodemo.py
# https://twistedmatrix.com/documents/current/core/examples/stdin.py


###########################################
##### NEEDS PATCH TO WORK ON WINDOWS:
##### http://stackoverflow.com/a/14332475
###########################################


class TerminalBot(basic.LineReceiver):
    delimiter = '\n'

    def __init__(self, config):
        self.config = config
        self.watcher = BitstampWatcher()
        self.watcher.add_alert_callback(self.out)
        self.responder = BotResponder(self.config, self.watcher)

    def connectionMade(self):
        print("Welcome! This should work if you aren't using Windows.")

    def lineReceived(self, line):
        response = self.responder.dispatch(line)
        if response:
            self.out(response)

    def out(self, line):
        self.sendLine(line)


def main():
    configure.setup_logs()

    try:
        config = configure.load_config()
    except IOError as e:
        log.critical("Aborting, problem loading config: {0}".format(e), exc_info=True)
        sys.exit(1)

    bot = TerminalBot(config)
    stdio.StandardIO(bot)

    reactor.run()



if __name__ == '__main__':
    main()
