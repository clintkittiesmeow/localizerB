import csv
import logging
import os
import queue
import shutil
import threading
import time
from subprocess import PIPE, Popen

import gpsd
import pyshark
from tqdm import tqdm, trange

import localizer
from localizer import antenna, wifi, gps

module_logger = logging.getLogger('localizer.capture')

class Capture:
    def __init__(self, params=localizer.params):
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

        self._test = params.test
        self._capture_path = params.path
        self._iface = params.iface
        self._duration = params.duration
        self._degrees = params.degrees
        self._bearing = params.bearing
        self._hop_int = params.hop_int

        # Set up working folder
        os.umask(0)
        if self._test is not None:  # If we have a test specified, put everything in that folder
            self._capture_path = os.path.join(self._capture_path, self._test)
        self._capture_path = os.path.join(self._capture_path, time.strftime('%Y%m%d-%H-%M-%S'))

        try:
            os.makedirs(self._capture_path, exist_ok=True)
        except OSError as e:
            module_logger.error("Could not create the working directory {} ({})"
                                              .format(self._capture_path, e))
            exit(1)

        # Make sure we can write to the folder
        if not os.access(self._capture_path, os.W_OK | os.X_OK):
            module_logger.error("Could not write to the working directory {}".format(self._capture_path))
            exit(1)

        # Create capture file names
        self._capture_file_gps = os.path.join(self._capture_path, time.strftime('%Y%m%d-%H-%M-%S') + ".nmea")
        self._capture_file_pcap = os.path.join(self._capture_path, time.strftime('%Y%m%d-%H-%M-%S') + ".pcapng")
        self._output_csv_res = os.path.join(self._capture_path, time.strftime('%Y%m%d-%H-%M-%S') + "-results" + ".csv")
        self._output_csv_test = os.path.join(self._capture_path, time.strftime('%Y%m%d-%H-%M-%S') + "-test" + ".csv")

        # Threading sync flag
        self._initialize_flag = threading.Event()
        self._start_flag = threading.Event()

        module_logger.info("Setting up capture threads")

        # Show progress bar of creating threads
        with tqdm(total=4, desc="{:<35}".format("Setting up threads")) as pbar:

            # Set up gps thread
            self._gps_response_queue = queue.Queue()
            self._gps_thread = gps.GPSThread(self._gps_response_queue,
                                             self._start_flag,
                                             self._duration,
                                             self._capture_file_gps)
            self._gps_thread.start()
            pbar.update()
            pbar.refresh()

            # Set up antenna control thread
            self._antenna_response_queue = queue.Queue()
            self._antenna_thread = antenna.AntennaStepperThread(self._antenna_response_queue,
                                                                self._start_flag,
                                                                self._duration,
                                                                self._degrees,
                                                                self._bearing,
                                                                True)
            self._antenna_thread.start()
            pbar.update()
            pbar.refresh()

            # Set up pcap thread
            self._capture_response_queue = queue.Queue()
            self._capture_thread = CaptureThread(self._capture_response_queue,
                                                 self._initialize_flag,
                                                 self._start_flag,
                                                 self._iface,
                                                 self._duration,
                                                 self._capture_file_pcap)
            self._capture_thread.start()
            pbar.update()
            pbar.refresh()

            # Set up WiFi channel scanner thread
            self._channel_hopper_thread = wifi.ChannelHopper(self._start_flag,
                                                             self._iface,
                                                             self._duration,
                                                             self._hop_int)
            self._channel_hopper_thread.start()
            pbar.update()
            pbar.refresh()

    def capture(self):
        """
        Executes the capture by managing the necessary threads and consolidating the actual into a single csv file
        """

        module_logger.info("Waiting for GPS 3D fix")
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

        module_logger.info("Triggering synchronized threads")
        # Start threads
        self._initialize_flag.set()

        # Print out timer to console
        for sec in trange(self._duration, desc="{:<35}".format("Capturing packets for {}s".format((str(self._duration))))):
            time.sleep(1)

        # Show progress bar of getting thread results
        with tqdm(total=3, desc="{:<35}".format("Waiting for results")) as pbar:

            pbar.update()
            pbar.refresh()
            loop_start_time, loop_stop_time, loop_expected_time, loop_average_time = self._antenna_response_queue.get()

            pbar.update()
            pbar.refresh()
            _gps_results = self._gps_response_queue.get()

            pbar.update()
            pbar.refresh()
            _capture_result_cap, _capture_result_drop = self._capture_response_queue.get()
            module_logger.info("Captured {} packets ({} dropped)".format(_capture_result_cap, _capture_result_drop))

        print("Processing results...")

        # Write test metadata to disk
        module_logger.info("Writing test metadata to csv")
        with open(self._output_csv_test, 'w', newline='') as test_csv:
            fieldnames = ['name', 'path', 'iface', 'duration', 'start', 'end', 'degrees', 'bearing']
            test_csv_writer = csv.DictWriter(test_csv, dialect="unix", fieldnames=fieldnames)
            test_csv_writer.writeheader()
            test_csv_writer.writerow({fieldnames[0]: self._test,
                                      fieldnames[1]: self._capture_path,
                                      fieldnames[2]: self._iface,
                                      fieldnames[3]: self._duration,
                                      fieldnames[4]: loop_start_time,
                                      fieldnames[5]: loop_stop_time,
                                      fieldnames[6]: self._degrees,
                                      fieldnames[7]: self._bearing})

        _beacon_count = 0
        _beacon_failures = 0

        module_logger.info("Processing capture results")
        # Build CSV of beacons from pcap and antenna_results
        with open(self._output_csv_res, 'w', newline='') as results_csv:

            # Read pcapng into memory
            print("Initializing tshark, loading packets into memory...")
            packets = pyshark.FileCapture(self._capture_file_pcap, display_filter='wlan[0] == 0x80')
            packets.load_packets()
            fieldnames = ['timestamp', 'bssid', 'ssi', 'channel', 'bearing',
                          'lat', 'lon', 'alt', 'lat_err', 'lon_error', 'alt_error']
            results_csv_writer = csv.DictWriter(results_csv, dialect="unix", fieldnames=fieldnames)
            results_csv_writer.writeheader()

            for packet in tqdm(packets, desc="{:<35}".format("Processing packets")):

                try:
                    # Get time, bssid & db from packet
                    ptime = packet.sniff_time.timestamp()
                    pbssid = packet.wlan.bssid
                    pssi = int(packet.radiotap.dbm_antsignal)
                    pchannel = int(packet.radiotap.channel_freq)
                except AttributeError:
                    _beacon_failures += 1
                    continue

                # Antenna correlation
                # Compute the timespan for the rotation, and use the relative packet time to determine
                # where in the rotation the packet was captured
                # This is necessary to have a smooth antenna rotation with microstepping
                total_time = loop_stop_time - loop_start_time
                pdiff = ptime - loop_start_time
                if pdiff <= 0:
                    pdiff = 0

                pprogress = pdiff / total_time
                pbearing = pprogress * self._degrees + self._bearing

                # GPS correlation
                plat = None
                plon = None
                palt = None
                plat_err = None
                plon_err = None
                palt_err = None
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

                results_csv_writer.writerow({
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

                _beacon_count += 1

        module_logger.info("Processed {} beacons".format(_beacon_count))
        module_logger.info("Failed to process {} beacons".format(_beacon_failures))
        print("Processed {} beacons, exported to csv file ({})".format(_beacon_count, self._output_csv_res))

        # Show progress bar of joining threads
        with tqdm(total=4, desc="{:<35}".format("Waiting for threads")) as pbar:

            # Channel Hopper Thread
            pbar.update()
            pbar.refresh()
            self._channel_hopper_thread.join()

            pbar.update()
            pbar.refresh()
            self._antenna_thread.join()

            pbar.update()
            pbar.refresh()
            self._gps_thread.join()

            pbar.update()
            pbar.refresh()
            self._capture_thread.join()


class CaptureThread(threading.Thread):

    def __init__(self, response_queue, initialize_flag, start_flag, iface, duration, output):

        super().__init__()

        module_logger.info("Starting Packet Capture Thread")

        self.daemon = True
        self._response_queue = response_queue
        self._initialize_flag = initialize_flag
        self._start_flag = start_flag
        self._iface = iface
        self._duration = duration
        self._output = output

        # Check for required system packages
        self._packet_cap_util = "dumpcap"
        self._pcap_params = ['-i', self._iface, '-B', '12', '-q']

        if shutil.which(self._packet_cap_util) is None:
            module_logger.error("Required packet capture system tool '{}' is not installed"
                                .format(self._packet_cap_util))
            exit(1)

        # Ensure we are in monitor mode
        from localizer import wifi
        if wifi.get_interface_mode(self._iface) != "monitor":
            wifi.set_interface_mode(self._iface, "monitor")
        assert(wifi.get_interface_mode(self._iface) == "monitor")

    def run(self):
        module_logger.info("Executing capture thread")

        command = [self._packet_cap_util] + self._pcap_params + ["-a", "duration:{}".format(self._duration + 1), "-w", self._output]

        # Wait for synchronization signal
        self._initialize_flag.wait()

        _start_time = time.time()
        proc = Popen(command, stdout=PIPE, stderr=PIPE)

        # Wait for process to output "File: ..." to stderr and then set flag for other threads
        _timeout_start = time.time()
        curr_line = ""
        while not curr_line.startswith("File:"):
            curr_line = proc.stderr.readline().decode()
            if time.time() > _timeout_start + 5:
                raise TimeoutError("Capture process did not start as expected: {}/{}".format(curr_line, command))
            else:
                time.sleep(.1)
        self._start_flag.set()

        proc.wait()
        _end_time = time.time()
        module_logger.info("Captured packets for {:.2f}s (expected {}s)".format(_end_time-_start_time, self._duration))

        import re
        matches = re.search("(?<=dropped on interface\s')(?:\S+':\s)(\d+)/(\d+)", proc.stderr.read().decode())
        if matches is not None and len(matches.groups()) == 2:
            num_cap = int(matches.groups()[0])
            num_drop = int(matches.groups()[1])
        else:
            raise ValueError("Capture failed")

        # Respond with actual
        self._response_queue.put((num_cap, num_drop))
