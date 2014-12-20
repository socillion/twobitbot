#!/usr/bin/env python

from twisted.internet import task

import logging
import copy
from collections import deque

from twobitbot import utils
from exchangelib import bitstamp

log = logging.getLogger(__name__)


# todo: replace dicts with trade objects
# todo: move thresholds into config file
# todo: add live_orders support
# todo: add tracking for walls


# temp class for integrating bitstampobserver
class BitstampAlerter(bitstamp.BitstampObserver):
    def __init__(self, triggervolume=100):
        super(BitstampAlerter, self).__init__()
        self.triggervolume = triggervolume
        self.obs = bitstamp.BitstampObserver()
        self.alert_callbacks = list()

    def add_alerter(self, callback):
        """"""
        if callable(callback):
            self.alert_callbacks.append(callback)
        else:
            raise ValueError("Alert callback must be callable.")

    def _send_alert(self, data):
        """Call with Trade object that has amount and price data."""
        ann_str = u"Bitstamp alert | "

        try:
            if data.is_buy:
                ann_str += u'\u25B2 BUY '
            else:
                ann_str += u'\u25BC SELL '
        except AttributeError:
                pass
        amt_str = utils.truncatefloat(data.amount)
        ann = u"%s %s BTC at $%0.2f" % (ann_str, amt_str, data.price)
        log.info(ann.encode('utf8'))

        for cb in self.alert_callbacks:
            cb(ann)

    def whale_scanner(self):
        """"""


class BitstampWatcher(object):

    def __init__(self, triggervolume=100):
        self.triggervolume = triggervolume or 100

        self._highestbid = None
        self._lowestask = None

        self.recentorders = deque()
        self.orderbook = dict()
        self.last_orderbook = None

        self.alert_cbs = list()

        # was previously done with BitstampWSAPI and add_trade_listener/add_orderbook_listener
        self.api = bitstamp.BitstampWebsocketAPI2()
        self.api.listen('trade', self.on_trade)
        self.api.listen('orderbook', self.on_orderbook)
        #self.api.add_liveorder_listener('')

        self.checker = task.LoopingCall(self.check_whale_marketorder)
        self.checker.start(10)

    @property
    def highestbid(self):
        if self._keep_orderbook_fresh():
            return self._highestbid

    @property
    def lowestask(self):
        if self._keep_orderbook_fresh():
            return self._lowestask

    def _keep_orderbook_fresh(self):
        """Check that the orderbook data is fresh.
        Returns true if it is, or there isn't data, and false if it's stale."""
        now = utils.now_in_utc_secs()
        if self.last_orderbook and now - self.last_orderbook > 60:
            # 60s+ since last orderbook
            return False
        else:
            # either the orderbook callback hasn't triggered yet or we have fresh data
            return True

    def __del__(self):
        if self.checker is not None:
            self.checker.stop()

    def _tag_trade_buysell(self, order):
        bid = self.highestbid
        ask = self.lowestask

        if bid is None or ask is None:
            return

        if order['price'] <= bid:
            # order executed under or at bid, so it's a sell
            order['is_buy'] = False
        if order['price'] >= ask:
            # order executed at or above ask, so it's a buy
            order['is_buy'] = True

    def on_trade(self, data):
        """Callback, called when new bitstamp trade events
        Data persisted in self.bitstamp_recentorders"""
        self._tag_trade_buysell(data)
        if not 'is_buy' in data:
           # short circuit if not tagged buy/sell
            return
        if data['amount'] > self.triggervolume:
            self.announce_whale_order(data)
            log.debug("trade event alerting on Bitstamp order: %.2f @ %.2f, is_buy: %s" %
                     (data['amount'], data['price'], data['is_buy']))
        else:
            data['timestamp'] = utils.now_in_ms()
            self.recentorders.appendleft(data)

    def _clear_old_trades(self, timelimit_ms=15000):
        """This has to be called to get a time-limited view of recent trades.
        Parameters:
            timelimit_ms - removes all orders more than this many ms old, compared to the most recent order"""
        if len(self.recentorders) > 0:
            while self.recentorders[0]['timestamp'] - self.recentorders[-1]['timestamp'] > timelimit_ms:
                self.recentorders.pop()

    def check_whale_marketorder(self):
        # Avoid race condition with _trade_event removing orders??? no sure if important
        # Not sure if this is the best method to do so.
        # May not be necessary now that I removed the recentorders.clear() call in there
        self._clear_old_trades()
        orders = copy.copy(self.recentorders)

        ordersum = sum([order['amount'] for order in orders])

        # this much btc or more to trigger an alert

        if ordersum > self.triggervolume:
            buyvol = sellvol = 0
            high = low = 0

            for order in orders:
                if 'is_buy' in order and order['is_buy'] is True:
                    buyvol += order['amount']
                    if high == 0 or order['price'] > high:
                        high = order['price']
                elif 'is_buy' in order and order['is_buy'] is False:
                    sellvol += order['amount']
                    if low == 0 or order['price'] < low:
                        low = order['price']

            log.debug("ordersum %s, buyvol %s, sellvol %s, high %.2f, low %.2f" %
                      (ordersum, buyvol, sellvol, high, low))
            if buyvol > self.triggervolume and buyvol/(buyvol+sellvol) > 0.8:
                self.announce_whale_order({'amount': buyvol, 'price': high, 'is_buy': True})
                self.recentorders.clear()
            elif sellvol > self.triggervolume and sellvol/(buyvol+sellvol) > 0.8:
                self.announce_whale_order({'amount': sellvol, 'price': low, 'is_buy': False})
                self.recentorders.clear()

    def on_orderbook(self, data):
        """Callback, called when new bitstamp orderbook data available"""
        self.orderbook = data
        if 'bids' in data and 'asks' in data and len(data['bids']) > 0 and len(data['asks']) > 0:
            self._highestbid = data['bids'][0]['price']
            self._lowestask = data['asks'][0]['price']
            self.last_orderbook = utils.now_in_utc_secs()
        else:
            log.warn("Bad orderbook data in on_orderbook: %s" % (data))

    def announce_whale_order(self, data):
        """Call with dict in form of {'amount': ordersize, 'price': orderprice}. Additional data in dict is ignored"""
        ann_str = u"Bitstamp alert | "
        if 'is_buy' in data:
            if data['is_buy'] is True:
                ann_str += u'\u25B2 BUY '
            elif data['is_buy'] is False:
                ann_str += u'\u25BC SELL '
        else:
            #ann_str = "Whale alert!"
            ann_str += ""

        amt_str = utils.truncatefloat(data['amount'])
        ann = u"%s %s BTC at $%0.2f" % (ann_str, amt_str, data['price'])
        log.info(ann.encode('utf8'))
        # sendline won't accept unicode, but moved the encoding into the actual callbacks
        self._send_alert(ann)

    def add_alert_callback(self, callback):
        self.alert_cbs.append(callback)

    def _send_alert(self, msg):
        for cb in self.alert_cbs:
            cb(msg)


class Trade:
    def __init__(self, amount=0, price=0, timestamp=None, is_buy=None):
        self.amount = amount
        self.price = price
        self.timestamp = timestamp
        self.is_buy = is_buy


def main():
    pass


if __name__ == '__main__':
    main()
