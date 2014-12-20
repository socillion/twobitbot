Future features & Todo
=======
* Exchange wall alerts
* Support for alerts on additional exchanges, including Bitfinex, BTC-e, and Huobi
* User commands to list exchange prices, volume, etc
* Mining difficulty command?
* Competitive elements added to the flair paper-trading, such as a scoreboard. In addition, allow users to see
current sentiment (ratio of bull vs bear).
* bitfinex hidden wall detection
* last seen feature

Other Todo
=======
* refactor how configuration is used and add some more options
    * log file (bot.log is currently hardcoded)
* finish converting all code to use Decimals (sqlite3 converter/adapter)
* add telnet/web/similar interface in addition to terminal+irc?
* finish converting to an application for use with twistd (ircbot.tac)
    * reload config file without restarting
    * make auxiliary classes into twisted services
* testing
* packaging
* add better live_orders support (edit: this has been supplanted by a new, similar, data feed) and Bitstamp HTTP API
* rethink logging
* finish switching BitstampWatcher to BitstampAlerter
* add !translate command
    * not sure of feasibility, google translate is only available as a paid service
* change !forex and future pair-related commands to use X/Y in addition to XY
* update requirements.txt
* blockchain stuff? blockr.io and bc.i apis

* throttle flair changes based on hostname and not nick
* optional freenode username verification
* add swap/price formerly nickbot commands (also other nickbot stuff???)
* add small bets (unlikely to implement)

* fix the wolfram command, it fails on a lot of valid inputs
* is there a race condition with the throttling for calls like !wolfram that take a while to complete? it looks like it
* make daemon script initialize a virtualenv using mkvirtualenv -r requirements.txt?

Future flair changes:
1. add flair bottom to go with flair top. Margin called too?
2. possibly change flair top list to use BTC value instead of USD
3. more than 1:1 leverage?

* add restricted_commands or similar to config to block specific ones

* btc symbol instead of 'BTC' text?
* Maybe more easily extensible command system?
* fix repo line endings - mixed CRLF/LF. Even 1 CR somehow.
* convert string literals to unicode, experiencing bugs in situations like "{}".format(u"something")
    where the interpolated string is user input
    `from __future__ import unicode_literals`
* decide on whether to put defaults in confspec, initializers, or where. BitstampWatcher threshold, flair defaults, etc


<eo-r> think we could get the bot to tell us transactions with like >200k days destroyed or something? http://btc.blockr.io/documentation/api
<eo-r> or maybe just blocks >500k?

* add volume-differentiated alerts to twobitbot 
100-250 BTC Tuna alert
250-500 BTC Dolphin alert
500-1,000 BTC Manatee alert
1,000-2,000 BTC Orca alert
2,000-5,000 BTC Whale alert
5,000-10,000 BTC Mobidick alert
10,000-50,000 BTC Leviathan alert
50,000-100,000 BTC Poseidon alert
100,000-200,000 BTC Kraken alert
200,000+ BTC Satoshi alert
