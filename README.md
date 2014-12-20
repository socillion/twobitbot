Two Bit Bot
=======
Twobitbot is an IRC bot built using Twisted in Python 2.7.

It has an arsenal of features aimed at Bitcoin and cryptocurrency traders, such as paper trading and large trade alerts.

With a configuration file set up at `bot.ini`, it can be started with `bot.sh start`, `twistd -y ircbot.tac`, or `python bot.py`.

Currently version 1.04, find up-to-date source at https://github.com/socillion/twobitbot

Features
=======
* Alerts on large orders executed on exchanges (currently limited to Bitstamp BTCUSD)
* Simple paper-trading via buy/sell chat commands
* Various other handy functions

Commands
=======
* `!time <location>`
    * Looks up the current time in a given location - use it to convert between timezones
* `!flair <long|fiat|short>`, `!flair status <username (optional)>`, `!flair top`
    * Flair is a paper-trading feature bound to IRC nicknames. 
* `!wolfram <query>`, `!math <query>`
    * Use Wolfram Alpha to do math and get information
* `!forex <amount> <pair>`, `!forex <pair>`, `!forex <amount> <one currency> to <another currency>`
    * Convert between currencies using real time forex rates.
* `!help` for a list of commands

Configuration
=======
Twobitbot is configured via INI files in the main directory - `bot.ini`, with a fallback to `default.ini`.
See `default.ini` for an explanation of available configuration options.

NOTE: currently the bot must be restarted for configuration changes to be applied.

License
=======
Twobitbot is licensed under the MIT License except where otherwise noted.

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
Twobitbot currently can only be installed manually.
It depends on:

* `python27`
* `sqlite3`
* `configobj`
* `twisted`
* `treq`
* `pyopenssl`
* `wolframalpha`

* `exchangelib` at https://github.com/socillion/exchangelib

Note: `pyopenssl` depends on `cryptography`, which can be annoying to install.
See instructions here: https://github.com/pyca/cryptography/blob/master/docs/installation.rst

Todo
=======
See `TODO.md`

Changelog
=======
v1.04 Dec 20, 2014
* Added commands:
    * !math and !wolfram commands via Wolfram Alpha
    * !forex conversions using rates from the ECB and elsewhere
    * !swaps for Bitfinex swap statistics
* Created a launch bash script `bot.sh`
* Upgraded flair game - added shorting (DB format is incompatible with 1.04)
* Implemented config options: volume_alert_threshold, max_command_usage_delay, 
    flair_change_delay, flair_top_list_size, wolfram_alpha_api_key, open_exchange_rates_app_id

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