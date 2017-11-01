import logging
import shutil
import os
import threading
import time
import pyshark
import csv
import localizer
import queue
import sys
import gpsd
from subprocess import PIPE, run

from localizer import antenna, wifi, gps


class Capture:
    def __init__(self, iface, duration, degrees, bearing, test=None):
        """
        A capture class that will coordinate antenna rotation and capture.

        :param iface: The interface to capture from
        :type iface: str
        :param duration: The time in seconds to complete a capture
        :type duration: int
        :param degrees: The number of degrees to rotate for the capture
        :type degrees: float
        :param bearing: The initial bearing of the antenna
        :type bearing: float
        :param test: Optional test parameter that is added to the working directory path for output
        :type test: str
        """

        super().__init__()

        self._test = test
        self._capture_path = localizer.working_directory
        self._iface = iface
        self._duration = duration
        self._degrees = degrees
        self._bearing = bearing

        # Set up working folder
        os.umask(0)
        if self._test is not None:  # If we have a test specified, put everything in that folder
            self._capture_path = os.path.join(self._capture_path, self._test)
        self._capture_path = os.path.join(self._capture_path, time.strftime('%Y%m%d-%H-%M-%S'))

        try:
            os.makedirs(self._capture_path, exist_ok=True)
        except OSError as e:
            logging.getLogger('global').error("Could not create the working directory {} ({})"
                                              .format(self._capture_path, e))
            exit(1)

        # Make sure we can write to the folder
        if not os.access(self._capture_path, os.W_OK | os.X_OK):
            logging.getLogger('global').error("Could not write to the working directory {}".format(self._capture_path))
            exit(1)

        # Create capture file names
        self._capture_file_gps = os.path.join(self._capture_path, time.strftime('%Y%m%d-%H-%M-%S') + ".nmea")
        self._capture_file_pcap = os.path.join(self._capture_path, time.strftime('%Y%m%d-%H-%M-%S') + ".pcapng")
        self._csv_file = os.path.join(self._capture_path, time.strftime('%Y%m%d-%H-%M-%S') + ".csv")

        # Threading sync flag
        self._flag = threading.Event()

        # Set up gps thread
        self._gps_command_queue = queue.Queue()
        self._gps_response_queue = queue.Queue()
        self._gps_thread = gps.GPSThread(self._gps_command_queue,
                                         self._gps_response_queue,
                                         self._flag)
        self._gps_thread.start()

        # Set up antenna control thread
        self._antenna_command_queue = queue.Queue()
        self._antenna_response_queue = queue.Queue()
        self._antenna_thread = antenna.AntennaStepperThread(self._antenna_command_queue,
                                                            self._antenna_response_queue,
                                                            self._flag)
        self._antenna_thread.start()

        # Set up WiFi channel scanner thread
        self._channel_command_queue = queue.Queue()
        self._channel_hopper_thread = wifi.ChannelHopper(self._channel_command_queue,
                                                         self._flag,
                                                         self._iface)
        self._channel_hopper_thread.start()

        # Set up pcap thread
        self._capture_command_queue = queue.Queue()
        self._capture_response_queue = queue.Queue()
        self._capture_thread = CaptureThread(self._capture_command_queue,
                                             self._capture_response_queue,
                                             self._flag,
                                             self._iface,
                                             self._duration)
        self._capture_thread.start()

    def capture(self):
        """
        Executes the capture by managing the necessary threads and consolidating the results into a single csv file
        """

        # Ensure that gps has a 3D fix
        try:
            _time_waited = 0
            while gpsd.get_current().mode != 3:
                print("Waiting for {}s for 3D gps fix (current mode = '{}' - press 'CTRL-c to cancel)\r"
                      .format(_time_waited, gpsd.get_current().mode))
                time.sleep(1)
                _time_waited += 1
        except KeyboardInterrupt:
            print('\nCapture canceled.')
            return
        else:
            print('\n')

        # Set up commands
        self._gps_command_queue.put((self._duration, self._capture_file_gps))
        self._antenna_command_queue.put((self._duration, self._degrees, self._bearing))
        self._channel_command_queue.put((self._duration, .1))
        self._capture_command_queue.put((self._duration, self._capture_file_pcap))

        # Start threads
        self._flag.set()

        # Print out timer to console
        for sec in range(self._duration):
            print("Capturing packets for {}/{}s\r".format(str(sec+1), str(self._duration)), end="")
            sys.stdout.flush()
            time.sleep(1)

        print("\nProcessing results...")
        sys.stdout.flush()

        # Get results
        self._channel_command_queue.join()

        self._capture_command_queue.join()
        while not self._capture_response_queue.empty():
            print(self._capture_response_queue.get_nowait())
            self._capture_response_queue.task_done()

        self._antenna_command_queue.join()
        _antenna_results = self._antenna_response_queue.get()
        self._antenna_response_queue.task_done()

        self._gps_command_queue.join()
        _gps_results = self._gps_response_queue.get()
        self._gps_response_queue.task_done()

        _packet_count = 0

        # Build CSV of beacons from pcap and antenna_results
        with open(self._csv_file,  'w', newline='') as csvfile:

            # Read pcapng into memory
            cap = pyshark.FileCapture(self._capture_file_pcap, display_filter='wlan[0] == 0x80')
            fieldnames = ['timestamp', 'bssid', 'ssi', 'channel', 'bearing',
                          'lat', 'lon', 'alt', 'lat_err', 'lon_error', 'alt_error']
            pacwriter = csv.DictWriter(csvfile, dialect="unix", fieldnames=fieldnames)
            pacwriter.writeheader()

            for packet in cap:
                # Get time, bssid & db from packet
                ptime = float(packet.frame_info.time_epoch.main_field.show)
                pbssid = packet.wlan.bssid.main_field.show
                pssi = int(packet.wlan_radio.signal_dbm.main_field.show)
                pchannel = int(packet.wlan_radio.channel.main_field.show)
                pbearing = None
                plat = None
                plon = None
                palt = None
                plat_err = None
                plon_err = None
                palt_err = None

                # Lookup bearing in _antenna_results
                for tstamp, bearing in sorted(_antenna_results.items(), reverse=True):
                    if ptime >= tstamp:
                        pbearing = bearing
                        break

                assert pbearing is not None

                # Lookup coordinates in _gps_results
                for tstamp, message in sorted(_gps_results.items(), reverse=True):
                    if ptime >= tstamp:
                        plat = message.lat
                        plon = message.lon
                        palt = message.alt
                        if 'y' in message.error:
                            plat_err = message.error['y']
                        if 'x' in message.error:
                            plon_err = message.error['x']
                        if 'v' in message.error:
                            palt_err = message.error['v']
                        break

                assert plat is not None
                assert plon is not None
                assert palt is not None

                pacwriter.writerow({
                    fieldnames[0]: ptime,
                    fieldnames[1]: pbssid,
                    fieldnames[2]: pssi,
                    fieldnames[3]: pchannel,
                    fieldnames[4]: pbearing,
                    fieldnames[5]: plat,
                    fieldnames[6]: plon,
                    fieldnames[7]: palt,
                    fieldnames[8]: plat_err,
                    fieldnames[9]: plon_err,
                    fieldnames[10]: palt_err, })

                _packet_count += 1

        print("Processed {} beacons, exported to csv file ({})".format(_packet_count, self._csv_file))
        return


