#!/usr/bin/env python

import logging
import sys

from twisted.internet import defer
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.words.protocols import irc

from twobitbot.bitstampwatcher import BitstampWatcher
from twobitbot.utils import ratelimit, configure
from twobitbot import botresponder


######## Get unicode in windows console
try:
    import utils.unicodeconsole
except ImportError:
    sys.exc_clear()
else:
    del utils.unicodeconsole
######################

# Here's a dilemma: why not use endpoints (e.g. TCP4ClientEndpoint) instead of connectTCP?
# Mostly because ReconnectingClientFactory is so damn nice. It might be great to eventually rewrite to use endpoints,
# but until it's 100% necessary I won't because it seems to be non-trivial to handle connectionLost.
# See http://stackoverflow.com/a/5447108
# <me> not sure how i'd handle reconnecting from the protocol
# <habnabit> you'd need to put that logic somewhere else. a connection manager object, for example
#
# factory.doStop()/.doStart maybe?

# todo clean shutdowns once again

# TODO: refactor to make passing around exchanges and configuration easier/better.
# TODO: Services
# TODO: rethink logging
# TODO: replace bitstampwatcher

# todo type/rtype for all methods/functions in all 3 projects
# see https://www.jetbrains.com/pycharm/webhelp/type-hinting-in-pycharm.html

# todo support for invite-only channels, maybe password-protected as well.
#####################

log = logging.getLogger("ircbot")


class TwoBitBotIRC(irc.IRCClient):
    def __init__(self, config):
        self.config = config

        self.bitstamp = BitstampWatcher(triggervolume=self.config['volume_alert_threshold'])
        self.channels = list()
        self.broadcast_to_channels = list()
        #self.broadcast_to_users = list()
        self.responder = botresponder.BotResponder(self.config, self.bitstamp)

    # todo this overwrites ircclient var
    @property
    def nickname(self):
        return self.config['botname']
    #nickname = property(_get_nickname)

    def signedOn(self):
        """Called upon connecting to the server successfully."""
        if 'freenode' in self.config['server'] and len(self.config['password']) > 0:
            self.msg('nickserv', 'identify %s' % (self.config['password']))
        try:
            for chan in self.config['channels']:
                self.join(chan)
        except TypeError:
            log.critical("Problem joining channels sepecified in config file", exc_info=True)

        log.info("Signed on as %s." % (self.nickname))
        self.bitstamp.add_alert_callback(self.broadcast_msg)
        # not really necessary
        self.responder.set_name(self.nickname)

    def joined(self, channel):
        """Called when we finish joining a channel."""
        log.info("Joined %s." % (channel))
        self.channels.append(channel)
        self.broadcast_to_channels.append(channel)

    @defer.inlineCallbacks
    def privmsg(self, user, channel, msg):
        """Called when a message is seen in PM or a channel."""
        userhost = user.rsplit('@', 1)[1]
        user = user.split('!', 1)[0]

        if channel == self.nickname:
            # message directed just to us
            respond_to = user
            in_str = 'privmsg'
        else:
            # message was sent to a channel
            respond_to = channel
            in_str = respond_to

        if self.can_reply(userhost):
            response = yield self.responder.dispatch(msg, user)
            if response:
                log.debug("RESPOND to %s@%s in %s with '%s'" % (user, userhost, in_str, response.encode("utf8")))
                self.msg(respond_to, response.encode("utf8"))
                self.responded_to_user(userhost)

    def broadcast_msg(self, msg):
        """Send msg to all interested parties (per config)."""
        log.debug("BROADCAST to %s: '%s'" % (', '.join(self.broadcast_to_channels), msg.encode("utf8")))
        for ch in self.broadcast_to_channels:
            self.msg(ch, msg.encode("utf8"))
        # send msg to all interested channels/users

    def can_reply(self, userhost):
        """Check if the user has been responded to recently.
        Parameter: userhost
        Return:
            True if user should not be responded to, otherwise False."""

        if userhost in self.config['privileged_users']:
            return True
        elif userhost in self.config['banned_users']:
            return False
        elif self.factory.ratelimiter.is_limited(userhost):
            return False
        else:
            return True

    def responded_to_user(self, userhost):
        """ Track when a user was replied to for ratelimiting.
        Parameter: userhost"""
        self.factory.ratelimiter.user_event_now(userhost)


class TwoBitBotFactory(ReconnectingClientFactory):
    protocol = TwoBitBotIRC

    def __init__(self, config):
        self.config = config
        self.ratelimiter = ratelimit.ExponentialRateLimiter(
            max_delay=self.config['max_command_usage_delay'], base_factor=2, reset_after=30*60)

    def buildProtocol(self, addr):
        proto = TwoBitBotIRC(self.config)
        proto.factory = self
        return proto

    def clientConnectionLost(self, connector, reason):
        log.warning("Lost connection: %s" % (reason))
        self.retry(connector)

    def clientConnectionFailed(self, connector, reason):
        log.error("Could not connect: %s" % (reason))
        self.retry(connector)


def main():
    configure.setup_logs()
    # load config
    try:
        config = configure.load_config()
    except IOError as e:
        log.critical("Aborting, problem loading config: {0}".format(e), exc_info=True)
        sys.exit(1)

    # def shutdown():
    #     # add shutdown calls here...
    # reactor.addSystemEventTrigger('before', 'shutdown', shutdown)

    from twisted.internet import reactor

    factory = TwoBitBotFactory(config)

    reactor.connectTCP(config['server'], config['server_port'], factory)
    reactor.run()


if __name__ == '__main__':
    main()
