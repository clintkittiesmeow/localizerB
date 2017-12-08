import csv
import logging
import os
import time
from datetime import date
from multiprocessing import Pool

import pyshark
from geomag import WorldMagneticModel
from tqdm import tqdm

from localizer import capture

module_logger = logging.getLogger(__name__)
_macs = []


def process_capture(meta_tuple):

    global _macs

    # Unpack tuple - required for tqdm imap
    path, meta_file = meta_tuple

    with open(os.path.join(path, meta_file), 'rt') as meta_csv:
        _meta_reader = csv.DictReader(meta_csv, dialect='unix')
        meta = next(_meta_reader)

    _beacon_count = 0
    _beacon_failures = 0

    # Correct bearing to compensate for magnetic declination
    _declination = WorldMagneticModel()\
        .calc_mag_field(float(meta[capture.meta_csv_fieldnames[6]]),
                        float(meta[capture.meta_csv_fieldnames[7]]),
                        date=date.fromtimestamp(float(meta["start"])))\
        .declination

    _results_path = os.path.join(path, time.strftime('%Y%m%d-%H-%M-%S') + "-results" + ".csv")

    module_logger.info("Processing capture (meta: {})".format(str(meta)))

    # Build CSV of beacons from pcap and antenna_results
    try:
        with open(_results_path, 'w', newline='') as results_csv:

            # Read pcapng
            _pcap = os.path.join(path, meta[capture.meta_csv_fieldnames[16]])
            packets = pyshark.FileCapture(_pcap, display_filter='wlan[0] == 0x80')
            fieldnames = ['test',
                          'pass',
                          'duration',
                          'hop-rate',
                          'timestamp',
                          'bssid',
                          'ssi',
                          'channel',
                          'bearing',
                          'lat',
                          'lon',
                          'alt',
                          'lat_err',
                          'lon_error',
                          'alt_error']
            results_csv_writer = csv.DictWriter(results_csv, dialect="unix", fieldnames=fieldnames)
            results_csv_writer.writeheader()

            module_logger.info("Processing packets")
            for packet in packets:

                try:
                    # Get time, bssid & db from packet
                    pbssid = packet.wlan.bssid
                    if _macs and pbssid not in _macs:
                        continue
                    ptime = packet.sniff_time.timestamp()
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
                pbearing = (pprogress * float(meta["degrees"]) + float(meta["bearing"]) + _declination) % 360

                results_csv_writer.writerow({
                    fieldnames[0]: meta[capture.meta_csv_fieldnames[0]],
                    fieldnames[1]: meta[capture.meta_csv_fieldnames[1]],
                    fieldnames[2]: meta[capture.meta_csv_fieldnames[4]],
                    fieldnames[3]: meta[capture.meta_csv_fieldnames[5]],
                    fieldnames[4]: ptime,
                    fieldnames[5]: pbssid,
                    fieldnames[6]: pssi,
                    fieldnames[7]: pchannel,
                    fieldnames[8]: pbearing,
                    fieldnames[9]: meta[capture.meta_csv_fieldnames[6]],
                    fieldnames[10]: meta[capture.meta_csv_fieldnames[7]],
                    fieldnames[11]: meta[capture.meta_csv_fieldnames[8]],
                    fieldnames[12]: meta[capture.meta_csv_fieldnames[9]],
                    fieldnames[13]: meta[capture.meta_csv_fieldnames[10]],
                    fieldnames[14]: meta[capture.meta_csv_fieldnames[11]]
                })

                _beacon_count += 1

        module_logger.info("Completed processing {} beacons to {}".format(_beacon_count, _results_path))
        module_logger.info("Failed to process {} beacons".format(_beacon_failures))
        return _beacon_count, _results_path

    except ValueError as e:
        module_logger.error(e)
        # Delete csv
        os.remove(_results_path)
        return _beacon_count, None


def _check_capture_dir(files):
    """
    Check whether the list of files has the required files in it to be considered a capture directory

    :param files: Files to check
    :type files: list
    :return: True if the files indicate a capture path, false otherwise
    :rtype: bool
    """

    for suffix in capture.capture_suffixes.values():
        if not any(file.endswith(suffix) for file in files):
            return False

    return True


def _check_capture_processed(files):
    """
    Check whether the list of files has already been processed

    :param files: Files to check
    :type files: list
    :return: True if the files indicate a capture has been processed already, false otherwise
    :rtype: bool
    """

    if any(file.endswith(capture.results_suffix) for file in files):
        return True

    return False


def _get_capture_meta(files):
    """
    Get the capture meta file path from list of files

    :param files: Files to check
    :type files: list
    :return: Filename of meta file
    :rtype: str
    """

    for file in files:
        if file.endswith(capture.capture_suffixes["meta"]):
            return file

    return None


def process_directory(macs=None):
    """
    Process entire directory - will search subdirectories for required files and process them if not already processed

    :param macs: list of mac addresses to filter on
    :type macs: str
    :return: The number of directories processed
    :rtype: int
    """

    # Read in macs
    if macs:
        global _macs
        with open(macs, 'r', newline='') as mac_tsv:
            csv_reader = csv.DictReader(mac_tsv, dialect="unix", delimiter='\t')
            for line in csv_reader:
                _macs.append(line["BSSID"])

    _tasks = []

    # Walk through each subdirectory of working directory
    module_logger.info("Building list of directories to process")
    for root, dirs, files in os.walk(os.getcwd()):
        if not _check_capture_dir(files):
            continue
        elif _check_capture_processed(files):
            continue
        else:
            # Add meta file to list
            _file = _get_capture_meta(files)
            assert _file is not None
            _tasks.append((root, _file))

    print("Found {} unprocessed data sets".format(len(_tasks)))

    if _tasks:
        with Pool(processes=4) as pool:
            _results = 0
            for result in tqdm(pool.imap_unordered(process_capture, _tasks), total=len(_tasks)):
                _results += result[0]

            print("Processed {} packets in {} directories".format(_results, len(_tasks)))
