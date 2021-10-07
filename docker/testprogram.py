#!/opt/conda/bin/python

import signal
import time

run = True

def handler_stop_signals(signum, frame):
    global run
    print("RECEIVED", signum)
    run = False

def hup(signal, frame):
    print('RECEVED HUP')

signal.signal(signal.SIGINT, handler_stop_signals)
signal.signal(signal.SIGTERM, handler_stop_signals)
signal.signal(signal.SIGHUP, hup)

while run:
    pass

print('Exit 1')
time.sleep(10)
print('Exit 2')
