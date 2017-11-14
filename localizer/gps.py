import csv
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

    def __init__(self, response_queue, event_flag, duration, nmea_output, csv_output):
        """
        GPS Thread that, when started and when the flag is raised, records the time and GPS location
        """

        super().__init__()

        module_logger.info("Starting GPS Logging Thread")

        self.daemon = True
        self._response_queue = response_queue
        self._event_flag = event_flag
        self._duration = duration
        self._nmea_output = nmea_output
        self._csv_output = csv_output

    def run(self):
        module_logger.info("Executing gps thread")

        gps_sentences = {}

        # Wait for synchronization signal
        self._event_flag.wait()

        _start_time = time.time()
        gpspipe = Popen(['gpspipe', '-r', '-uu', '-o', self._nmea_output])

        # Capture gps data for <duration> seconds
        t = time.time() + self._duration
        while time.time() < t:
            gps_sentences[time.time()] = gpsd.get_current()
            time.sleep(_gps_update_frequency)

        module_logger.info("Terminating gpspipe")
        gpspipe.terminate()

        _end_time = time.time()
        module_logger.info("Captured gps data for {:.2f}s (expected {}s)".format(_end_time-_start_time, self._duration))

        # Set up average coordinate
        _avg_lat = 0
        _avg_lon = 0
        _avg_alt = 0
        _avg_lat_err = 0
        _avg_lon_err = 0
        _avg_alt_err = 0
        _lat_err_count = 0
        _lon_err_count = 0
        _alt_err_count = 0

        # Write GPS coordinates to CSV
        with open(self._csv_output, 'w', newline='') as nmea_csv:

            fieldnames = ['timestamp', 'lat', 'lon', 'alt', 'lat_err', 'lon_error', 'alt_error']
            nmea_csv_writer = csv.DictWriter(nmea_csv, dialect="unix", fieldnames=fieldnames)
            nmea_csv_writer.writeheader()

            for tstamp, msg in gps_sentences.items():

                _avg_lat += msg.lat
                _avg_lon += msg.lon
                _avg_alt += msg.alt


                lat_err = None
                lon_err = None
                alt_err = None
                if 'y' in msg.error:
                    lat_err = msg.error['y']
                    _lat_err_count += 1
                if 'x' in msg.error:
                    lon_err = msg.error['x']
                    _lon_err_count += 1
                if 'v' in msg.error:
                    alt_err = msg.error['v']
                    _alt_err_count += 1

                nmea_csv_writer.writerow({fieldnames[0]: tstamp,
                                         fieldnames[1]: msg.lat,
                                         fieldnames[2]: msg.lon,
                                         fieldnames[3]: msg.alt,
                                         fieldnames[4]: lat_err,
                                         fieldnames[5]: lon_err,
                                         fieldnames[6]: alt_err})

        # Finish calculating coordinate average
        _avg_lat /= len(gps_sentences)
        _avg_lon /= len(gps_sentences)
        _avg_alt /= len(gps_sentences)
        _avg_lat_err /= _lat_err_count
        _avg_lon_err /= _lon_err_count
        _avg_alt_err /= _alt_err_count

        # Confirm capture file contains gps coordinates
        if os.path.isfile(self._nmea_output) and os.path.isfile(self._csv_output):
            module_logger.info("Successfully captured gps nmea data")
        else:
            module_logger.error("Could not capture gps nmea data")

        # send gps data back
        self._response_queue.put((_avg_lat, _avg_lon, _avg_alt, _avg_lat_err, _avg_lon_err, _avg_alt_err))
