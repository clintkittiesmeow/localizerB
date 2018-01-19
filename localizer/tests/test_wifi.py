import math
import queue
import tempfile
import time
import unittest
from threading import Event

from tqdm import tqdm

import localizer
from localizer import wifi


class TestWifi(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if localizer.meta.iface is None:
            localizer.meta.iface = wifi.get_first_interface()
        if localizer.meta.path is None:
            localizer.meta.path = tempfile.gettempdir()

        # Speed up tests
        localizer.meta.duration = 5

    def test_1_params_valid(self):
        self.assertTrue(localizer.meta.validate_wifi(), msg=("Invalid parameters:\n" + str(localizer.meta)))

    def test_2_set_mode(self):
        # Get all the interfaces
        ifaces = wifi.get_interfaces()
        self.assertIsNotNone(ifaces, msg="Parsing interfaces failed")
        ifaces_list = list(ifaces)
        self.assertTrue(len(ifaces_list)>0, msg="No wireless interfaces found")

        modes = ["monitor", "managed"]
        for mode in modes:
            for iface in ifaces:
                wifi.set_interface_mode(iface, mode)
                self.assertEqual(wifi.get_interface_mode(iface), mode,
                                 msg="Failed to enable {} mode on iface {}".format(mode, iface))

    def test_3_channel_hop(self):
        _flag = Event()
        _response_queue = queue.Queue()
        _thread = wifi.ChannelThread(_flag,
                                     localizer.meta.iface,
                                     localizer.meta.duration,
                                     localizer.meta.hop_int,
                                     _response_queue)
        _thread.start()
        _flag.set()

        _original_channel = wifi.get_channel(localizer.meta.iface)
        _channel_changed = False
        # Check channel changes at least once during duration:

        # Display timer
        with tqdm(range(localizer.meta.duration)) as pbar:
            for sec in pbar:
                _current_channel = wifi.get_channel(localizer.meta.iface)
                if _current_channel != _original_channel and not _channel_changed:
                    _channel_changed = True
                pbar.set_description("Current channel:{:>3}".format(_current_channel))
                time.sleep(1)

        self.assertTrue(_channel_changed)

        _start, _end = _response_queue.get()
        self.assertEquals(math.floor(_end - _start - localizer.meta.duration), 0, "Thread took too long (> 1s difference)")

        _thread.join()


# Script can be run standalone to test the antenna
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test wifi adapter mode change and channel changing")
    parser.add_argument("duration",
                        help="Number of seconds to run the test",
                        type=int,
                        nargs='?',
                        default=localizer.meta.duration)
    parser.add_argument("iface",
                        help="Interface to test",
                        nargs='?',
                        default=wifi.get_first_interface())
    parser.add_argument("interval",
                        help="Number of seconds between channel hops",
                        type=float,
                        nargs='?',
                        default=localizer.meta.hop_int)
    arguments = parser.parse_args()

    try:
        localizer.meta.duration = arguments.duration
        localizer.meta.iface = arguments.iface
        localizer.meta.hop_int = arguments.interval
    except ValueError:
        print("Invalid parameters")
        exit(1)

    import sys
    sys.argv = sys.argv[:1]
    unittest.main()
