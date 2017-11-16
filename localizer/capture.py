import csv
import logging
import os
import queue
import shutil
import sys
import threading
import time
from subprocess import PIPE, Popen

import gpsd
import pyshark
from tqdm import tqdm, trange

from localizer import antenna, wifi, gps

module_logger = logging.getLogger('localizer.capture')

_capture_suffixes = {"nmea": ".nmea",
                     "pcap": ".pcapng",
                     "meta": "-test.csv",
                     "coords": "-gps.csv"}
_processed_suffix = "-results.csv"

_meta_csv_fieldnames = ['name',
                        'path',
                        'iface',
                        'duration',
                        'pos_lat',
                        'pos_lon',
                        'pos_alt',
                        'pos_lat_err',
                        'pos_lon_err',
                        'pos_alt_err',
                        'start',
                        'end',
                        'degrees',
                        'bearing',
                        'pcap',
                        'nmea',
                        'coords']


def capture(params, sub=None):
    # Global paths
    _capture_path = os.getcwd()

    # Set up working folder
    os.umask(0)
    _capture_path = os.path.join(_capture_path, params.test)

    if sub is not None:
        _capture_path = os.path.join(_capture_path, sub)

    try:
        os.makedirs(_capture_path, exist_ok=True)
    except OSError as e:
        module_logger.error("Could not create the working directory {} ({})"
                            .format(_capture_path, e))
        exit(1)

    # Make sure we can write to the folder
    if not os.access(_capture_path, os.W_OK | os.X_OK):
        module_logger.error("Could not write to the working directory {}".format(_capture_path))
        exit(1)

    # Create capture file names
    _capture_file_pcap = os.path.join(_capture_path, time.strftime('%Y%m%d-%H-%M-%S') + _capture_suffixes["pcap"])
    _capture_file_gps = os.path.join(_capture_path, time.strftime('%Y%m%d-%H-%M-%S') + _capture_suffixes["nmea"])
    _output_csv_gps = os.path.join(_capture_path, time.strftime('%Y%m%d-%H-%M-%S') + _capture_suffixes["coords"])
    _output_csv_test = os.path.join(_capture_path, time.strftime('%Y%m%d-%H-%M-%S') + _capture_suffixes["meta"])

    # Threading sync flag
    _initialize_flag = threading.Event()
    _start_flag = threading.Event()

    module_logger.info("Setting up capture threads")

    # Show progress bar of creating threads
    with tqdm(total=4, desc="{:<35}".format("Setting up threads")) as pbar:

        # Set up gps thread
        _gps_response_queue = queue.Queue()
        _gps_thread = gps.GPSThread(_gps_response_queue,
                                    _start_flag,
                                    params.duration,
                                    _capture_file_gps,
                                    _output_csv_gps)
        _gps_thread.start()
        pbar.update()
        pbar.refresh()

        # Set up antenna control thread
        _antenna_response_queue = queue.Queue()
        _antenna_thread = antenna.AntennaStepperThread(_antenna_response_queue,
                                                       _start_flag,
                                                       params.duration,
                                                       params.degrees,
                                                       params.bearing,
                                                       True)
        _antenna_thread.start()
        pbar.update()
        pbar.refresh()

        # Set up pcap thread
        _capture_response_queue = queue.Queue()
        _capture_thread = CaptureThread(_capture_response_queue,
                                        _initialize_flag,
                                        _start_flag,
                                        params.iface,
                                        params.duration,
                                        _capture_file_pcap)
        _capture_thread.start()
        pbar.update()
        pbar.refresh()

        # Set up WiFi channel scanner thread
        _channel_hopper_thread = wifi.ChannelHopper(_start_flag,
                                                    params.iface,
                                                    params.duration,
                                                    params.hop_int)
        _channel_hopper_thread.start()
        pbar.update()
        pbar.refresh()

    # Ensure that gps has a 3D fix
    module_logger.info("Waiting for GPS 3D fix")
    try:
        _time_waited = 0
        while gpsd.get_current().mode != 3:
            print("Waiting for {}s for 3D gps fix (current mode = '{}' - press 'CTRL-c to cancel)\r"
                  .format(_time_waited, gpsd.get_current().mode))
            time.sleep(1)
            _time_waited += 1
    except KeyboardInterrupt:
        print('\nCapture canceled.')
        return False
    else:
        print('\n')

    module_logger.info("Triggering synchronized threads")
    # Start threads
    _initialize_flag.set()

    # Print out timer to console
    for _ in trange(params.duration + 1, desc="{:<35}"
                    .format("Capturing packets for {}s".format((str(params.duration))))):
        time.sleep(1)

    # Show progress bar of getting thread results
    with tqdm(total=3, desc="{:<35}".format("Waiting for results")) as pbar:

        pbar.update()
        pbar.refresh()
        loop_start_time, loop_stop_time, loop_expected_time, loop_average_time = _antenna_response_queue.get()

        pbar.update()
        pbar.refresh()
        _avg_lat, _avg_lon, _avg_alt, _avg_lat_err, _avg_lon_err, _avg_alt_err = _gps_response_queue.get()

        pbar.update()
        pbar.refresh()
        _capture_result_cap, _capture_result_drop = _capture_response_queue.get()
        module_logger.info("Captured {} packets ({} dropped)".format(_capture_result_cap, _capture_result_drop))

    print("Writing metadata...")

    # Write test metadata to disk
    module_logger.info("Writing test metadata to csv")
    with open(_output_csv_test, 'w', newline='') as test_csv:
        _test_csv_writer = csv.DictWriter(test_csv, dialect="unix", fieldnames=_meta_csv_fieldnames)
        _test_csv_writer.writeheader()
        _test_csv_data = {_meta_csv_fieldnames[0]: params.test,
                          _meta_csv_fieldnames[1]: _capture_path,
                          _meta_csv_fieldnames[2]: params.iface,
                          _meta_csv_fieldnames[3]: params.duration,
                          _meta_csv_fieldnames[4]: _avg_lat,
                          _meta_csv_fieldnames[5]: _avg_lon,
                          _meta_csv_fieldnames[6]: _avg_alt,
                          _meta_csv_fieldnames[7]: _avg_lat_err,
                          _meta_csv_fieldnames[8]: _avg_lon_err,
                          _meta_csv_fieldnames[9]: _avg_alt_err,
                          _meta_csv_fieldnames[10]: loop_start_time,
                          _meta_csv_fieldnames[11]: loop_stop_time,
                          _meta_csv_fieldnames[12]: params.degrees,
                          _meta_csv_fieldnames[13]: params.bearing,
                          _meta_csv_fieldnames[14]: _capture_file_pcap,
                          _meta_csv_fieldnames[15]: _capture_file_gps,
                          _meta_csv_fieldnames[16]: _output_csv_gps}
        _test_csv_writer.writerow(_test_csv_data)

    # Show progress bar of joining threads
    with tqdm(total=4, desc="{:<35}".format("Waiting for threads")) as pbar:

        # Channel Hopper Thread
        pbar.update()
        pbar.refresh()
        _channel_hopper_thread.join()

        pbar.update()
        pbar.refresh()
        _antenna_thread.join()

        pbar.update()
        pbar.refresh()
        _gps_thread.join()

        pbar.update()
        pbar.refresh()
        _capture_thread.join()

    return _capture_path, _test_csv_data


