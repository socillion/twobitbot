#!/usr/bin/env python

import logging
import datetime
import math
import time
import calendar

log = logging.getLogger(__name__)


# class AttributeDict(dict):
#     def __init__(self, *args, **kwargs):
#         super(AttributeDict, self).__init__(*args, **kwargs)
#         self.__dict__ = self


def format_time(dt):
    try:
        return "%s" % (dt.strftime("%b %d %I:%M %p"))
    except (AttributeError, TypeError):
        log.warn("Invalid datetime object passed to utilities.format_time: %s of type %s" %
                 (dt, type(dt).__name__), exc_info=True)


def format_timedelta(td):
    """Return a string format of a timedelta. Days/Hours/Minutes."""
    ret = ""
    total_secs = td.seconds

    # kinda hacky, should fix this
    if total_secs < 0:
        total_secs *= -1

    days = td.days
    hours, rem_secs = divmod(total_secs, 3600)
    mins = math.floor(rem_secs/60)

    for delta, name in zip((days, hours, mins), ("day", "hour", "min")):
        if delta > 0:
            if len(ret.strip()) > 0:
                ret += " and "
            ret += "%d %s" % (delta, name)
            ret += plural_string(delta)

    return ret


def plural_string(num):
    if num > 1:
        return 's'
    else:
        return ''


def now_in_ms():
    """Relative timestamp. only useful for comparing to other now_in_ms() outputs from same session"""
    if not hasattr(now_in_ms, "basetime"):
        now_in_ms.basetime = datetime.datetime.now()

    now = datetime.datetime.now()
    now_rel = now - now_in_ms.basetime
    return int(now_rel.total_seconds()*1000)


def now_in_utc_secs():
    return int(calendar.timegm(time.gmtime()))


def truncatefloat(num, decimals=2, commas=False):
    """Takes a float, returns a string. Return value is capped at N digits after the decimal and
    trailing zeros are removed, as well as the decimal if nothing but 0s after it."""
    # remove extraneous trailing 0s and . as well as reduce to max 2 digits after decimal point
    # fixed bug: must be 2 different rstrips, rstrip('0.') will strip 100.00 to 1 instead of 100
    fmt_str = '{:' + (',' if commas else '') + '.{}f}}'.format(decimals)
    try:
        return fmt_str.format(num).rstrip('0').rstrip('.')
    except TypeError:
        log.error("truncatefloat was passed a bad type: %s of type %s" % (num, type(num).__name__), exc_info=True)
