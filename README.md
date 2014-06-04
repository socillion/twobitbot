Two Bit Bot
=======
Twobitbot is an IRC bot built using Twisted in Python 2.7.

It has an arsenal of features aimed at Bitcoin and cryptocurrency traders, such as paper trading and whale alerts.

With a configuration file set up, it can be started with `python bot.py`.

Currently version 1.03, find up-to-date source at https://github.com/socillion/twobitbot

Features
=======
* Alerts on large orders executed on exchanges (currently limited to Bitstamp BTCUSD)
* Simple paper-trading via buy/sell chat commands
* Various other handy functions

Commands
=======
* `!time <location>`
    * Looks up the current time in a given location - use it to convert between timezones
* `!flair <bear|bull>`, `!flair status <username (optional)>`, `!flair top`
    * Flair is a paper-trading feature bound to IRC nicknames. This sacrifices some security due to users
    being able to 'steal' nicknames, but makes it a more usable feature than if it required logging in.
* `!help` for a list of commands

Configuration
=======
Twobitbot is configured via INI files in the main directory - `bot.ini`, with a fallback to `default.ini`.
See `default.ini` for an explanation of available configuration options.

NOTE: the active configuration file currently cannot be edited while the application is running,
because it will be overwritten at shutdown.

License
=======
Twobitbot is licensed under the MIT License except where otherwise noted.
The complete text is located in `./LICENSE`.

Files & Modules
=======
* `bot` handles IRC connections and events, and is the main file.
* `termbot` an alternate interface via terminal.
* `botresponder` handles responding to user commands/events.
* `flair` encapsulates logic for the flair paper-trading game.
* `bitstampwatcher` handles interfacing with the Bitstamp exchange and is responsible for Bitstamp activity alerts.
* `utils` is a package of various utility functions.
    * `misc` contains random helpers and is imported into the package.
    * `googleapis` module with functions to interface with Google APIs, currently limited to timezone/geolocation.
    * `ratelimit` provides tools to limit the rate at which users can access services.
    * `unicodeconsole` is a fix to make unicode possible on Windows terminals.
* `flair.db` is an sqlite3 database containing flair state.
* `confspec.ini` is the INI template that `default.ini` and `bot.ini` are checked against.


Requirements
=======
Although there are future plans to change this, currently twobitbot must be installed manually.
It depends on:

* `python27`
* `sqlite3`
* `configobj`
* `twisted`
* `treq`
* `pyopenssl`

* `bitcoinapis` at https://github.com/socillion/bitcoinapis
    * `autobahn`
    * `twistedpusher` at https://github.com/socillion/twistedpusher


Note: `pyopenssl` depends on `cryptography`, which can be annoying to install.
See instructions here: https://github.com/pyca/cryptography/blob/master/docs/installation.rst

Future features
=======
* Exchange wall alerts
* Support for alerts on additional exchanges, including Bitfinex, BTC-e, and Huobi
* User commands to list exchange prices, volume, etc
* Mining difficulty command?
* Competitive elements added to the flair paper-trading, such as a scoreboard. In addition, allow users to see
current sentiment (ratio of bull vs bear).
* bitfinex hidden wall detection
* change flair bear to short instead of fiat?
* last seen feature

Other Todo
=======
* rethink volume alert system
* clean up callbacks
* refactor how configuration is used and add some more options
    * rate limiting (flair and bot)
* finish converting all code to use Decimals (sqlite3 converter/adapter)
* possibly change flair to use BTC value instead of USD
* add telnet/web/similar interface in addition to terminal+irc?
* make auxiliary classes into twisted services
* convert to an application for use with twistd
* testing
* packaging
* add wall tracking
* add better live_orders support and Bitstamp HTTP API
* rethink logging


Changelog
=======
v1.04
* add config: volume_alert_threshold

v1.03 Apr 7, 2014
* switch bitstamp api code to twisted using TwistedPusher
* convert flair and api code to use Decimals
* improved logging
* abstract rate limiting to ratelimit.py, switch to exponential delay, and add rate limit to switching flair.
* change exchange APIs to return consistent objects
* add ban list
* split API into separate repo
* command dispatch QOL change, including arbitrary command prefixes

v1.02 Apr 2, 2014
* Fix timezone googleapi to reflect DST, encode urls properly, and return location name
* change !time to return the location name that was looked up
* clean up config reading, add google api key support
* change now_in_utc_secs to actually return UTC times
* added command !flair top
* track bitstamp orderbook age to avoid using stale data
* fix day field in format_timedelta

v1.01 Mar 26, 2014
* fixed !help, removed ping command
* converted lookup_localized_time to async (twisted/treq)
* use more config file values (server, server_port, donation_addr, bot_usage_delay)
* fix flair capitalization bug (user should be case-insensitive)
* switch to inlineCallbacks (so much more readable!)