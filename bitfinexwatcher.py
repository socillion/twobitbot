#!/usr/bin/env python

import logging

from twisted.internet import task

from exchangelib import bitfinex
from twobitbot.utils.misc import now_in_utc_secs

log = logging.getLogger(__name__)


class BitfinexWatcher(object):
    def __init__(self):
        self._highestbid = None
        self._lowestask = None
        # easier than None
        self.last_updated = 0

        # todo switch to using exchangelib's poll instead of this
        self.checker = task.LoopingCall(self._update_data)
        self.checker.start(5)

    @property
    def highestbid(self):
        if self._is_data_fresh():
            return self._highestbid

    @property
    def lowestask(self):
        if self._is_data_fresh():
            return self._lowestask

    def _is_data_fresh(self):
        if now_in_utc_secs() - self.last_updated <= 60:
            return True
        return False

    def _update_data(self):
        def process(data):
            if isinstance(data, dict) and 'bid' in data and 'ask' in data:
                self._highestbid = data['bid']
                self._lowestask = data['ask']
                self.last_updated = now_in_utc_secs()
                return True
            return False
        d = bitfinex.ticker()
        d.addCallback(process)
        return d
