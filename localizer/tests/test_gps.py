import os
import queue
import tempfile
import time
import unittest
from threading import Event

import gpsd
from tqdm import trange

import localizer
from localizer import gps


class TestGPS(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if localizer.params.path is None:
            localizer.params.path = tempfile.gettempdir()

        # Speed up tests
        localizer.params.duration = 5

    def test_1_params_valid(self):
        self.assertTrue(localizer.params.validate_gps(), msg=("Invalid parameters:\n"+str(localizer.params)))

    def test_2_gps_enabled(self):
        gpsd.connect()
        try:
            device = gpsd.device()
        except KeyError:
            self.fail("Failed to connect to gpsd and gps device")

    def test_3_gps_capture(self):
        _response_queue = queue.Queue()
        _flag = Event()
        _tmp_nmea = os.path.join(localizer.params.path, 'tmp.nmea')
        _tmp_csv = os.path.join(localizer.params.path, 'tmp.csv')
        _thread = gps.GPSThread(_response_queue, _flag, localizer.params.duration, _tmp_nmea, _tmp_csv)
        _thread.start()
        _flag.set()

        # Display timer
        for sec in trange(localizer.params.duration, desc="Executing test for {}s"
                .format((str(localizer.params.duration)))):
            time.sleep(1)

        _avg_lat, _avg_lon, _avg_alt, _avg_lat_err, _avg_lon_err, _avg_alt_err = _response_queue.get()
        _start, _end = _response_queue.get()

        self.assertAlmostEqual(_end-_start, localizer.params.duration, 0, "GPS Capture took too long (> 1s difference)")

        self.assertNotEqual(_avg_lat, 0, "Failed to get latitude")
        self.assertNotEqual(_avg_lon, 0, "Failed to get longitude")
        self.assertNotEqual(_avg_alt, 0, "Failed to get altitude")

        self.assertTrue(os.path.isfile(_tmp_nmea), msg="Failed to create NMEA capture")
        self.assertTrue(os.path.isfile(_tmp_csv), msg="Failed to create parsed NMEA capture")
        # Cleanup file
        os.remove(_tmp_nmea)
        os.remove(_tmp_csv)
        self.assertFalse(os.path.isfile(_tmp_nmea), msg="Failed to remove NMEA capture")
        self.assertFalse(os.path.isfile(_tmp_csv), msg="Failed to remove parsed NMEA capture")

        _thread.join()

# Script can be run standalone to test the antenna
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test gps by capturing from gpsd")
    parser.add_argument("duration",
                        help="Number of seconds to run the test",
                        type=int,
                        nargs='?',
                        default=localizer.params.duration)
    parser.add_argument("path",
                        help="Temporary path to write test output",
                        nargs='?',
                        default=tempfile.gettempdir())
    arguments = parser.parse_args()

    try:
        localizer.params.duration = arguments.duration
        localizer.params.path = arguments.path
    except ValueError:
        print("Invalid parameters")
        exit(1)

    import sys

    sys.argv = sys.argv[:1]
    unittest.main()
