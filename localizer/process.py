import csv
import logging
import os
import time
from datetime import date
from multiprocessing import Pool

import pandas as pd
import pyshark
from geomag import WorldMagneticModel
from tqdm import tqdm

from localizer import capture, locate

module_logger = logging.getLogger(__name__)


def process_capture(meta_file, write_to_disk=False, guess=False, clockwise=True, macs=None):
    """
    Process a captured data set
    :param meta_file:       path to meta file containing test results
    :param write_to_disk:   bool designating whether to write to disk
    :param clockwise:       direction antenna was moving during the capture,
    :param macs:            list of macs to filter on
    :param columns:         A list of the column names to filter
    :return: (_beacon_count, _results_path):
    """
    from dateutil import parser

    _path = os.path.split(meta_file)[0]

    with open(meta_file, 'rt') as meta_csv:
        _meta_reader = csv.DictReader(meta_csv, dialect='unix')
        meta = next(_meta_reader)

    module_logger.info("Processing capture (meta: {})".format(str(meta)))

    _beacon_count = 0
    _beacon_failures = 0

    # Correct bearing to compensate for magnetic declination
    _declination = WorldMagneticModel()\
        .calc_mag_field(float(meta[capture.meta_csv_fieldnames[6]]),
                        float(meta[capture.meta_csv_fieldnames[7]]),
                        date=date.fromtimestamp(float(meta["start"])))\
        .declination

    # Read results into a DataFrame
    # Build columns
    _default_columns = ['test',
                        'pass',
                        'duration',
                        'hop-rate',
                        'timestamp',
                        'bssid',
                        'ssid',
                        'security',
                        'encryption',
                        'ssi',
                        'channel',
                        'bearing_magnetic',
                        'bearing_true',
                        'lat',
                        'lon',
                        'alt',
                        'lat_err',
                        'lon_error',
                        'alt_error']

    _rows = []
    _pcap = os.path.join(_path, meta[capture.meta_csv_fieldnames[16]])

    # Build filter string
    _filter = 'wlan[0] == 0x80'
    if macs:
        _mac_string = ' and ('
        _mac_strings = ['wlan.bssid == ' + mac for mac in macs]
        _mac_string += ' or '.join(_mac_strings)
        _mac_string += ')'
        _filter += _mac_string

    packets = pyshark.FileCapture(_pcap, display_filter=_filter, keep_packets=False, use_json=True)

    for packet in packets:

        try:
            # Get time, bssid & db from packet
            pbssid = packet.wlan.bssid
            ptime = parser.parse(packet.sniff_timestamp).timestamp()
            pssid = next((tag.ssid for tag in packet.wlan_mgt.tagged.all.tag if hasattr(tag, 'ssid')), None)
            pssi = int(packet.wlan_radio.signal_dbm) if hasattr(packet.wlan_radio, 'signal_dbm') else int(packet.radiotap.dbm_antsignal)
            pchannel = int(packet.wlan_radio.channel) if hasattr(packet.wlan_radio, 'channel') else int(packet.radiotap.channel.freq)

            # Determine AP security, if any
            # WPA
            try:
                psecurity = next(("WPA" for tag in packet.wlan_mgt.tagged.all.tag if hasattr(tag, 'wfa.ie.wpa.version')), None)
                # WEP
                if not psecurity:
                    psecurity = "WEP" if packet.wlan_mgt.fixed.all.capabilities_tree.has_field("privacy") else None
                pencryption = None
            except TypeError as e:
                print("{}: {}".format(e, str(packet)))

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

        cw = 1 if clockwise else -1

        pprogress = pdiff / total_time
        pbearing_magnetic = (cw * pprogress * float(meta["degrees"]) + float(meta["bearing"])) % 360
        pbearing_true = (pbearing_magnetic + _declination) % 360

        _rows.append([
            meta[capture.meta_csv_fieldnames[0]],
            meta[capture.meta_csv_fieldnames[1]],
            meta[capture.meta_csv_fieldnames[4]],
            meta[capture.meta_csv_fieldnames[5]],
            ptime,
            str(pbssid),
            str(pssid),
            psecurity,
            pencryption,
            pssi,
            pchannel,
            pbearing_magnetic,
            pbearing_true,
            meta[capture.meta_csv_fieldnames[6]],
            meta[capture.meta_csv_fieldnames[7]],
            meta[capture.meta_csv_fieldnames[8]],
            meta[capture.meta_csv_fieldnames[9]],
            meta[capture.meta_csv_fieldnames[10]],
            meta[capture.meta_csv_fieldnames[11]],
        ])

        _beacon_count += 1

    # # Import the results into a DataFrame
    # if columns:
    #     _output_columns = list(set(columns) & set(_default_columns))
    #     _results_df = pd.DataFrame(_rows, columns=_default_columns).filter(items=_output_columns)
    # else:

    _results_df = pd.DataFrame(_rows, columns=_default_columns)
    # Add mw column
    _results_df.loc[:,'mw'] = dbm_to_mw(_results_df['ssi'])
    module_logger.info("Completed processing {} beacons ({} failures)".format(_beacon_count, _beacon_failures))

    # If a path is given, write the results to a file
    if write_to_disk:
        _results_path = os.path.join(_path, time.strftime('%Y%m%d-%H-%M-%S') + "-results" + ".csv")
        _results_df.to_csv(_results_path, sep=',', index=False)
        module_logger.info("Wrote results to {}".format(_results_path))
        write_to_disk = _results_path

    # If asked to guess, return list of bssids and a guess as to their bearing
    if guess:
        _columns = ['ssid', 'bssid', 'bearing', 'security', 'strength', 'method']
        _rows = []

        for names, group in _results_df.groupby(['ssid','bssid']):
            _security = pd.unique(group['security'])[0]
            _strength = group['ssi'].max()
            _guess, _method = locate.interpolate(group, meta[capture.meta_csv_fieldnames[14]])
            _rows.append([names[0], names[1], _guess, _security, _strength, _method])

        guess = pd.DataFrame(_rows, columns=_columns)

    return _beacon_count, _results_df, write_to_disk, guess


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


def process_directory(macs=None, clockwise=True):
    """
    Process entire directory - will search subdirectories for required files and process them if not already processed

    :param macs: list of mac addresses to filter on
    :type macs: list[str]
    :param clockwise: Direction of antenna travel
    :type clockwise: bool
    :return: The number of directories processed
    :rtype: int
    """

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
            _tasks.append((os.path.join(root,_file), True, False, clockwise, macs))

    print("Found {} unprocessed data sets".format(len(_tasks)))

    if _tasks:
        with Pool(processes=4) as pool:
            _results = 0
            for result in tqdm(pool.imap_unordered(process_capture_helper, _tasks), total=len(_tasks)):
                _results += result[0]

            print("Processed {} packets in {} directories".format(_results, len(_tasks)))


def process_capture_helper(tup):
    return process_capture(*tup)


def dbm_to_mw(dbm):
    return 10**(dbm/10)