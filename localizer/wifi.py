import atexit
import logging
import re
import shutil
import threading
import time
from subprocess import call, run, PIPE, CalledProcessError

from tqdm import tqdm

import localizer

# Global Constants
IEEE80211bg = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
IEEE80211bg_intl = IEEE80211bg + [12, 13, 14]
IEEE80211a = [36, 40, 44, 48, 52, 56, 60, 64, 149, 153, 157, 161]
IEEE80211bga = IEEE80211bg + IEEE80211a
IEEE80211bga_intl = IEEE80211bg_intl + IEEE80211a
TU = 1024/1000000  # 1 TU = 1024 usec https://en.wikipedia.org/wiki/TU_(Time_Unit)
STD_BEACON_INT = 100*TU
OPTIMAL_BEACON_INT = 179*TU
STD_CHANNEL_DISTANCE = 1

module_logger = logging.getLogger(__name__)

# Make sure required system tools are installed
if shutil.which("iwconfig") is None:
    module_logger.error("Required system tool 'iwconfig' is not installed")
    exit(1)
if shutil.which("ifconfig") is None:
    module_logger.error("Required system tool 'ifconfig' is not installed")
    exit(1)
if shutil.which("iwlist") is None:
    module_logger.error("Required system tool 'iwlist' is not installed")
    exit(1)


def set_interface_mode(iface, mode):
    """
    Uses ifconfig and iwconfig to put a device into specified mode (eg monitor, managed, etc).

    :param iface: Name of interface to set the mode on
    :type iface: str
    :param mode: New mode to set the interface to
    :type mode: str
    :return: Returns whether setting the interface mode was successful
    :rtype: bool
    """

    try:
        interfaces = get_interfaces()
        if iface not in interfaces:
            raise ValueError("Interface {} is not a valid interface; {}".format(iface, interfaces.keys()))

        module_logger.info("Enabling {} mode on {}".format(mode, iface))
        call(['ifconfig', iface, 'down'], stdout=localizer.DN, stderr=localizer.DN)
        call(['iwconfig', iface, 'mode', mode], stdout=localizer.DN, stderr=localizer.DN)
        call(['ifconfig', iface, 'up'], stdout=localizer.DN, stderr=localizer.DN)

        # Validate mode of interface
        interfaces = get_interfaces()
        if interfaces[iface]["mode"] == mode:
            module_logger.info("Finished enabling {} mode on {}".format(mode, iface))
            return True
        else:
            raise ValueError("Failed putting interface {} into {} mode; interface currently in {} mode"
                             .format(iface, mode, interfaces[iface]["mode"]))

    except (KeyError, ValueError, CalledProcessError) as e:
        module_logger.error(e)
        return False


def get_interface_mode(iface):
    """
    Get the current mode of an interface

    :param iface: Interface to query for mode
    :type iface: str
    :return: Mode of interface
    :rtype: str
    """

    try:
        return get_interfaces()[iface]["mode"]
    except KeyError:
        module_logger.error("No interface '{}'".format(iface))
        return None


def get_interfaces():
    """
    Queries iwconfig and builds a dictionary of interfaces and their properties

    :return: A dictionary with keys as interface name (str) and value as dictionary of key/value pairs
    :rtype: dict
    """

    try:
        proc = run(['iwconfig'], stdout=PIPE, stderr=localizer.DN)

        # Loop through all the lines and build a dictionary of interfaces
        interfaces = {}
        current_interface = None
        for line in proc.stdout.split(b'\n'):
            line = line.decode().rstrip()
            if len(line.strip()) == 0:
                continue                                                # Continue on blank lines
            if line[0] != ' ':                                           # Doesn't start with space
                current_line = line.split('  ')                             # Prepare the line
                current_interface = current_line[0]            # Parse the interface
                interfaces[current_interface] = {}                      # Set up new interface in dictionary
                line = '  '.join(current_line[1:])                     # Reset current line without interface
            if current_interface is not None:                           # Grab values and put them in dict
                line = line.strip().lower()
                line_values = line.strip().split('  ')                 # Split by two spaces
                for value in line_values:                               # Step through each value on the first line
                    value = value.strip()                               # Clean up our value
                    if value.find(':') == -1:                          # Check for colon-separated values
                        interfaces[current_interface][value] = None     # Put in dict
                    else:                                               # Put key/value in dict
                        value_split = value.split(':')
                        interfaces[current_interface][value_split[0].strip()] = value_split[1].strip()
            else:
                raise ValueError("Unexpected iwconfig response: {}".format(line))

        return interfaces

    except (ValueError, IndexError) as e:
        module_logger.error(e)
        return None


