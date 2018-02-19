import csv
import logging
import os
import queue
import shutil
import threading
import time
from subprocess import PIPE, Popen

import gpsd
from tabulate import tabulate
from tqdm import tqdm, trange

import localizer
from localizer import antenna, gps, process, interface
from localizer.meta import meta_csv_fieldnames, capture_suffixes

OPTIMAL_CAPTURE_DURATION = 20
OPTIMAL_CAPTURE_DURATION_FOCUSED = 6
OPTIMAL_CAPTURE_DEGREES_FOCUSED = 84

module_logger = logging.getLogger(__name__)


def capture(params, pass_num=None, reset=None, focused=None):
    _start_time = time.time()

    # Create capture file names
    _capture_prefix = time.strftime('%Y%m%d-%H-%M-%S')
    _capture_file_pcap = _capture_prefix + capture_suffixes["pcap"]
    _capture_file_gps = _capture_prefix + capture_suffixes["nmea"]
    _output_csv_gps = _capture_prefix + capture_suffixes["coords"]
    _output_csv_capture = _capture_prefix + capture_suffixes["meta"]
    _output_csv_guess = _capture_prefix + capture_suffixes["guess"] if params.focused else None

    # Build capture path and validate directory
    # Set up working folder
    os.umask(0)
    _capture_path = params.capture

    if pass_num is not None:
        _capture_path = os.path.join(_capture_path, pass_num)

    if focused is not None:
        _capture_path = os.path.join(_capture_path, focused.replace(':', '').replace('-', ''))

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

    # Threading sync flag
    _initialize_flag = threading.Event()
    _capture_ready = threading.Event()

    module_logger.info("Setting up capture threads")

    # Show progress bar of creating threads
    with tqdm(total=4, desc="{:<35}".format("Setting up threads")) as pbar:

        # Set up antenna control thread
        _antenna_response_queue = queue.Queue()
        _antenna_thread = antenna.AntennaThread(_antenna_response_queue,
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
        _channel_hopper_thread = interface.ChannelThread(_capture_ready,
                                                         params.iface,
                                                         params.duration,
                                                         params.hop_int,
                                                         distance=params.hop_dist,
                                                         init_chan=params.channel)
        _channel_hopper_thread.start()
        pbar.update()
        pbar.refresh()

    # Ensure that gps has a 3D fix
    if not localizer.debug:
        module_logger.info("Waiting for GPS 3D fix")
        _printed = False
        try:
            _time_waited = 0
            while gpsd.get_current().mode != 3:
                print("Waiting for {}s for 3D gps fix (current mode = '{}' - press 'CTRL-c to cancel)\r"
                      .format(_time_waited, gpsd.get_current().mode), end='')
                _printed = True
                time.sleep(1)
                _time_waited += 1
        except KeyboardInterrupt:
            print('\nCapture canceled.')
            return False
        finally:
            if _printed:
                print('\n')


    module_logger.info("Triggering synchronized threads")
    # Start threads
    _initialize_flag.set()

    if not _capture_ready.is_set():
        module_logger.info("Waiting for threads to start...")
        try:
            _delay_notified = False
            _timeout_start = time.time()
            while not _capture_ready.is_set():
                if time.time() > _timeout_start + 5 and not _delay_notified:
                    module_logger.error(
                        "Waiting over 5s for capture to start... Press Ctrl-C to cancel")
                    _delay_notified = True
                time.sleep(.1)
        except KeyboardInterrupt:
            print('\nCapture canceled.')
            return False

    # Print out timer to console
    for _ in trange(int(params.duration), desc="{:<35}"
                    .format("Capturing packets for {}s".format((str(params.duration))))):
        time.sleep(1)

    # Show progress bar of getting thread results
    with tqdm(total=3, desc="{:<35}".format("Waiting for results")) as pbar:

        pbar.update()
        pbar.refresh()
        loop_start_time, loop_stop_time = _antenna_response_queue.get()

        pbar.update()
        pbar.refresh()
        _avg_lat, _avg_lon, _avg_alt, _avg_lat_err, _avg_lon_err, _avg_alt_err = _gps_response_queue.get()

        pbar.update()
        pbar.refresh()
        _capture_result_cap, _capture_result_drop = _capture_response_queue.get()
        module_logger.info("Captured {} packets ({} dropped)".format(_capture_result_cap, _capture_result_drop))

    # Create Meta Dict
    _capture_csv_data = {meta_csv_fieldnames[0]: params.capture,
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
                         meta_csv_fieldnames[18]: _output_csv_gps,
                         meta_csv_fieldnames[19]: focused,
                         meta_csv_fieldnames[20]: _output_csv_guess,
     }

    # Perform processing while we wait for threads to finish:
    _guesses = None
    _guess_time_start = time.time()
    if params.focused:
        module_logger.info("Processing capture")
        _meta_path = os.path.join(_capture_path, _output_csv_capture)
        _, _, _, _guesses = process.process_capture(_capture_csv_data, _capture_path, write_to_disk=True, guess=True, clockwise=True, macs=params.macs)
        _guesses.to_csv(os.path.join(_capture_path, _output_csv_guess), sep=',')
    _guess_time_end = time.time()

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


    # Write capture metadata to disk
    module_logger.info("Writing capture metadata to csv")
    with open(os.path.join(_capture_path, _output_csv_capture), 'w', newline='') as capture_csv:
        _capture_csv_writer = csv.DictWriter(capture_csv, dialect="unix", fieldnames=meta_csv_fieldnames)
        _capture_csv_writer.writeheader()
        _capture_csv_data[meta_csv_fieldnames[21]] = time.time() - _start_time
        _capture_csv_data[meta_csv_fieldnames[22]] = len(_guesses) if _guesses is not None else None
        _capture_csv_data[meta_csv_fieldnames[23]] = _guess_time_end - _guess_time_start if _guesses is not None else None
        _capture_csv_writer.writerow(_capture_csv_data)

    # Perform focused-level captures
    if params.focused and _guesses is not None and len(_guesses):
        module_logger.info("Performing focused captures on {} access points:\n{}".format(len(_guesses), _guesses))
        _width = params.focused[0]
        _duration = params.focused[1]

        _params = []

        for i, row in _guesses.iterrows():
            _bearing_guess = row.bearing
            _focused = row.bssid

            _new_bearing = _bearing_guess - _width/2
            _new_degrees = _width

            _param = params.copy()
            _param.bearing_magnetic = _new_bearing
            _param.degrees = _new_degrees
            _param.duration = _duration
            _param.channel = row.channel
            _param.hop_int = 0
            _param.focused = None
            _params.append((_param, _focused))

        # Try to set the next bearing to speed up capture
        for i, val in enumerate(_params):
            _p, _f = val

            try:
                _reset = _params[i + 1][0].bearing_magnetic
            except IndexError:
                _reset = params.bearing_magnetic

            # Recursively run capture
            module_logger.debug("Focused Capture:\n\tCurrent bearing: {}\n\tCapture Bearing: {}\n\tReset Bearing: {}".format(antenna.bearing_current, _p.bearing_magnetic, _reset))
            capture(_p, pass_num, _reset, _f)

    return _capture_path, _output_csv_capture


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
        while interface.get_interface_mode(self._iface) != "monitor":
            interface.set_interface_mode(self._iface, "monitor")

    def run(self):
        module_logger.info("Executing capture thread")

        _dur = int(self._duration + 1)
        command = [self._pcap_util] + self._pcap_params + ["-a", "duration:{}".format(_dur), "-w", self._output]

        # Wait for synchronization signal
        self._initialize_flag.wait()

        _start_time = time.time()
        proc = Popen(command, stdout=PIPE, stderr=PIPE)

        # Wait for process to output "File: ..." to stderr and then set flag for other threads
        curr_line = ""
        while not curr_line.startswith("File:"):
            curr_line = proc.stderr.readline().decode()
            time.sleep(.1)

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


class APs():

    def __init__(self):
        self._aps = None

    @property
    def aps(self):
        return self._aps

    @aps.setter
    def aps(self, val):
        self._aps = val.reset_index(drop=True)

    def update(self, val):
        for i, row in val.iterrows():
            # If the new row exists in the dataframe, update the existing value
            if row.bssid in self._aps.bssid.unique():
                self._aps.iloc[self._aps.index[self._aps.bssid == row.bssid][0]] = row
            # If it's not in the current list, add it
            else:
                self._aps = self._aps.append(row)

        self._aps.reset_index(inplace=True, drop=True)

    def __getitem__(self, arg):
        return self._aps.iloc[arg]

    def __len__(self):
        if self._aps is None:
            return 0
        else:
            return len(self._aps)

    def __str__(self):
        return tabulate(self._aps, headers='keys', tablefmt='psql')
