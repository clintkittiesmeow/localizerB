import atexit
import logging
import os
from threading import Event

from localizer.params import Params
from localizer.server import HTTPThread

# Shared Variables
debug = False
serve = False
params = Params()


# Console colors
W = '\033[0m'  # white (normal)
R = '\033[31m'  # red
G = '\033[32m'  # green
O = '\033[33m'  # orange
B = '\033[34m'  # blue
P = '\033[35m'  # purple
C = '\033[36m'  # cyan
GR = '\033[37m'  # gray


# Set up logging
logger = logging.getLogger('localizer')
logger.setLevel(logging.DEBUG)
_console_logger = logging.StreamHandler()
_console_logger.setLevel(logging.ERROR)
_console_logger.setFormatter(logging.Formatter('%(name)s - %(levelname)s: %(message)s'))
logger.addHandler(_console_logger)

# Set up web server
PORT = 80
httpd = None
httpd_signal = Event()


def set_serve(value):
    global serve
    serve = value

    if serve:
        start_httpd()
    else:
        shutdown_httpd()


def restart_httpd():
    shutdown_httpd()
    start_httpd()


def shutdown_httpd():
    global httpd
    if httpd is not None:
        httpd_signal.set()
        logger.info("Shutting down http server")
        httpd.join()
        httpd_signal.clear()
        httpd = None


def start_httpd():
    global httpd
    if httpd is not None:
        shutdown_httpd()
    else:
        logger.info("Starting http server in {}".format(params.path))
        httpd = HTTPThread(httpd_signal, PORT)
        httpd.start()



def set_debug(value):
    global debug
    debug = value
    if logger is not None:
        if debug:
            _console_logger.setLevel(logging.DEBUG)
        else:
            _console_logger.setLevel(logging.ERROR)

        logger.info("Debug set to {}".format(value))


# /dev/null, send output from programs so they don't print to screen.
DN = open(os.devnull, 'w')
ERRLOG = open(os.devnull, 'w')
OUTLOG = open(os.devnull, 'w')


@atexit.register
def cleanup():
    logging.shutdown()
