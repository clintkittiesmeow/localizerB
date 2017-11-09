import localizer
from localizer.antenna import AntennaStepperThread
from threading import Event
import queue
import time
import unittest


class TestAntenna(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Speed up tests
        localizer.params.duration = 5

    def test_1_params_valid(self):
        self.assertTrue(localizer.params.validate_antenna(), msg=("Invalid parameters:\n"+str(localizer.params)))

    def test_2_antenna_rotation(self):
        _command_queue = queue.Queue()
        _response_queue = queue.Queue()
        _flag = Event()
        _thread = AntennaStepperThread(_command_queue, _response_queue, _flag)
        _thread.start()

        _command_queue.put((localizer.params.duration, localizer.params.degrees, localizer.params.bearing))
        _flag.set()

        # Display timer
        print()
        for t in range(1, localizer.params.duration):
            # Display timer
            print("Time elapsed: {:>2}s/{}s\r".format(t, localizer.params.duration), end='')
            time.sleep(1)
        print()

        _command_queue.join()
        loop_start_time, loop_stop_time, loop_expected_time, loop_average_time = _response_queue.get()
        _response_queue.task_done()

        self.assertGreater(loop_stop_time, loop_start_time, msg="Somethings horribly wrong")

        print("Antenna test complete (total time: {}s)".format(loop_stop_time - loop_start_time))
        print("\tExpected loop time:\t{:.15f}s".format(loop_expected_time))
        print("\tActual loop time:\t{:>.15f}s".format(loop_average_time))
        print("\tActual loop time {:.2%} longer than expected".format(
            (loop_average_time - loop_expected_time) / loop_expected_time))

        self.assertAlmostEqual(loop_expected_time, loop_average_time, msg="Antenna loop is too slow")


# Script can be run standalone to test the antenna
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test antenna by rotating it [degrees] in [seconds]")
    parser.add_argument("duration",
                        help="Number of seconds to rotate the antenna",
                        type=int,
                        default=localizer.params.duration)
    parser.add_argument("degrees",
                        help="Number of degrees to rotate the antenna",
                        type=float,
                        nargs='?',
                        default=localizer.params.degrees)
    parser.add_argument("bearing",
                        help="Starting bearing of the antenna",
                        type=float,
                        nargs='?',
                        default=localizer.params.bearing)
    arguments = parser.parse_args()

    try:
        localizer.params.duration = arguments.duration
        localizer.params.degrees = arguments.degrees
        localizer.params.bearing = arguments.bearing
    except ValueError:
        print("Invalid parameters")
        exit(1)

    import sys

    sys.argv = sys.argv[:1]
    unittest.main()
