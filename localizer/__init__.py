import atexit
import http.server
import logging
import os
import socketserver
from threading import Thread

from localizer.params import Params

# Shared Variables
debug = False
serve = False

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
package_logger = logging.getLogger('localizer')
package_logger.setLevel(logging.DEBUG)
_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.WARNING)
_console_handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s: %(message)s'))
package_logger.addHandler(_console_handler)

# Set up web server
PORT = 80
httpd = None
httpd_thread = None
socketserver.TCPServer.allow_reuse_address = True


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
    global httpd, httpd_thread

    if httpd is not None:
        package_logger.info("Shutting down http server")
        httpd.shutdown()
        httpd = None
        httpd_thread.join()
        httpd_thread = None


def start_httpd():
    global httpd, httpd_thread
    if httpd is not None or httpd_thread is not None:
        shutdown_httpd()

    package_logger.info("Starting http server in {}".format(os.getcwd()))
    httpd = socketserver.TCPServer(("", PORT), QuietSimpleHTTPRequestHandler)
    httpd_thread = Thread(target=httpd.serve_forever)
    httpd_thread.daemon = True
    httpd_thread.start()


# Working Directory
_working_dir = None


def set_working_dir(path):
    global _working_dir

    if path == _working_dir:
        return

    _current_dir = os.getcwd()

    try:
        # cd into directory
        os.chdir(path)
        _new_path = os.getcwd()

        # Try to write and remove a tempfile to the directory
        _tmpfile = os.path.join(_new_path, 'tmpfile')
        with open(_tmpfile, 'w') as fp:
            fp.write(" ")
        os.remove(_tmpfile)

        # restart httpd if it's running
        if serve:
            restart_httpd()

        _working_dir = _new_path
    except (PermissionError, TypeError):
        os.chdir(_current_dir)
        raise ValueError("Cannot write to working directory '{}'".format(path))
    except FileNotFoundError:
        os.chdir(_current_dir)
        raise ValueError("Invalid directory '{}'".format(path))


# A quiet implementation of SimpleHTTPRequestHandler
class QuietSimpleHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


def set_debug(value):
    global debug, _console_handler
    debug = value
    if package_logger is not None:
        if debug:
            _console_handler.setLevel(logging.DEBUG)
        else:
            _console_handler.setLevel(logging.WARNING)

        package_logger.info("Debug set to {}".format(value))


def load_macs(mac_path):
    import csv
    with open(mac_path, 'r', newline='') as mac_tsv:
        csv_reader = csv.DictReader(mac_tsv, dialect="unix", delimiter='\t')
        return [line['BSSID'] for line in csv_reader]


# /dev/null, send output from programs so they don't print to screen.
DN = open(os.devnull, 'w')
ERRLOG = open(os.devnull, 'w')
OUTLOG = open(os.devnull, 'w')


@atexit.register
def cleanup():
    logging.shutdown()
