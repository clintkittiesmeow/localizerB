import gpsd
import threading
import logging
import shutil
import time
import os
from subprocess import Popen

# initialize GPS information
if shutil.which("gpsd") is None:
    logging.getLogger('global').error("Required system tool 'gpsd' is not installed")
    exit(1)
if shutil.which("gpspipe") is None:
    logging.getLogger('global').error("Required system tool 'gpspipe' is not installed")
    exit(1)
gpsd.connect()
logging.getLogger('global').info("GPS device connected: {}".format(gpsd.device()))

# GPS Update frequency - Depends on hardware - eg BU-353-S4 http://usglobalsat.com/store/gpsfacts/bu353s4_gps_facts.html
_gps_update_frequency = 1


class GPSThread(threading.Thread):

    def __init__(self, command_queue, response_queue, event_flag):
        """
        GPS Thread that, when started and when the flag is raised, records the time and GPS location
        """

        super().__init__()

        logging.getLogger('global').info("Starting GPS Logging Thread")

        self.daemon = True
        self._command_queue = command_queue
        self._response_queue = response_queue
        self._event_flag = event_flag

    def run(self):
        while True:
            # Get command from command queue
            duration, output = self._command_queue.get()

            # Wait for synchronization signal
            self._event_flag.wait()

            gpspipe = Popen(['gpspipe', '-r', '-uu', '-o', output])

            gps_sentences = {}

            # Capture gps data for <duration> seconds
            t = time.time() + duration
            while time.time() < t:
                gps_sentences[time.time()] = gpsd.get_current()
                time.sleep(_gps_update_frequency)

            gpspipe.terminate()

            # Confirm capture file contains gps coordinates
            if os.path.isfile(output):
                logging.getLogger('global').info("Successfully captured gps nmea data")
            else:
                logging.getLogger('global').error("Could not capture gps nmea data")

            self._command_queue.task_done()

            # send gps data back
            self._response_queue.put(gps_sentences)
            self._response_queue.join()
