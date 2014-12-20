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

# todo look into sqlalchemy for this stuff


class NoExchangeDataError(ValueError):
    pass


class Position(object):
    BULL = 1
    NEUTRAL = 0
    BEAR = -1
    # todo do i really need to have these be numbers

    @staticmethod
    def to_text(position):
        if position == Position.BULL:
            return "long"
        elif position == Position.BEAR:
            return "short"
        elif position == Position.NEUTRAL:
            return "fiat"
        else:
            raise ValueError("Invalid position '{}'".format(position))

    @staticmethod
    def from_text(position_str):
        position_str = str(position_str).strip().lower()
        if position_str in ('bull', 'long', 'paavo'):
            return Position.BULL
        elif position_str in ('bear', 'short'):
            return Position.BEAR
        elif position_str in ('neutral', 'fiat'):
            return Position.NEUTRAL
        else:
            raise ValueError("Invalid position string '{}'".format(position_str))


FlairRow = namedtuple('FlairRow2', ['user', 'position', 'price', 'usd_amount', 'timestamp'])


class FlairGame(object):
    usd_pip = Decimal(100*100)
    msg_no_orderbook_data = "I have no recent orderbook data. Please try again later."

    def __init__(self, exchange_watcher, db, change_delay=0):
        """
        db: flair sqlite3 database location
        change_delay: how long users must wait between flair changes
        top_list_size: how many entries to return with the `!flair top` command
        """
        # todo implement better method of doing stuff than passing an exchange_watcher
        # really the watcher can be anything that has highestbid and lowestask attrs
        self.watcher = exchange_watcher
        self.ratelimiter = ratelimit.ConstantRateLimiter(delay=change_delay)
        self.db_location = db

        self.dbpool = None
        self.start()

        # todo possibly remove shutdown call? check if this and check_same_thread are necessary...
        reactor.addSystemEventTrigger('before', 'shutdown', self.stop)

    def start(self):
        self.dbpool = adbapi.ConnectionPool('sqlite3', self.db_location, check_same_thread=False)
        if not self.dbpool:
            raise IOError("Could not load flair DB {0}".format(self.db_location))
        return self._create_flair_table()

    def stop(self):
        if self.dbpool:
            return self.dbpool.finalClose()

    @defer.inlineCallbacks
    def change(self, user, position):
        # determine the new position, converting it from a string to a Position enum entry
        try:
            position = Position.from_text(position)
        except ValueError:
            log.debug("Invalid flair change command: '{}' by {}".format(position, user))
            defer.returnValue(None)

        # moved this from the very top so it doesn't emit an error if it's an invalid command
        if self.ratelimiter.is_limited(user):
            defer.returnValue("I'm sorry {}, I'm afraid I can't do that. Wait a few minutes first.".format(user))

        old = yield self._users_current_flair(user)
        try:
            price = self._determine_flair_price(position, getattr(old, 'position'))
        except NoExchangeDataError:
            defer.returnValue(FlairGame.msg_no_orderbook_data)
        except ValueError:
            defer.returnValue("{}, you are already {}.".format(user, Position.to_text(position)))

        if not old:
            # user hasn't set flair before
            log.debug("Initializing flair {} ({}) for {} at {:.2f}".format(Position.to_text(position),
                                                                           position, user, price))
            self._update_user_flair(user, position, price, price)
            defer.returnValue("{}, welcome to the flair game! You are now {} from ${:.2f}.".format(
                user, Position.to_text(position), price))
        else:
            #  valid command to change flair, and user already has it set
            profit_loss, new_usd_balance = self._calc_profit_loss(old.position, old.price, old.usd_amount, price)

            if new_usd_balance <= 0:
                # margin called, so re-initialize their flair
                new_usd_balance = price
                margin_called = True
            else:
                margin_called = False

            self._update_user_flair(user, position, price, new_usd_balance)
            if position != Position.NEUTRAL:
                btc_str = " {:.4f} BTC".format(new_usd_balance/price)
            else:
                btc_str = ""
            defer.returnValue(("{user}, you {0}are now {position}{btc_str} from ${price:.2f} with ${balance:.2f}"
                               .format("were margin called and " if margin_called else "",
                                       user=user, position=Position.to_text(position), btc_str=btc_str,
                                       price=price, balance=new_usd_balance)))

    @defer.inlineCallbacks
    def top(self, count=5):
        rows = yield self._all_flairs()

        if rows:
            # normalized_users stores dicts of user, position, usd balance including unrealized p/l
            normalized_users = list()

            for row in rows:
                try:
                    _, usd_balance = self._calc_profit_loss(row.position, row.price, row.usd_amount)
                except NoExchangeDataError:
                    defer.returnValue(FlairGame.msg_no_orderbook_data)
                normalized_users.append({'user': row.user,
                                         'position': Position.to_text(row.position),
                                         'balance': usd_balance})
            top = sorted(normalized_users, key=lambda usr: (usr['balance'], usr['user']), reverse=True)
            top_strs = ["{0[user]} ({0[position]} with ${0[balance]:.2f})".format(user_row) for user_row in top[:count]]
            defer.returnValue("Top flair users: " + ', '.join(top_strs))

    @defer.inlineCallbacks
    def status(self, user):
        last = yield self._users_current_flair(user)
        if not last:
            # no flair found
            defer.returnValue("No flair found for user {}. Join the game with !flair <long|fiat|short>.".format(user))
        else:
            since_change = datetime.datetime.utcnow() - datetime.datetime.utcfromtimestamp(last.timestamp)
            date_str = utils.format_timedelta(since_change)

            try:
                profit_loss, new_usd_balance = self._calc_profit_loss(last.position, last.price, last.usd_amount)
            except NoExchangeDataError:
                defer.returnValue(FlairGame.msg_no_orderbook_data)

            if len(date_str):
                date_str = " for {}".format(date_str)
            if last.position != Position.NEUTRAL:
                pl_str = " (P/L {:+.2%})".format(profit_loss/last.usd_amount)
                btc_str = " {:.4f} BTC".format(last.usd_amount/last.price)
            else:
                pl_str = btc_str = ""
            # old:
            # "user is bear from $653.12 (P/L 1.23%) with X btc/usd for 3 days, 4 hours, and 5 minutes."
            ret = ("{user} is {position}{btc_str} from {price:.2f}{pl_str}{date} with a net worth of ${balance:.2f}."
                   .format(user=user, position=Position.to_text(last.position), btc_str=btc_str, price=last.price,
                           pl_str=pl_str, date=date_str, balance=new_usd_balance))
            defer.returnValue(ret)

    ##### helper methods below this point #####

    def _calc_profit_loss(self, position, open_price, open_usd_amount, close_price=None):
        """Returns a tuple of profit/loss and the resulting fiat balance."""
        if not close_price:
            close_price = self._determine_flair_price(position)
        old_btc_amount = open_usd_amount / open_price

        if position == Position.NEUTRAL:
            close_usd_amount = open_usd_amount
        elif position == Position.BULL:
            close_usd_amount = old_btc_amount * close_price
        elif position == Position.BEAR:
            profit_loss = open_usd_amount - old_btc_amount * close_price
            close_usd_amount = open_usd_amount + profit_loss
        else:
            raise ValueError("Invalid position {}".format(position))
        profit_loss = close_usd_amount - open_usd_amount
        return profit_loss, close_usd_amount

    def _determine_flair_price(self, position, prev_position=None):
        """helper to figure out a current price given a position. this is needed because
        for bull it would be lowest ask, bear highest bid, etc, simulating having closed the
        position on the exchange."""
        # todo verify this works correctly if prev_position is not set, e.g for top

        if prev_position is None:
            prev_position = Position.NEUTRAL

        bid = self.watcher.highestbid
        ask = self.watcher.lowestask
        mid = (bid + ask) / 2

        if not bid or not ask:
            log.error('Bad exchange price data: bid {} ask {}'.format(bid, ask))
            raise NoExchangeDataError

        if position != prev_position:
            if position == Position.BULL or (position == Position.NEUTRAL and
                                             prev_position == Position.BEAR):
                price = ask
            elif position == Position.BEAR or (position == Position.NEUTRAL and
                                               prev_position == Position.BULL):
                price = bid
            else:
                raise ValueError("Invalid flair change: {} -> {}".format(Position.to_text(position),
                                                                         Position.to_text(prev_position)))
        elif position == Position.NEUTRAL and prev_position == Position.NEUTRAL:
            price = mid
        else:
            raise ValueError("Invalid flair change: {} -> {}".format(Position.to_text(position),
                                                                     Position.to_text(prev_position)))
        return price

    def _load_row(self, raw_row):
        """Helper function to process rows read from the DB to e.g. do Decimal and pip conversions."""
        # todo call Position.to_text from here and from_text when inserting into db?
        # in order: user, position, price, usd_amount, timestamp
        row = list(raw_row)

        # price
        row[2] = Decimal(row[2])/self.usd_pip
        # usd_amount
        row[3] = Decimal(row[3])/self.usd_pip
        # timestamp
        row[4] = int(row[4])

        return FlairRow(*row)

    @defer.inlineCallbacks
    def _users_current_flair(self, user):
        """Get a user's current flair."""
        rows = yield self.dbpool.runQuery("""SELECT user, position, price, usd_amount, timestamp
                                             FROM ircflair WHERE user = ? ORDER BY timestamp DESC LIMIT 1""", (user,))
        if rows:
            defer.returnValue(self._load_row(rows[0]))
        else:
            log.debug("No flair found for user {}".format(user))
            defer.returnValue(None)

    @defer.inlineCallbacks
    def _all_flairs(self):
        """Get a list of all current flairs."""
        query = """SELECT user, position, price, usd_amount, max(timestamp) from ircflair group by user"""
        rows = yield self.dbpool.runQuery(query)
        defer.returnValue([self._load_row(row) for row in rows])

    def _update_user_flair(self, user, position, price, usd_amount):
        log.debug(("Changing {}'s flair to {} ({}) at ${:.2f} with a balance of ${:.2f}."
                   .format(user, Position.to_text(position), position, price, usd_amount)))
        self.ratelimiter.user_event_now(user.lower())
        record = FlairRow(user=user, position=position, price=price, usd_amount=usd_amount,
                          timestamp=utils.now_in_utc_secs())
        return self.dbpool.runQuery("""
                    INSERT INTO ircflair(user, position, price, usd_amount, timestamp) VALUES(?, ?, ?, ?, ?)""",
                                    (record.user, record.position, int(record.price*self.usd_pip),
                                     int(record.usd_amount*self.usd_pip), record.timestamp))

    def _create_flair_table(self):
        create_table = """CREATE TABLE IF NOT EXISTS ircflair (id INTEGER PRIMARY KEY,
                      user TEXT COLLATE NOCASE, position INTEGER, price INTEGER,
                      usd_amount INTEGER, timestamp INTEGER)"""
        return self.dbpool.runQuery(create_table)

class FlairGameService(FlairGame, service.Service):
    name = 'FlairGameService'

    def __init__(self, exchange_watcher, flair_db, ratelimiter=None):
        super(FlairGameService, self).__init__(exchange_watcher, flair_db, ratelimiter)

    def startService(self):
        log.info("Starting flair service")
        self.start()

    def stopService(self):
        log.info("Stopping flair service")
        self.stop()
