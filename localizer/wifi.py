# Modified from wifite.py:

from subprocess import Popen, call, PIPE
import os
import atexit
import threading
import logging
import time
import shutil

# /dev/null, send output from programs so they don't print to screen.
DN = open(os.devnull, 'w')
ERRLOG = open(os.devnull, 'w')
OUTLOG = open(os.devnull, 'w')

# Global Constants
IEEE80211bg=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
IEEE80211bg_intl=IEEE80211bg + [12, 13, 14]
IEEE80211a=[36, 40, 44, 48, 52, 56, 60, 64, 149, 153, 157, 161]
IEEE80211bga=IEEE80211bg + IEEE80211a
IEEE80211bga_intl=IEEE80211bg_intl + IEEE80211a

# Make sure required system tools are installed
if shutil.which("iwconfig") is None:
    logging.error("Required system tool 'iwconfig' is not installed")
    exit(1)
if shutil.which("ifconfig") is None:
    logging.error("Required system tool 'ifconfig' is not installed")
    exit(1)

def set_interface_mode(iface, mode):
    """
    Uses ifconfig and iwconfig to put a device into specified mode (eg monitor, managed, etc).

    :param iface str: Name of interface to set the mode on
    :param mode str: New mode to set the interface to
    :return: Returns whether setting the interface mode was successful
    :rtype: bool
    """

    try:
        interfaces = get_interfaces()
        if iface not in interfaces:
            raise ValueError("Interface {} is not a valid interface".format(iface))

        logging.info("Enabling {} mode on {}".format(mode, iface))
        call(['ifconfig', iface, 'down'], stdout=DN, stderr=DN)
        call(['iwconfig', iface, 'mode', mode], stdout=DN, stderr=DN)
        call(['ifconfig', iface, 'up'], stdout=DN, stderr=DN)

        # Validate mode of interface
        interfaces = get_interfaces()
        if interfaces[iface]["mode"] == mode:
            logging.info("Finished enabling {} mode on {}".format(mode, iface))
            return True
        else:
            raise ValueError("Failed putting interface {} into {} mode; interface currently in {} mode"
                             .format(iface, mode, interfaces[iface]["mode"]))

    except (KeyError, ValueError) as e:
        logging.error(e)
        return False


def get_interface_mode(iface):
    try:
        return get_interfaces()[iface]["mode"]
    except  KeyError as e:
        logging.error("No interface '{}'".format(iface))
        return None


def get_interfaces():
    """
    Queries iwconfig and builds a dictionary of interfaces and their properties

    :return: A dictionary with keys as interface name (str) and value as dictionary of key/value pairs
    :rtype: dict
    """

    try:
        proc = Popen(['iwconfig'], stdout=PIPE, stderr=DN)

        # Loop through all the lines and build a dictionary of interfaces
        interfaces = {}
        current_interface = None
        for line in proc.communicate()[0].split(b'\n'):
            line = line.decode().rstrip()
            if len(line.strip()) == 0: continue                         # Continue on blank lines
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
        logging.error(e)
        return None


class ChannelHopper(threading.Thread):
    def __init__(self, command_queue, event_flag, iface, channels=IEEE80211bg):
        """
        Wait for commands on the queue and asynchronously change channels of wireless interface with specified timing.

        :param command_queue queue.Queue: A queue to read commands in the format (iface, iterations, interval)
        :param channels list[int]: A list of channels to iterate over
        """

        super(ChannelHopper, self).__init__()
        self.daemon = True
        self._iface = iface
        self._command_queue = command_queue
        self._event_flag = event_flag
        self._channels = channels

        logging.info("Starting Channel Hopper Thread")

        # Ensure we are in monitor mode
        if get_interface_mode(self._iface) != "monitor":
            set_interface_mode(self._iface, "monitor")
        assert(get_interface_mode(self._iface) == "monitor")

        # Set channel to first channel
        call(['iwconfig', self._iface, 'channel', str(self._channels[0])], stdout=DN, stderr=DN)

    def run(self):
        while True:
            duration, interval = self._command_queue.get()
            len_of_channels = len(self._channels)

            # Wait for synchronization signal
            self._event_flag.wait()

            # HOP CHANNELS https://github.com/elBradford/snippets/blob/master/chanhop.sh
            for i in range(round(duration/interval)):
                call(['iwconfig', self._iface, 'channel', str(self._channels[i%len_of_channels])], stdout=DN, stderr=DN)
                time.sleep(interval)
            self._command_queue.task_done()


@atexit.register
def cleanup():
    """
    Cleanup - ensure all devices are no longer in monitor mode
    """

    logging.info("Cleaning up all monitored interfaces")
    ifaces = get_interfaces()

    for iface in ifaces:
        if iface["mode"] == "monitor":
            set_interface_mode(iface, "managed")