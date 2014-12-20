#!/usr/bin/env python

from twisted.internet import defer, threads

import logging
import datetime
from decimal import Decimal

from twobitbot import utils
from twobitbot.flair import FlairGame
from exchangelib import forex, bitfinex

log = logging.getLogger(__name__)


class BotResponder(object):
    def __init__(self, config, exchange_watcher):
        self.config = config
        self.exchange_watcher = exchange_watcher
        try:
            self.name = self.config['botname']
        except KeyError:
            self.name = None
        self.flair = FlairGame(self.exchange_watcher, db=self.config['flair_db'],
                               change_delay=self.config['flair_change_delay'])

        if self.config['wolfram_alpha_api_key']:
            import wolframalpha
            self.wolframalpha = wolframalpha.Client(self.config['wolfram_alpha_api_key'])
        else:
            self.wolframalpha = False
            """:type: wolframalpha.Client"""

        self.forex = forex.ForexConverterService(self.config['open_exchange_rates_app_id'])
        self.forex.startService()

        self.bfx_swap_data = dict()
        self.bfx_swap_data_time = None

    def set_name(self, nickname):
        self.name = nickname

    def dispatch(self, msg, user=''):
        """ Handle a received message, dispatching it to the appropriate command responder.
        Parameters:
            msg - received message (string)
            user - who sent the message
        Return value: response message (string/deferred)"""
        # dispatching inspired by https://twistedmatrix.com/documents/current/core/examples/stdiodemo.py
        msg = msg.strip()

        # all commands are delegated to methods starting with cmd_
        if msg.startswith(self.config['command_prefix']):
            args = msg.split()
            # remove the prefix
            args[0] = args[0][len(self.config['command_prefix']):]

            cmd = args[0].lower()
            args = args[1:]
            try:
                cmd_method = getattr(self, 'cmd_' + cmd)
            except AttributeError as e:
                log.debug('Invalid command {0} used by {1} with arguments {2}'.format(cmd, user, args))
            else:
                try:
                    return cmd_method(user, *args)
                except TypeError as e:
                    log.warn('Issue dispatching {0} for {1} (cmd={2}, args={3}'.format(cmd_method, user, cmd, args),
                             exc_info=True)

    def cmd_donate(self, user=None):
        return "Bitcoin donations accepted at %s." % (self.config['btc_donation_addr'])

    def cmd_help(self, user=None):
        # todo update help stuff
        return ("Commands: {0}time <location>, {0}flair <long|fiat|short>, {0}flair status [user], {0}flair top, "
                "{0}forex <conversion>, {0}wolfram <query>, {0}swaps").format(self.config['command_prefix'])

    @defer.inlineCallbacks
    def cmd_time(self, user, *msg):
        # small usability change since users sometimes misuse this
        # command as "!time in X" instead of "!time X"
        if len(msg) >= 2 and msg[0] == 'in':
            msg = tuple(msg[1:])

        location = ' '.join(msg)
        if len(location) <= 1:
            defer.returnValue(None)
        log.info("Looking up current time in '%s' for %s" % (location, user))

        localized = yield utils.lookup_localized_time(location, datetime.datetime.utcnow(),
                                                      self.config['google_api_key'])
        if localized:
            defer.returnValue("The time in %s is %s" %
                              (localized['location'],
                               utils.format_time(localized['time'])))
        else:
            defer.returnValue("Invalid location.")

    @defer.inlineCallbacks
    def cmd_math(self, user, *msg):
        # todo:
        # - fucks up unicode (try "!math price of 1 bitcoin")
        # - messes up multi line output (try "!math licks to get to the center of a tootsie pop")
        # - works on website but not API (try "!math price of gas in portland oregon")
        #       fails for 'pi'...
        # another broken one: 'weather in denver colorado'. Works on website.
        # OK. looks like I just can't use .results, see
        # https://api.wolframalpha.com/v2/query?appid=PT5W9R-HUPGU4U33P&input=pi
        # Would have to ignore 'Identity' pod...
        # todo consider stripping newlines in some cases, e.g. the temperature queries, where its 2 very short lines
        if not self.wolframalpha:
            log.warn("Could not respond to a !math or !wolfram command because no Wolfram Alpha API key is set")
            defer.returnValue(None)
        else:
            user_query = ' '.join(msg)
            log.info("Querying Wolfram Alpha with '{}' for '{}'".format(user_query, user))
            response = yield threads.deferToThread(self.wolframalpha.query, user_query)

            answer = next(response.results, '')
            answer = answer.text.strip() if answer else "I don't know what you mean."
            # todo replace this unicode literal with unicode_literal future import
            defer.returnValue(u"{}: {}".format(user, answer))

    def cmd_wolfram(self, user, *msg):
        return self.cmd_math(user, *msg)

    def cmd_forex(self, user, *msg):
        # todo consider accepting queries like !fx xau where the usd part of xauusd is just implicit
        if len(msg) == 1 and len(msg[0]) == 6:
            # has to be an invocation like !forex cnyusd
            amount = 1
            from_currency = msg[0][:3]
            to_currency = msg[0][3:]
        elif len(msg) == 2 and len(msg[1]) == 6:
            # has to be an invocation like !forex 2345 eurusd
            amount = msg[0]
            from_currency = msg[1][:3]
            to_currency = msg[1][3:]
        elif len(msg) == 4 and msg[2].lower() == 'to':
            # has to be an invocation like !forex 123 cny to usd
            amount = msg[0]
            from_currency = msg[1]
            to_currency = msg[3]
        elif len(msg) == 0:
            # spit out help message
            # todo update help msg
            return ("ECB forex rates, updated daily. Usage: "
                    "{0}forex cnyusd, {0}forex 5000 mxneur, {0}forex 9001 eur to usd.").format(
                        self.config['command_prefix'])
        else:
            # unsupported usage
            return

        if from_currency == to_currency:
            return

        try:
            converted = self.forex.convert(amount, from_currency, to_currency)
        except ValueError as e:
            log.info('Forex conversion issue: {}'.format(e.message))
        else:
            if converted <= 1e-4 or converted >= 1e20:
                # These are arbitrary but at least the upper cap is 100% required to avoid situations like
                # !forex 10e23892348 RUBUSD which DDoS the bot and then the channel once it finally prints it.
                return None
            amount_str = utils.truncatefloat(Decimal(amount), decimals=5, commas=True)
            converted_str = utils.truncatefloat(converted, decimals=5, commas=True)
            # todo display info on data source
            return "{} {} is {} {}".format(amount_str, from_currency.upper(), converted_str, to_currency.upper())

    def cmd_fx(self, *msg):
        return self.cmd_forex(*msg)

    def cmd_flair(self, user, *msg):
        if len(msg) == 0:
            log.info("No flair subcommand specified, so returning %s's flair stats." % (user))
            return self.flair.status(user)

        cmd = msg[0]

        if cmd == 'status':
            target = user
            if len(msg) > 1:
                target = msg[1]
                log.info("Returning %s's flair stats for %s" % (target, user))
            else:
                log.info("Returning %s's flair stats" % (user))
            return self.flair.status(target)
        elif cmd == 'top':
            log.info("Returning top flair user statistics for %s" % (user))
            return self.flair.top(count=self.config['flair_top_list_size'])
        else:
#        elif cmd == 'bull' or cmd == 'bear':
            log.info("Attempting to change %s's flair to %s" % (user, cmd))
            return self.flair.change(user, cmd)

    @defer.inlineCallbacks
    def cmd_swaps(self, user, *msg):
        if not self.bfx_swap_data_time or utils.now_in_utc_secs() - self.bfx_swap_data_time > 5*30:
            self.bfx_swap_data = dict()
            # 2 for loops here so all 3 requests get sent ASAP
            for currency in ('usd', 'btc', 'ltc'):
                self.bfx_swap_data[currency] = bitfinex.lends(currency)
            for c, d in self.bfx_swap_data.iteritems():
                self.bfx_swap_data[c] = yield d
            self.bfx_swap_data_time = utils.now_in_utc_secs()
        swap_data = {}
        swap_data_strs = list()
        for currency in self.bfx_swap_data.iterkeys():
            swap_data[currency] = Decimal(self.bfx_swap_data[currency][0]['amount_lent'])
            swap_data_strs.append('{} {}'.format(currency.upper(), utils.truncatefloat(swap_data[currency], commas=True)))
        defer.returnValue("Bitfinex open swaps: {}".format(', '.join(reversed(swap_data_strs))))
