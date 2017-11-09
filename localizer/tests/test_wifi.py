import localizer
from localizer import wifi
from threading import Event
import queue
import time
import unittest


class TestWifi(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if localizer.params.iface is None:
            localizer.params.iface = wifi.get_first_interface()
        if localizer.params.path is None:
            localizer.params.path = '/tmp'

    def test_1_params_valid(self):
        self.assertTrue(localizer.params.validate_wifi(), msg=("Invalid parameters:\n"+str(localizer.params)))

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
        _command_queue = queue.Queue()
        _flag = Event()
        _thread = wifi.ChannelHopper(_command_queue, _flag, localizer.params.iface)
        _thread.start()

        _command_queue.put((localizer.params.duration, localizer.params.hop_int))
        _flag.set()

        _original_channel = wifi.get_channel(localizer.params.iface)
        _channel_changed = False
        # Check channel changes at least once during duration:
        print()
        for t in range(1, localizer.params.duration):
            _current_channel = wifi.get_channel(localizer.params.iface)
            if _current_channel != _original_channel and not _channel_changed:
                _channel_changed = True

            # Display timer
            print("Time elapsed: {:>2}s/{}s\r".format(t, localizer.params.duration), end='')
            time.sleep(1)
        print()

        _command_queue.join()

        self.assertTrue(_channel_changed)


# Script can be run standalone to test the antenna
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test wifi adapter mode change and channel changing")
    parser.add_argument("duration",
                        help="Number of seconds to run the test",
                        type=int,
                        nargs='?',
                        default=localizer.params.duration)
    parser.add_argument("iface",
                        help="Interface to test",
                        nargs='?',
                        default=wifi.get_first_interface())
    parser.add_argument("interval",
                        help="Number of seconds between channel hops",
                        type=float,
                        nargs='?',
                        default=localizer.params.hop_int)
    arguments = parser.parse_args()

    try:
        localizer.params.duration = arguments.duration
        localizer.params.iface = arguments.iface
        localizer.params.hop_int = arguments.interval
    except ValueError:
        print("Invalid parameters")
        exit(1)

    import sys
    sys.argv = sys.argv[:1]
    unittest.main()
