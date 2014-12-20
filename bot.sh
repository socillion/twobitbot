#!/bin/bash

# Some inspiration taken from:
# https://codereview.stackexchange.com/questions/2217/is-this-a-decent-way-of-writing-a-start-stop-daemon-script


# the virtualenv feature requires an already set up virtualenv
# and a WORKON_HOME env var (used by virtualenvwrapper).
# example (in ~/.bashrc):
# `export WORKON_HOME=$HOME/.virtualenvs`

# Set USE_VIRTUALENV to 1 to enable using a virtualenv.
# WORKON_HOME ENV VAR MUST BE SET.
USE_VIRTUALENV=0
VIRTUALENV_NAME=twobitbot

TWISTD_EXEC="twistd"
EXEC="$TWISTD_EXEC -y ircbot.tac"
PID_FILE=twistd.pid
NAME=bot.sh

# todo shouldn't need to do this once everything is properly packaged
# for if the application isn't in PYTHONPATH
PYTHONPATH="$PYTHONPATH":..

# todo add command for reloading config (send SIGUSR2 to twistd PID and handle in ircbot.tac?)
# todo switch to real daemon script (i.e. init.d etc)?

#############################

if [ "$USE_VIRTUALENV" -eq 1 ]
then
    VIRTUALENV="$WORKON_HOME/$VIRTUALENV_NAME"
    source "$VIRTUALENV"/bin/activate
fi

case "$1" in
    start)
        echo 'Starting...'
        $EXEC

        if [ $? -eq 0 ]
        then
            echo "Done. Started with PID $(cat "$PID_FILE")."
        fi
        ;;
    stop)
        echo 'Stopping...'
        PID=$(cat "$PID_FILE" 2>/dev/null)

        if [ $? -eq 0 ]
        then
            kill "$PID"
            echo "Done. Stopped PID $PID."
        else
            echo 'Daemon is already stopped.'
        fi
        ;;
    force-reload|restart)
        echo 'Restarting...'
        PID=$(cat "$PID_FILE" 2>/dev/null)
        if [ $? -eq 0 ]
        then
            kill "$PID"
            echo "Stopped PID $PID."
        else
            echo "Daemon not running."
        fi

        $EXEC

        if [ $? -eq 0 ]
        then
            echo "Done. Started with PID $(cat "$PID_FILE")."
        fi
        ;;
    status)
        echo -n "Status: "
        PID=$(cat "$PID_FILE" 2>/dev/null)
        if [ $? -eq 0 ]
        then
            echo "Running with PID $PID."
        else
            echo "Stopped."
        fi
        ;;
    *)
        echo "Use: ./$NAME {start|stop|restart|force-reload|status}"
        exit 1
        ;;
esac
exit 0