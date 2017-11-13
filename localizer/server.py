import http.server
import logging
import socketserver
import threading
from time import sleep

module_logger = logging.getLogger('localizer.server')

class HTTPThread(threading.Thread):
    """
    Simple HTTP server that will serve the files in the current working directory
    """

    def __init__(self, flag, port):

        self._flag = flag
        self._httpd = socketserver.TCPServer(("", port), http.server.SimpleHTTPRequestHandler)

        super().__init__()

    def run(self):

        self._httpd.serve_forever()

        while not self._flag.is_set():
            sleep(.5)
