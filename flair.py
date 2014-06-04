#!/usr/bin/env python

import logging
import datetime
from decimal import Decimal
from collections import namedtuple

from twisted.internet import defer, reactor
from twisted.application import service
from twisted.enterprise import adbapi

from twobitbot import utils
from twobitbot.utils import ratelimit


log = logging.getLogger(__name__)

# not sure whether to put all this code into a service, or write a thin wrapper service around the Flair class...

# todo change decimal code to use sqlite3 converter and adapter
# http://stackoverflow.com/questions/6319409/how-to-convert-python-decimal-to-sqlite-numeric
# todo FlairRow for updating DB, and more transparent Decimal conversion

# todo convert top user list to BTC instead of USD

FlairRow = namedtuple('FlairRow', ['user', 'type', 'price', 'usd_amt', 'btc_amt', 'time'])


class Flair(object):
    btcpip = Decimal(10000)
    usdpip = Decimal(100)

    def __init__(self, exchange_watcher, flair_db, ratelimiter=None):
        # todo implement better method of doing stuff than passing an exchange_watcher
        self.watcher = exchange_watcher
        self.ratelimiter = ratelimiter or ratelimit.ConstantRateLimiter(delay=3*60)
        self.db_location = flair_db

        self.dbpool = None
        self.start()

        # todo possibly remove shutdown call? check if this and check_same_thread are necessary...
        reactor.addSystemEventTrigger('before', 'shutdown', self.stop)

    def start(self):
        self.dbpool = adbapi.ConnectionPool('sqlite3', self.db_location, check_same_thread=False)
        if not self.dbpool:
            raise IOError("Could not load flair DB {0}".format(self.db_location))

        create_table = """CREATE TABLE IF NOT EXISTS ircflair (id INTEGER PRIMARY KEY,
                      user TEXT COLLATE NOCASE, flairstatus TEXT, flairprice INTEGER, usd_amount INTEGER,
                      btc_amount INTEGER, timestamp INTEGER)"""
        self.dbpool.runQuery(create_table)

    def stop(self):
        if self.dbpool:
            self.dbpool.finalClose()

    @defer.inlineCallbacks
    def change(self, user, cmd):
        price = 0

        if not self.watcher.lowestask or not self.watcher.highestbid:
            log.debug("Flair change called without bid/ask initialized.")
            defer.returnValue("I have no recent orderbook data. Please try again later.")

        if cmd == 'bull':
            price = self.watcher.lowestask
        elif cmd == 'bear':
            price = self.watcher.highestbid
        else:
            log.debug("Invalid flair change command: '%s' by %s" % (cmd, user))
            defer.returnValue(None)

        if self.ratelimiter.is_limited(user):
            defer.returnValue("I'm sorry %s, I'm afraid I can't do that. Wait a few minutes first." % (user))

        old = yield self.check_last(user)
        new = {'user': user, 'type': cmd, 'price': price*Flair.usdpip, 'usd_amt': 0, 'btc_amt': 0}
        if not old:
            # user hasn't set flair before
            log.debug("Initializing flair %s for %s at %.2f" % (cmd, user, price))
            if cmd == 'bull':
                new['btc_amt'] = 1*Flair.btcpip
            elif cmd == 'bear':
                new['usd_amt'] = price*Flair.usdpip
            self._insert_flairupdate(new)
            defer.returnValue("%s, welcome to the flair game! You are now %s from $%.2f." % (user, cmd, price))
        elif cmd != old.type:
            # valid command to change flair, user already has it set
            amt_str = ''
            if cmd == 'bull':
                log.debug("Updating flair to %s for %s (who has $%s), old price %.2f and new price %.2f" %
                         (cmd, user, old.usd_amt/Flair.usdpip, old.price/Flair.usdpip, price))
                new['btc_amt'] = old.usd_amt / price * Flair.usdpip
                amt_str = "%.4f BTC" % (new['btc_amt']/Flair.btcpip)
            elif cmd == 'bear':
                log.debug("Updating flair to %s for %s (who has %.4f BTC), old price %.2f and new price %.2f" %
                         (cmd, user, old.btc_amt/Flair.btcpip, old.price/Flair.usdpip, price))
                new['usd_amt'] = price * old.btc_amt * (Flair.usdpip / Flair.btcpip)
                amt_str = "$%.2f" % (new['usd_amt'] / Flair.usdpip)
            self._insert_flairupdate(new)
            self.ratelimiter.user_event_now(user)
            defer.returnValue("%s, you are now %s from $%.2f with %s." % (user, cmd, price, amt_str))
        else:
            # user tried to change flair to current value
            defer.returnValue("%s, you are already a %s." % (user, cmd))

    def _insert_flairupdate(self, rec):
        for k in ('price', 'usd_amt', 'btc_amt'):
            rec[k] = int(rec[k])
        return self.dbpool.runQuery("""INSERT INTO ircflair(user, flairstatus, flairprice,
                                usd_amount, btc_amount, timestamp)
                                VALUES(?, ?, ?, ?, ?, ?)""",
                                    (rec['user'], rec['type'], rec['price'], rec['usd_amt'],
                                     rec['btc_amt'], utils.now_in_utc_secs()))

    def _check(self, user):
        return self.dbpool.runQuery("""SELECT user, flairstatus, flairprice, usd_amount, btc_amount, timestamp
                                    FROM ircflair WHERE user = ? ORDER BY timestamp DESC""", (user,))

    @defer.inlineCallbacks
    def check_last(self, user):
        rows = yield self._check(user)
        if rows:
            # in order: user, type, price, usd_amt, btc_amt, time
            # need to convert it so we can make Decimals in-place
            last = list(rows[0])
            # convert price, usd_amt, btc_amt to Decimals
            for k in (2, 3, 4):
                last[k] = Decimal(last[k])
            # timestamp to int
            last[5] = int(last[5])

            data = FlairRow(*last)
            defer.returnValue(data)
        else:
            raise ValueError

    @defer.inlineCallbacks
    def top(self):
        if not self.watcher.highestbid:
            defer.returnValue("I have no recent orderbook data. Please try again later.")
            log.debug("Top flair called without current bid/ask set.")

        query = """SELECT user, flairstatus, usd_amount, btc_amount, max(timestamp) from ircflair group by user"""

        rows = yield self.dbpool.runQuery(query)

        if rows and self.watcher.highestbid:
            normalized_users = list()
            bull_usd = self.watcher.highestbid
            for row in rows:
                # need to convert it to assign, since it's a tuple
                row = list(row)
                row[2] = Decimal(row[2])
                row[3] = Decimal(row[3])

                if row[1] == 'bull':
                    normalized_users.append((row[0], row[1], (row[3] * bull_usd)/Flair.btcpip))
                else:
                    normalized_users.append((row[0], row[1], row[2]/100))
            top = sorted(normalized_users, key=lambda usr: usr[2], reverse=True)
            top_strs = ["%s (%s with $%.2f)" % (user[0], user[1], user[2]) for user in top[:3]]
            defer.returnValue("Top flair users: " + ', '.join(top_strs))

    @defer.inlineCallbacks
    def status(self, user):
        if not self.watcher.lowestask or not self.watcher.highestbid:
            defer.returnValue("I have no recent orderbook data. Please try again later.")
            log.debug("Flair status called without current bid/ask set.")
        last = yield self.check_last(user)
        if last:
            since_change = datetime.datetime.utcnow() - datetime.datetime.utcfromtimestamp(last.time)
            date_str = utils.format_timedelta(since_change)
            balance_str = ""
            price_str = "%.2f" % (last.price/Flair.usdpip)
            pl = 0
            if last.type == 'bear':
                pl = (last.price / (self.watcher.lowestask * Flair.usdpip) * 100) - 100
                balance_str = "$%s" % (last.usd_amt/Flair.usdpip)
            elif last.type == 'bull':
                pl = (self.watcher.highestbid * Flair.usdpip / last.price * 100) - 100
                balance_str = "%.4f BTC" % (last.btc_amt / Flair.btcpip)
            if pl > 0:
                pl_str = "+"
            else:
                pl_str = ""
            pl_str += ("%.2f" % (pl)) + '%'

            # "user is bear from $653.12 (P/L 1.23%) with X btc/usd for 3 days, 4 hours, and 5 minutes."
            ret = "%s is %s from %s (P/L %s) with %s" % (last.user, last.type, price_str, pl_str, balance_str)
            if len(date_str) > 0:
                ret += " for %s" % date_str
            ret += "."
            defer.returnValue(ret)

        else:
            defer.returnValue("No flair found for user %s. Join the game with !flair <BEAR|BULL>." % (user))


class FlairService(Flair, service.Service):
    name = 'FlairService'

    def __init__(self, exchange_watcher, flair_db, ratelimiter=None):
        super(FlairService, self).__init__(exchange_watcher, flair_db, ratelimiter)

    def startService(self):
        log.info("Starting flair service")
        self.start()

    def stopService(self):
        log.info("Stopping flair service")
        self.stop()

