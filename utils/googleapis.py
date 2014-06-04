#!/usr/bin/env python

import logging
import datetime
import treq

from twisted.internet import defer

from twobitbot.utils.misc import now_in_utc_secs

log = logging.getLogger(__name__)

# todo raise errors on failure...

@defer.inlineCallbacks
def lookup_localized_time(location, utc_time, google_api_key=''):
    """
    Lookup the time in a location.
    :param location: location name
    :type location: str

    :param utc_time: UTC time to convert
    :type utc_time: datetime.datetime

    :param google_api_key: optional API key for Google API calls
    :type google_api_key: str

    :return: a dict containing keys 'time' which is localized time as a datetime object,
            and 'location' which is the location name returned by Google.
    @rtype: defer.Deferred
    """
    geocode = yield lookup_geocode(location, google_api_key)
    if geocode:
        tz = yield lookup_timezone(geocode, google_api_key)
        try:
            new_time = utc_time+datetime.timedelta(seconds=tz)
        except TypeError:
            log.error("Encountered error changing timezone with sec offset", exc_info=True)
        else:
            ret = {'time': new_time, 'location': geocode['loc']}
            defer.returnValue(ret)


@defer.inlineCallbacks
def lookup_geocode(location, api_key=''):
    """
    Determine the lat/long coordinates for a location name.

    :param location: location name
    :type location: str
    :type api_key: str

    :return: a dict with keys 'lat', 'lng', 'loc' that contain
     the lat/long coordinates and placename for the location.
    :rtype: defer.Deferred
    """
    try:
        res = yield treq.get("http://maps.googleapis.com/maps/api/geocode/json",
                             params={'address': location, 'sensor': 'false', 'key': api_key})
        if res and res.code == 200:
            data = yield treq.json_content(res)
            if data['status'] == 'OK':
                # API returned at least one geocode
                ret = data['results'][0]['geometry']['location']
                ret['loc'] = data['results'][0]['formatted_address']
                defer.returnValue(ret)
            else:
                log.warn("Bad status response from Google Geocode API: %s" % (data['status']))
        elif res is not None:
            log.warn("Bad HTTP status from Google Geocode API: %s" % (res.code))
    except TypeError:
        log.warn("Bad location passed to lookup_geocode", exc_info=True)


@defer.inlineCallbacks
def lookup_timezone(loc, api_key=''):
    """
    Determine the timezone of a lat/long pair.

    @param loc: lat/long coordinates of a location
    @type loc: dict
    @type api_key: str

    @rtype: defer.Deferred yielding a second offset representing the timezone
    """
    try:
        res = yield treq.get(("https://maps.googleapis.com/maps/api/timezone/json"),
                             params={'location': str(loc['lat']) + ',' + str(loc['lng']),
                                     'timestamp': str(now_in_utc_secs()), 'sensor': 'false', 'key': api_key})
        if res and res.code == 200:
            data = yield treq.json_content(res)
            if data['status'] == 'OK':
                # API returned timezone info. What we care about: rawOffset
                defer.returnValue(int(data['rawOffset'])+int(data['dstOffset']))
            else:
                log.warn("Bad status response from Google Geocode API: %s" % (data['status']))
        elif res is not None:
            log.warn("Bad HTTP status from Google Timezone API: %s" % (res.code))
    except TypeError:
        log.warn("Bad lat/long parameter passed to lookup_timezone: %s" % (loc), exc_info=True)



def main():
    pass


if __name__ == '__main__':
    main()
