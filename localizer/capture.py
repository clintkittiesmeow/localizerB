import logging
import shutil
import os
import threading

from localizer import antenna
from localizer import wifi
import queue

class Capture():
    def __init__(self, iface, duration, degrees=360, bearing=0, capture_path=None):
        """
        A capture class that will coordinate antenna rotation and capture.

        :param iface str: The interface to capture from
        :param duration int: The time in seconds to complete a capture
        :param degrees float: The number of degrees to rotate for the capture
        :param bearing float: The initial bearing of the antenna
        :param capture_path str: Absolute path to use as a working directory. If not provided, default YYYYMMDD-HH-MM-SS in the working directory is attempted.
        """

        super(Capture, self).__init__()

        self._capture_path = capture_path
        self._iface = iface
        self._duration = duration
        self._degrees = degrees
        self._bearing = bearing

        # Set up working folder
        if self._capture_path is None:
            import time
            self._capture_path = os.path.join(os.getcwd(), time.strftime('%Y%m%d-%H-%M-%S'))

        try:
            os.makedirs(self._capture_path, exist_ok=True)
        except OSError as e:
            logging.error("Could not create the working directory {} ({})".format(self._capture_path, e))
            exit(1)

        # Make sure we can write to the folder
        if not os.access(self._capture_path, os.W_OK):
            logging.error("Could not write to the working directory {}".format(self._capture_path))
            exit(1)

        # Threading sync flag
        self._flag = threading.Event()

        # Set up antenna control thread
        self._antenna_command_queue = queue.Queue()
        self._antenna_response_queue = queue.Queue()
        self._antenna_thread = antenna.AntennaStepperThread(self._antenna_command_queue, self._antenna_response_queue, self._flag)
        self._antenna_thread.start()

        # Set up WiFi channel scanner thread
        self._channel_command_queue = queue.Queue()
        self._channel_hopper_thread = wifi.ChannelHopper(self._channel_command_queue, self._flag, self._iface)
        self._channel_hopper_thread.start()

        # Set up pcap thread
        self._capture_command_queue = queue.Queue()
        self._capture_thread = CaptureThread(self._capture_command_queue, self._flag, self._iface, self._duration, self._capture_path)
        self._capture_thread.start()

    def capture(self):
        # Set up commands
        self._antenna_command_queue.put((self._duration, self._degrees, self._bearing))
        self._channel_command_queue.put((self._duration, .1))
        self._capture_command_queue.put(self._duration)

        # Start threads
        self._flag.set()

        # Print out timer to console
        for sec in range(round(self._duration)):
            print("Capturing packets for {}s/{}s\r".format(str(sec), str(self._duration)), end="")

        # Get results
        self._channel_command_queue.join()
        self._capture_command_queue.join()
        self._antenna_command_queue.join()
        antenna_results = self._antenna_response_queue.get()
        self._antenna_response_queue.task_done()

        # Build CSV of beacons from pcap and antenna_results





class CaptureThread(threading.Thread):
    def __init__(self, command_queue, event_flag, iface, duration, directory):
        super(CaptureThread, self).__init__()

        self._command_queue = command_queue
        self._event_flag = event_flag
        self._directory = directory
        self._iface = iface
        self._duration = duration

        # Check for required system packages
        packet_cap_util = "dumpcap"
        packet_cap_parameters = ["-i", self._iface, "-a", "duration:{}".format(self._duration), ]

        if shutil.which(packet_cap_util) is None:
            logging.error("Required packet capture system tool '{}' is not installed".format(packet_cap_util))
            exit(1)


    def run(self):
        while True:
            # Get command from queue
            duration = self._command_queue.get()

