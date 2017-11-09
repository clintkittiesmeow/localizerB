import localizer
from localizer.capture import CaptureThread
from threading import Event
import queue
import time
import unittest
import os


class TestCapture(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if localizer.params.iface is None:
            localizer.params.iface = localizer.wifi.get_first_interface()
        if localizer.params.path is None:
            localizer.params.path = '/tmp'

    def test_1_params_valid(self):
        self.assertTrue(localizer.params.validate_capture(), msg=("Invalid parameters:\n"+str(localizer.params)))

    def test_2_packet_capture(self):
        _command_queue = queue.Queue()
        _response_queue = queue.Queue()
        _flag = Event()
        _thread = CaptureThread(_command_queue, _response_queue, _flag, localizer.params.iface)
        _thread.start()
        _tmp_path = os.path.join(localizer.params.path, 'tmp.pcapng')

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
        num_rcv, num_drop = _response_queue.get()
        _response_queue.task_done()

        print("Received {} packets (dropped {} packets)".format(num_rcv, num_drop))
        self.assertGreater(num_rcv, 0, "Failed to capture any packets")
        self.assertEqual(num_drop, 0, "Dropped packets")

        self.assertTrue(os.path.isfile(_tmp_path), msg="Failed to create packet capture")
        # Cleanup file
        os.remove(_tmp_path)
        self.assertFalse(os.path.isfile(_tmp_path), msg="Failed to remove packet capture")


# Script can be run standalone
if __name__ == "__main__":
    import argparse
    from localizer import wifi

    parser = argparse.ArgumentParser(description="Test packet capture by capturing from dumpcap")
    parser.add_argument("duration",
                        help="Number of seconds to run the test",
                        type=int,
                        nargs='?',
                        default=localizer.params.duration)
    parser.add_argument("iface",
                        help="Interface to test",
                        nargs='?',
                        default=wifi.get_first_interface())
    parser.add_argument("path",
                        help="Temporary path to write test output",
                        nargs='?',
                        default='/tmp')
    arguments = parser.parse_args()

    try:
        localizer.params.duration = arguments.duration
        localizer.params.iface = arguments.iface
        localizer.params.path = arguments.path
    except ValueError:
        print("Invalid parameters")
        exit(1)

    import sys

    sys.argv = sys.argv[:1]
    unittest.main()
