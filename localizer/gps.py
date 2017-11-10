import logging
import os
import shutil
import threading
import time
from subprocess import Popen

import gpsd

module_logger = logging.getLogger('localizer.gps')

# initialize GPS information
if shutil.which("gpsd") is None:
    module_logger.error("Required system tool 'gpsd' is not installed")
    exit(1)
if shutil.which("gpspipe") is None:
    module_logger.error("Required system tool 'gpspipe' is not installed")
    exit(1)
gpsd.connect()

try:
    dev = gpsd.device()
    module_logger.info("GPS device connected: {}".format(gpsd.device()))
except KeyError:
    module_logger.error("GPS device failed to initialize, please make sure that gpsd can see gps data")
    exit(1)

# GPS Update frequency - Depends on hardware - eg BU-353-S4 http://usglobalsat.com/store/gpsfacts/bu353s4_gps_facts.html
_gps_update_frequency = 1


class GPSThread(threading.Thread):

    def __init__(self, response_queue, event_flag, duration, output):
        """
        GPS Thread that, when started and when the flag is raised, records the time and GPS location
        """

        super().__init__()

        module_logger.info("Starting GPS Logging Thread")

        self.daemon = True
        self._response_queue = response_queue
        self._event_flag = event_flag
        self._duration = duration
        self._output = output

    def run(self):
        module_logger.info("Executing gps thread")

        gps_sentences = {}

        # Wait for synchronization signal
        self._event_flag.wait()

        _start_time = time.time()
        gpspipe = Popen(['gpspipe', '-r', '-uu', '-o', self._output])

        # Capture gps data for <duration> seconds
        t = time.time() + self._duration
        while time.time() < t:
            gps_sentences[time.time()] = gpsd.get_current()
            time.sleep(_gps_update_frequency)

        module_logger.info("Terminating gpspipe")
        gpspipe.terminate()

        _end_time = time.time()
        module_logger.info("Captured gps data for {:.2f}s (expected {}s)".format(_end_time-_start_time, self._duration))

        # Confirm capture file contains gps coordinates
        if os.path.isfile(self._output):
            module_logger.info("Successfully captured gps nmea data")
        else:
            module_logger.error("Could not capture gps nmea data")

        # send gps data back
        self._response_queue.put(gps_sentences)
