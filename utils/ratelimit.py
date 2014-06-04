#!/usr/bin/env python

import logging

from twobitbot import utils

log = logging.getLogger(__name__)

# todo millisecond precision instead


class BaseUserRateLimiter(object):
    def __init__(self):
        self.users = dict()

    def is_limited(self, user):
        """Return True if the user is currently rate limited, False if they are not."""
        if user not in self.users:
            return False
        self.users[user]['since_last'] = self._get_now() - self.users[user]['last']
        return self._is_limited_predicate(self.users[user])

    def user_event_now(self, user):
        if user not in self.users:
            self.users[user] = {'last': 0, 'since_last': 0}
        self.users[user]['last'] = self._get_now()
        self._saw_user_event(self.users[user])

    def _is_limited_predicate(self, user):
        """Override. True if user is currently rate limited, False otherwise."""
        log.warn("Base class, no predicate provided for rate limiter.")
        return False

    def _saw_user_event(self, userinfo):
        """Override. Called when a user event occurs."""

    def _get_now(self):
        return utils.now_in_utc_secs()


class ExponentialRateLimiter(BaseUserRateLimiter):
    def __init__(self, max_delay=10*60, base_factor=1, reset_after=60*60):
        """max_delay: cap on how long users are made to wait.
        base_factor: delay starts out as 2^base_factor.
        reset_after: how long until user delay gets reset."""
        super(ExponentialRateLimiter, self).__init__()
        self.max_delay = max_delay
        self.base = base_factor
        self.reset_after = reset_after

    def _is_limited_predicate(self, user):
        if user['since_last'] <= 2**user['count'] and user['since_last'] < self.max_delay:
            # not enough time elapsed since last event, AND it hasn't been max_delay yet.
            return True
        return False

    def _saw_user_event(self, user):
        if user['since_last'] > self.reset_after or 'count' not in user:
            user['count'] = self.base
        else:
            user['count'] += 1


class ConstantRateLimiter(BaseUserRateLimiter):
    def __init__(self, delay=5):
        """delay: time between allowed usages."""
        super(ConstantRateLimiter, self).__init__()
        self.delay = delay

    def _is_limited_predicate(self, user):
        if user['since_last'] < self.delay:
            return True
        return False


def main():
    import time
    logging.basicConfig(level=logging.DEBUG)

    t = ExponentialRateLimiter(max_delay=10)
    t.user_event_now('x')
    time.sleep(2)

    for i in (3, 9, 7, 12):
        t.user_event_now('x')
        time.sleep(i)
        print(t.is_limited('x'))

if __name__ == '__main__':
    main()