class CaptureThread(threading.Thread):
    def __init__(self, command_queue, response_queue, event_flag, iface, duration):

        super().__init__()

        logging.getLogger('global').info("Starting Packet Capture Thread")

        self.daemon = True
        self._command_queue = command_queue
        self._response_queue = response_queue
        self._event_flag = event_flag
        self._iface = iface
        self._duration = duration

        # Check for required system packages
        self._packet_cap_util = "dumpcap"
        self._pcap_params = ['-i', self._iface, '-B', '12', '-q']

        if shutil.which(self._packet_cap_util) is None:
            logging.getLogger('global').error("Required packet capture system tool '{}' is not installed"
                                              .format(self._packet_cap_util))
            exit(1)

        # Ensure we are in monitor mode
        if wifi.get_interface_mode(self._iface) != "monitor":
            wifi.set_interface_mode(self._iface, "monitor")
        assert(wifi.get_interface_mode(self._iface) == "monitor")

    def run(self):
        while True:
            # Get command from queue
            duration, output = self._command_queue.get()
            command = [self._packet_cap_util] + self._pcap_params + ["-a", "duration:{}".format(duration), "-w", output]

            # Wait for synchronization signal
            self._event_flag.wait()

            proc = run(command, stdout=PIPE, stderr=PIPE)

            # Respond with results
            lines = proc.stderr.split(b'\n')
            if len(lines) >= 4:
                self._response_queue.put(lines[2].decode().strip())
                self._response_queue.put(lines[3].decode().strip())

            _num_cap_idx = lines[2].decode().find("Packets captured: ")
            if _num_cap_idx >= 0:
                logging.getLogger('global').info("Captured {} packets"
                                                 .format(lines[2].decode().strip()[_num_cap_idx+18:]))

            self._command_queue.task_done()
            self._response_queue.join()
