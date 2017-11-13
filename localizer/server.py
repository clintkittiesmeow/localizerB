import http.server
import socketserver
import threading
from time import sleep


class HTTPThread(threading.Thread):
    """
    Simple HTTP server that will serve the files in the current working directory
    """

    def __init__(self, flag, port):

        self._flag = flag
        self._httpd = socketserver.TCPServer(("", port), QuietSimpleHTTPRequestHandler)

        super().__init__()

    def run(self):

        self._httpd.serve_forever()

        while not self._flag.is_set():
            sleep(.5)

        self._httpd.shutdown()
        self._httpd.server_close()


# A quiet implementation of SimpleHTTPRequestHandler
class QuietSimpleHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
