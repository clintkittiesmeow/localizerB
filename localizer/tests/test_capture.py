import math
import os
import queue
import tempfile
import time
import unittest
from threading import Event

from tqdm import trange

import localizer
from localizer.capture import CaptureThread
from localizer.interface import get_first_interface


class TestCapture(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if localizer.meta.iface is None:
            localizer.meta.iface = get_first_interface()
        if localizer.meta.path is None:
            localizer.meta.path = tempfile.gettempdir()

        # Speed up tests
        localizer.meta.duration = 5

    def test_1_params_valid(self):
        self.assertTrue(localizer.meta.validate_capture(), msg=("Invalid parameters:\n" + str(localizer.meta)))

    def test_2_packet_capture(self):
        _response_queue = queue.Queue()
        _flag = Event()
        _dummyflag = Event()
        _tmp_path = os.path.join(localizer.meta.path, 'tmp.pcapng')
        _thread = CaptureThread(_response_queue,
                                _flag,
                                _dummyflag,
                                localizer.meta.iface,
                                localizer.meta.duration,
                                _tmp_path)
        _thread.start()
        _flag.set()

        # Display timer
        for sec in trange(localizer.meta.duration, desc="Executing test for {}s"
                .format((str(localizer.meta.duration)))):
            time.sleep(1)

        num_rcv, num_drop = _response_queue.get()
        _start, _end = _response_queue.get()

        self.assertEquals(math.floor(_end - _start - localizer.meta.duration), 0, "Capture took too long (> 1s difference)")
        print("Received {} packets (dropped {} packets)".format(num_rcv, num_drop))
        self.assertGreater(num_rcv, 0, "Failed to capture any packets")
        self.assertEqual(num_drop, 0, "Dropped packets")

        self.assertTrue(os.path.isfile(_tmp_path), msg="Failed to create packet capture")
        # Cleanup file
        os.remove(_tmp_path)
        self.assertFalse(os.path.isfile(_tmp_path), msg="Failed to remove packet capture")

        _thread.join()


# Script can be run standalone
if __name__ == "__main__":
    import argparse
    from localizer import interface

    parser = argparse.ArgumentParser(description="Test packet capture by capturing from dumpcap")
    parser.add_argument("duration",
                        help="Number of seconds to run the test",
                        type=int,
                        nargs='?',
                        default=localizer.meta.duration)
    parser.add_argument("iface",
                        help="Interface to test",
                        nargs='?',
                        default=interface.get_first_interface())
    parser.add_argument("path",
                        help="Temporary path to write test output",
                        nargs='?',
                        default=tempfile.gettempdir())
    arguments = parser.parse_args()

    try:
        localizer.meta.duration = arguments.duration
        localizer.meta.iface = arguments.iface
        localizer.meta.path = arguments.path
    except ValueError:
        print("Invalid parameters")
        exit(1)

    import sys

    sys.argv = sys.argv[:1]
    unittest.main()
