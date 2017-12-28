import csv
import logging
import os
import queue
import shutil
import threading
import time
from subprocess import PIPE, Popen

import gpsd
from tqdm import tqdm, trange

from localizer import antenna, wifi, gps, process

OPTIMAL_CAPTURE_DURATION = 20

module_logger = logging.getLogger(__name__)

capture_suffixes = {"nmea": ".nmea",
                    "pcap": ".pcapng",
                    "meta": "-test.csv",
                    "coords": "-gps.csv"}
results_suffix = "-results.csv"
TEST_SUFFIX = "-test.conf"

meta_csv_fieldnames = ['name',
                       'pass',
                       'path',
                       'iface',
                       'duration',
                       'hop_int',
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


def capture(params, pass_num=None, reset=None, fine=None):
    # Set up working folder
    os.umask(0)
    _capture_path = params.test

    if pass_num is not None:
        _capture_path = os.path.join(_capture_path, pass_num)

    if fine is not None:
        _capture_path = os.path.join(_capture_path, fine)

    try:
        os.makedirs(_capture_path, exist_ok=True)
    except OSError as e:
        module_logger.error("Could not create the working directory {} ({})"
                            .format(_capture_path, e))
        exit(1)

    # Make sure we can write to the folder
    if not os.access(_capture_path, os.W_OK | os.X_OK):
        module_logger.error("Could not write to the working directory {}".format(_capture_path))
        raise OSError()

    # Create capture file names
    _capture_file_pcap = time.strftime('%Y%m%d-%H-%M-%S') + capture_suffixes["pcap"]
    _capture_file_gps = time.strftime('%Y%m%d-%H-%M-%S') + capture_suffixes["nmea"]
    _output_csv_gps = time.strftime('%Y%m%d-%H-%M-%S') + capture_suffixes["coords"]
    _output_csv_test = time.strftime('%Y%m%d-%H-%M-%S') + capture_suffixes["meta"]

    # Threading sync flag
    _initialize_flag = threading.Event()
    _capture_ready = threading.Event()

    module_logger.info("Setting up capture threads")

    # Show progress bar of creating threads
    with tqdm(total=4, desc="{:<35}".format("Setting up threads")) as pbar:

        # Set up antenna control thread
        _antenna_response_queue = queue.Queue()
        _antenna_thread = antenna.AntennaStepperThread(_antenna_response_queue,
                                                       _capture_ready,
                                                       params.duration,
                                                       params.degrees,
                                                       params.bearing_magnetic,
                                                       reset)
        _antenna_thread.start()
        # Wait for antenna to be ready
        _antenna_response_queue.get()
        pbar.update()
        pbar.refresh()

        # Set up gps thread
        _gps_response_queue = queue.Queue()
        _gps_thread = gps.GPSThread(_gps_response_queue,
                                    _capture_ready,
                                    params.duration,
                                    os.path.join(_capture_path, _capture_file_gps),
                                    os.path.join(_capture_path, _output_csv_gps))
        _gps_thread.start()
        pbar.update()
        pbar.refresh()

        # Set up pcap thread
        _capture_response_queue = queue.Queue()
        _capture_thread = CaptureThread(_capture_response_queue,
                                        _initialize_flag,
                                        _capture_ready,
                                        params.iface,
                                        params.duration,
                                        os.path.join(_capture_path, _capture_file_pcap))
        _capture_thread.start()
        pbar.update()
        pbar.refresh()

        # Set up WiFi channel scanner thread
        _channel_hopper_thread = wifi.ChannelHopper(_capture_ready,
                                                    params.iface,
                                                    params.duration,
                                                    params.hop_int,
                                                    distance = params.hop_dist,
                                                    init_chan = params.channel)
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
        # Spawn

    print("Writing metadata...")

    # Write test metadata to disk
    module_logger.info("Writing test metadata to csv")
    with open(os.path.join(_capture_path, _output_csv_test), 'w', newline='') as test_csv:
        _test_csv_writer = csv.DictWriter(test_csv, dialect="unix", fieldnames=meta_csv_fieldnames)
        _test_csv_writer.writeheader()
        _test_csv_data = {meta_csv_fieldnames[0]: params.test,
                          meta_csv_fieldnames[1]: pass_num,
                          meta_csv_fieldnames[2]: _capture_path,
                          meta_csv_fieldnames[3]: params.iface,
                          meta_csv_fieldnames[4]: params.duration,
                          meta_csv_fieldnames[5]: params.hop_int,
                          meta_csv_fieldnames[6]: _avg_lat,
                          meta_csv_fieldnames[7]: _avg_lon,
                          meta_csv_fieldnames[8]: _avg_alt,
                          meta_csv_fieldnames[9]: _avg_lat_err,
                          meta_csv_fieldnames[10]: _avg_lon_err,
                          meta_csv_fieldnames[11]: _avg_alt_err,
                          meta_csv_fieldnames[12]: loop_start_time,
                          meta_csv_fieldnames[13]: loop_stop_time,
                          meta_csv_fieldnames[14]: params.degrees,
                          meta_csv_fieldnames[15]: params.bearing_magnetic,
                          meta_csv_fieldnames[16]: _capture_file_pcap,
                          meta_csv_fieldnames[17]: _capture_file_gps,
                          meta_csv_fieldnames[18]: _output_csv_gps}
        _test_csv_writer.writerow(_test_csv_data)

    # Perform processing while we wait for threads to finish:
    _guesses = None
    if params.fine:
        module_logger.info("Processing capture")
        _meta_path = os.path.join(_capture_path, _output_csv_test)
        _, _, _, _guesses = process.process_capture(_meta_path, write_to_disk=True, guess=True, clockwise=True, macs=params.macs)

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


    # Perform fine-level captures
    if params.fine and _guesses:
        module_logger.info("Performing fine captures on {} access points".format(len(_guesses)))
        _width = params.fine[0]
        _duration = params.fine[1]

        _params = []

        for row in _guesses.iterrows():
            _bearing_guess = row.bearing
            _fine = row.ssid + "_" + row.bssid.replace(':', '').replace('-', '')

            _new_bearing = _bearing_guess - _width/2
            _new_degrees = _width

            _param = params.copy()
            _param.bearing_magnetic = _new_bearing
            _param.degrees = _new_degrees
            _param.duration = _duration
            _param.fine = None
            _params.append((_param, _fine))

        # Try to set the next bearing to speed up capture
        for i, val in enumerate(_params):
            _p, _f = val

            try:
                _reset = _params[i + 1][0].bearing_magnetic
            except IndexError:
                _reset = None

            # Recursively run capture
            capture(_p, pass_num, _reset, _f)

    return _capture_path, _output_csv_test


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