def process_capture(path, meta):

    _beacon_count = 0
    _beacon_failures = 0

    _path = os.path.join(path, time.strftime('%Y%m%d-%H-%M-%S') + "-results" + ".csv")

    print("Processing capture in {}".format(path))
    module_logger.info("Processing capture in {} (meta: {})".format(path, str(meta)))

    # Build CSV of beacons from pcap and antenna_results
    try:
        with open(_path, 'w', newline='') as results_csv:

            # Read pcapng into memory
            print("Initializing tshark, loading packets into memory...")
            packets = pyshark.FileCapture(meta["pcap"], display_filter='wlan[0] == 0x80')
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
                total_time = float(meta["end"]) - float(meta["start"])
                pdiff = ptime - float(meta["start"])
                if pdiff <= 0:
                    pdiff = 0

                pprogress = pdiff / total_time
                pbearing = pprogress * float(meta["degrees"]) + float(meta["bearing"])

                results_csv_writer.writerow({
                    fieldnames[0]: ptime,
                    fieldnames[1]: pbssid,
                    fieldnames[2]: pssi,
                    fieldnames[3]: pchannel,
                    fieldnames[4]: pbearing,
                    fieldnames[5]: meta["pos_lat"],
                    fieldnames[6]: meta["pos_lon"],
                    fieldnames[7]: meta["pos_alt"],
                    fieldnames[8]: meta["pos_lat_err"],
                    fieldnames[9]: meta["pos_lon_err"],
                    fieldnames[10]: meta["pos_alt_err"], })

                _beacon_count += 1

        module_logger.info("Completed processing {} beacons to {}".format(_beacon_count, _path))
        module_logger.info("Failed to process {} beacons".format(_beacon_failures))
        print("Completed processing {} beacons, exported to csv file ({})".format(_beacon_count, _path))

    except ValueError as e:
        module_logger.error(e)
        # Delete csv
        os.remove(_path)


