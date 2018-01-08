import queue
import time
import unittest
from threading import Event

from tqdm import trange

import localizer
from localizer.antenna import AntennaStepperThread

_

class TestAntenna(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Speed up tests

        localizer.meta.duration = 5

    def test_1_params_valid(self):
        self.assertTrue(localizer.meta.validate_antenna(), msg=("Invalid parameters:\n" + str(localizer.meta)))

    def test_2_antenna_rotation(self):
        _response_queue = queue.Queue()
        _flag = Event()
        _thread = AntennaStepperThread(_response_queue,
                                       _flag,
                                       localizer.meta.duration,
                                       localizer.meta.degrees,
                                       localizer.meta.bearing)
        _thread.start()

        _flag.set()

        # Display timer
        for sec in trange(localizer.meta.duration, desc="Executing test for {}s"
                .format((str(localizer.meta.duration)))):
            time.sleep(1)

        loop_start_time, loop_stop_time, loop_expected_time, loop_average_time = _response_queue.get()

        self.assertGreater(loop_stop_time, loop_start_time, msg="Somethings horribly wrong")

        print("Antenna test complete (total time: {}s)".format(loop_stop_time - loop_start_time))
        print("\tExpected loop time:\t{:.15f}s".format(loop_expected_time))
        print("\tActual loop time:\t{:>.15f}s".format(loop_average_time))
        print("\tActual loop time {:.2%} longer than expected".format(
            (loop_average_time - loop_expected_time) / loop_expected_time))

        self.assertAlmostEqual(loop_expected_time, loop_average_time, msg="Antenna loop is too slow")

        _thread.join()


# Script can be run standalone to test the antenna
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test antenna by rotating it [degrees] in [seconds]")
    parser.add_argument("duration",
                        help="Number of seconds to run the test",
                        type=int,
                        nargs='?',
                        default=localizer.meta.duration)
    parser.add_argument("degrees",
                        help="Number of degrees to rotate the antenna",
                        type=float,
                        nargs='?',
                        default=localizer.meta.degrees)
    parser.add_argument("bearing",
                        help="Starting bearing of the antenna",
                        type=float,
                        nargs='?',
                        default=localizer.meta.bearing)
    arguments = parser.parse_args()

    try:
        localizer.meta.duration = arguments.duration
        localizer.meta.degrees = arguments.degrees
        localizer.meta.bearing = arguments.bearing_magnetic
    except ValueError:
        print("Invalid parameters")
        exit(1)

    import sys

    sys.argv = sys.argv[:1]
    unittest.main()
