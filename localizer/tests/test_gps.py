import localizer
from localizer import gps
from threading import Event
import queue
import time
import unittest
import os
import gpsd


class TestGPS(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if localizer.params.path is None:
            localizer.params.path = '/tmp'

    def test_1_params_valid(self):
        self.assertTrue(localizer.params.validate_gps(), msg=("Invalid parameters:\n"+str(localizer.params)))

    def test_2_gps_enabled(self):
        gpsd.connect()
        try:
            device = gpsd.device()
        except KeyError:
            self.fail("Failed to connect to gpsd and gps device")

    def test_3_gps_capture(self):
        _command_queue = queue.Queue()
        _response_queue = queue.Queue()
        _flag = Event()
        _thread = gps.GPSThread(_command_queue, _response_queue, _flag)
        _thread.start()
        _tmp_path = os.path.join(localizer.params.path, 'tmp.nmea')

        _command_queue.put((localizer.params.duration, _tmp_path))
        _flag.set()

        # Display timer
        print()
        for t in range(1, localizer.params.duration):
            # Display timer
            print("Time elapsed: {:>2}s/{}s\r".format(t, localizer.params.duration), end='')
            time.sleep(1)
        print()

        _command_queue.join()

        gps_sentences = _response_queue.get()
        _response_queue.task_done()
        self.assertGreater(len(gps_sentences), 0, msg="Failed to capture NMEA data from gpsd")

        self.assertTrue(os.path.isfile(_tmp_path), msg="Failed to create packet capture")
        # Cleanup file
        os.remove(_tmp_path)
        self.assertFalse(os.path.isfile(_tmp_path), msg="Failed to remove packet capture")


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
                        default='/tmp')
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