def process_directory(limit=sys.maxsize):
    """
    Process entire directory - will search subdirectories for required files and process them if not already processed

    :param limit: limit on the number of directories to process
    :type limit: int
    :return: The number of directories processed
    :rtype: int
    """

    _num_dirs = 0

    # Walk through each subdirectory of working directory
    for root, dirs, files in os.walk(os.getcwd()):
        for d in dirs:

            _dir_path = os.path.join(os.getcwd(), d)

            # Ensure we haven't hit our limit
            if limit <= 0:
                break

            if not _check_capture_dir(d):
                continue
            elif _check_capture_processed(d):
                continue
            else:
                # Read in test meta csv
                _file = _get_capture_meta(d)
                assert _file is not None
                _file_path = os.path.join(_dir_path, _file)

                with open(_file_path, 'rt') as meta_file:
                    _meta_reader = csv.DictReader(meta_file, dialect='unix')
                    _meta_dict = next(_meta_reader)

                    process_capture(_dir_path, _meta_dict)
                    _num_dirs += 1
                    limit -= 1

        break

    return _num_dirs


def _check_capture_dir(path):
    """
    Check whether the path has the required files in it to be considered a capture directory

    :param path: Path to check (no recursion)
    :type path: str
    :return: True if the path is valid, false otherwise
    :rtype: bool
    """

    files = os.listdir(path)
    for suffix in _capture_suffixes.values():
        if not any(file.endswith(suffix) for file in files):
            return False

    return True


def _check_capture_processed(path):
    """
    Check whether the path has already been processed

    :param path: Path to check (no recursion)
    :type path: str
    :return: True if the capture has been processed already, false otherwise
    :rtype: bool
    """

    files = os.listdir(path)
    if any(file.endswith(_processed_suffix) for file in files):
        return True

    return False


def _get_capture_meta(path):
    """
    Get the capture meta file path from directory

    :param path: Path to check (no recursion)
    :type path: str
    :return: Filename of meta file
    :rtype: str
    """

    for file in os.listdir(path):
        if file.endswith(_capture_suffixes["meta"]):
            return file

    return None


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
        self._pcap_util = "dumpcap"
        self._pcap_params = ['-i', self._iface, '-B', '12', '-q']

        if shutil.which(self._pcap_util) is None:
            module_logger.error("Required packet capture system tool '{}' is not installed"
                                .format(self._pcap_util))
            exit(1)

        # Ensure we are in monitor mode
        from localizer import wifi

        while wifi.get_interface_mode(self._iface) != "monitor":
            wifi.set_interface_mode(self._iface, "monitor")

    def run(self):
        module_logger.info("Executing capture thread")

        _dur = self._duration + 1
        command = [self._pcap_util] + self._pcap_params + ["-a", "duration:{}".format(_dur), "-w", self._output]

        # Wait for synchronization signal
        self._initialize_flag.wait()

        _start_time = time.time()
        proc = Popen(command, stdout=PIPE, stderr=PIPE)

        # Wait for process to output "File: ..." to stderr and then set flag for other threads
        try:
            _delay_notified = False
            _timeout_start = time.time()
            curr_line = ""
            while not curr_line.startswith("File:"):
                if time.time() > _timeout_start + 5 and not _delay_notified:
                    module_logger.error(
                        "Waiting over 5s for {} to start... Press Ctrl-C to cancel".format(self._pcap_util))
                    _delay_notified = True
                curr_line = proc.stderr.readline().decode()
                time.sleep(.1)
        except KeyboardInterrupt:
            print('\nCapture canceled.')
            return False

        # Tell other threads to start
        self._start_flag.set()

        # Wait for the dumpcap process to finish
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
        self._response_queue.put((_start_time, _end_time))
