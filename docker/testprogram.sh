#!/bin/sh

_term ()
{
    echo ; echo "trap: received SIGTERM ('TERM')" ; echo "exiting..." ; exit 0
}

_int ()
{
    echo ; echo "trap: received SIGINT ('INT')"   ; echo "exiting..." ; exit 0
}

_quit ()
{
    echo ; echo "trap: received SIGQUIT ('QUIT')" ; echo "exiting..." ; exit 0
}

_hup ()
{
    echo ; echo "trap: received SIGHUP ('HUP')"   ; echo "exiting..." ; exit 0
}

trap _term TERM
trap _int  INT
trap _quit QUIT
trap _hup  HUP

echo "==="
echo " have started: $0"
echo "    with args: $@"
echo "==="
echo " running: tail -f /dev/null | while read line ..."
echo " the 'tail -f /dev/null' created above ^^ is an orphaned process"
echo ""

tail -f /dev/null | while read line; do
    sleep 0
done
