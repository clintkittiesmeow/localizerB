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
        _tmp_path = os.path.join(localizer.params.path, 'tmp.nmea')
        _thread = gps.GPSThread(_response_queue, _flag, localizer.params.duration, _tmp_path)
        _thread.start()
        _flag.set()

        # Display timer
        for sec in trange(localizer.params.duration, desc="Executing test for {}s"
                .format((str(localizer.params.duration)))):
            time.sleep(1)

        gps_sentences = _response_queue.get()

        self.assertGreater(len(gps_sentences), 0, msg="Failed to capture NMEA data from gpsd")

        self.assertTrue(os.path.isfile(_tmp_path), msg="Failed to create packet capture")
        # Cleanup file
        os.remove(_tmp_path)
        self.assertFalse(os.path.isfile(_tmp_path), msg="Failed to remove packet capture")

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