def get_first_interface():
    """
    Returns the name of the first interface, or None if none are present on the system.

    :return: First wlan interface
    :rtype: str
    """

    ifaces = get_interfaces()
    if ifaces is not None and len(list(ifaces)) > 0:
        return list(ifaces)[0]
    else:
        return None


def get_channel(iface):
    """
    Returns the channel the specified interface is on, or zero if it can't be determined

    :param iface: Interface to query for channel
    :type iface: str
    :return: Channel
    :rtype: int
    """

    proc = run(['iwlist', iface, 'channel'], stdout=PIPE, stderr=PIPE)

    # Respond with actual
    lines = proc.stdout
    match = re.search('(?<=\(Channel\s)(\d{1,2})', lines.decode())
    if match is not None:
        return match.group()
    else:
        return 0


def set_channel(iface, channel):
    """
    Sets the channel of the specified interface

    :param iface: Interface to set the channel
    :type iface: str
    :param channel: Channel number to set the interface to
    :type channel: str
    :return: True for success, False for failure
    :rtype: bool
    """

    try:
        call(['iwconfig', iface, 'channel', channel], stdout=localizer.DN, stderr=localizer.DN)
        return True
    except CalledProcessError:
        return False


class ChannelHopper(threading.Thread):
    def __init__(self, event_flag, iface, duration, hop_int=OPTIMAL_BEACON_INT, response_queue=None, distance=STD_CHANNEL_DISTANCE, init_chan=None, channels=IEEE80211bg):
        """
        Wait for commands on the queue and asynchronously change channels of wireless interface with specified timing.

        :param command_queue queue.Queue: A queue to read commands in the format (iface, iterations, hop_int)
        :param channels list[int]: A list of channels to iterate over
        """

        super().__init__()

        module_logger.info("Starting Channel Hopper Thread")

        self.daemon = True
        self._event_flag = event_flag
        self._iface = iface
        self._duration = duration
        self._hop_int = hop_int
        self._distance = distance
        self._response_queue = response_queue
        self._channels = channels

        # Validate initial channel, if given
        self._init_chan = init_chan
        if self._init_chan and self._init_chan not in self._channels:
            raise ValueError("If you specify an initial channel, it must be in the list of channels")


        # Ensure we are in monitor mode
        if get_interface_mode(self._iface) != "monitor":
            set_interface_mode(self._iface, "monitor")
        assert(get_interface_mode(self._iface) == "monitor")

    def run(self):

        _chan_len = len(self._channels)

        # Build local channel str list for speed
        _channels = [str(channel) for channel in self._channels]

        # Initial channel position - will cycle through all in _channels
        if self._init_chan:
            _chan = self._channels.index(self._init_chan)
        else:
            _chan = 0
        set_channel(self._iface, _channels[_chan])  # Set channel to first channel

        # Wait for synchronization signal
        self._event_flag.wait()

        _start_time = time.time()
        _stop_time = _start_time + self._duration

        # Only hop channels if we have a list of channels to hop, and our duration is greater than 0
        if self._hop_int > 0 and len(self._channels) > 1:

            # HOP CHANNELS https://github.com/elBradford/snippets/blob/master/chanhop.sh
            while _stop_time > time.time():
                time.sleep(self._hop_int)
                _chan = (_chan + self._distance) % _chan_len
                set_channel(self._iface, _channels[_chan])

        else:
            time.sleep(_stop_time - time.time())

        _end_time = time.time()

        if self._response_queue is not None:
            self._response_queue.put((_start_time, _end_time))
        module_logger.info("Hopped {} channels for {:.2f}s (expected {}s)"
                           .format(len(self._channels), _end_time-_start_time, self._duration))


@atexit.register
def cleanup():
    """
    Cleanup - ensure all devices are no longer in monitor mode
    """

    ifaces = get_interfaces()
    ifaces_to_cleanup = [iface for iface in ifaces if ifaces[iface]["mode"] == "monitor"]

    if ifaces_to_cleanup:
        module_logger.info("Cleaning up all monitored interfaces")
        for iface in tqdm(ifaces_to_cleanup, desc="{:<35}".format("Restoring ifaces to managed mode")):
            set_interface_mode(iface, "managed")
