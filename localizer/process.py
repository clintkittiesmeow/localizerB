import csv
import logging
import os
import time
from concurrent import futures
from datetime import date

import pandas as pd
import pyshark
from dateutil import parser
#CB from geomag import WorldMagneticModel
import geomag #CB


from tqdm import tqdm

from localizer import locate
from localizer.meta import meta_csv_fieldnames, capture_suffixes, required_suffixes

module_logger = logging.getLogger(__name__)


def process_capture(meta, path, write_to_disk=False, guess=False, clockwise=True, macs=None):
    """
    Process a captured data set
    :param meta:            meta dict containing capture results
    :param write_to_disk:   bool designating whether to write to disk
    :param guess:           bool designating whether to return a table of guessed bearings for detected BSSIDs
    :param clockwise:       direction antenna was moving during the capture,
    :param macs:            list of macs to filter on
    :return: (_beacon_count, _results_path):
    """

    module_logger.info("Processing capture (meta: {})".format(str(meta)))

    _beacon_count = 0
    _beacon_failures = 0

    # Correct bearing to compensate for magnetic declination
    #CB _declination = WorldMagneticModel()\
    #CB     .calc_mag_field(float(meta[meta_csv_fieldnames[6]]),
    #CB                     float(meta[meta_csv_fieldnames[7]]),
    #CB                     date=date.fromtimestamp(float(meta["start"])))\
    #CB     .declination
    lat = float(meta[meta_csv_fieldnames[6]]) # CB
    lon = float(meta[meta_csv_fieldnames[7]]) # CB
    start_date = date.fromtimestamp(float(meta["start"])) # CB
    alt = 0
    _declination = geomag.declination(lat, lon, alt, start_date)  # CB

    # Read results into a DataFrame
    # Build columns
    _default_columns = ['capture',
                        'pass',
                        'duration',
                        'hop-rate',
                        'timestamp',
                        'bssid',
                        'ssid',
                        'encryption',
                        'cipher',
                        'auth',
                        'ssi',
                        'channel',
                        'bearing_magnetic',
                        'bearing_true',
                        'lat',
                        'lon',
                        'alt',
                        'lat_err',
                        'lon_error',
                        'alt_error',
                        ]

    _rows = []
    _pcap = os.path.join(path, meta[meta_csv_fieldnames[16]])

    # Build filter string
    _filter = 'wlan[0] == 0x80'
    # Override any provide mac filter list if we have one in the capture metadata
    if meta_csv_fieldnames[19] in meta and meta[meta_csv_fieldnames[19]]:
        macs = [meta[meta_csv_fieldnames[19]]]
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
            pchannel = next((int(tag.current_channel) for tag in packet.wlan_mgt.tagged.all.tag if hasattr(tag, 'current_channel')), None)
            if not pchannel:
                pchannel = int(packet.wlan_radio.channel) if hasattr(packet.wlan_radio, 'channel') else int(packet.radiotap.channel.freq)

            # Determine AP security, if any https://ccie-or-null.net/2011/06/22/802-11-beacon-frames/
            pencryption = None
            pcipher = None
            pauth = None

            _cipher_tree = None
            _auth_tree = None

            # Parse Security Details
            # Check for MS WPA tag
            _ms_wpa = next((i for i, tag in enumerate(packet.wlan_mgt.tagged.all.tag) if hasattr(tag, 'wfa.ie.wpa.version')), None)
            if _ms_wpa is not None:
                pencryption = "WPA"

                if hasattr(packet.wlan_mgt.tagged.all.tag[_ms_wpa].wfa.ie.wpa, 'akms.list'):
                    _auth_tree = packet.wlan_mgt.tagged.all.tag[_ms_wpa].wfa.ie.wpa.akms.list.akms_tree

                if hasattr(packet.wlan_mgt.tagged.all.tag[_ms_wpa].wfa.ie.wpa, 'ucs.list'):
                    _cipher_tree = packet.wlan_mgt.tagged.all.tag[_ms_wpa].wfa.ie.wpa.ucs.list.ucs_tree

            # Check for RSN Tag
            _rsn = next((i for i, tag in enumerate(packet.wlan_mgt.tagged.all.tag) if hasattr(tag, 'rsn')), None)
            if _rsn is not None:
                pencryption = "WPA"

                if hasattr(packet.wlan_mgt.tagged.all.tag[_rsn].rsn, 'akms.list') and _auth_tree is None:
                    _auth_tree = packet.wlan_mgt.tagged.all.tag[_rsn].rsn.akms.list.akms_tree

                if hasattr(packet.wlan_mgt.tagged.all.tag[_rsn].rsn, 'pcs.list') and _cipher_tree is None:
                    _cipher_tree = packet.wlan_mgt.tagged.all.tag[_rsn].rsn.pcs.list.pcs_tree

            # Parse _auth_tree
            if _auth_tree:
                try:
                    _type = _auth_tree.type == '2'
                except AttributeError:
                    _type = next((_node.type for _node in _auth_tree if hasattr(_node, 'type') and (_node.type == '2' or _node.type == '3')), False)

                if _type == '3':
                    pauth = "FT"
                elif _type == '2':
                    pauth = "PSK"

            # Parse _cipher_tree
            if _cipher_tree:
                _types = []
                try:
                    _types.append(_cipher_tree.type)
                except AttributeError:
                    _types += [_node.type for _node in _cipher_tree if hasattr(_node, 'type')]

                if _types:
                    _types_str = []
                    for _type in _types:
                        if _type == '4':
                            _types_str.append("CCMP")
                        elif _type == '2':
                            _types_str.append("TKIP")
                    pcipher = "+".join(_types_str)

            if not pencryption:
                # WEP
                pencryption = "WEP" if packet.wlan_mgt.fixed.all.capabilities_tree.has_field("privacy") and packet.wlan_mgt.fixed.all.capabilities_tree.privacy == 1 else "Open"
                if pencryption == "WEP":
                    pcipher = "WEP"

        except AttributeError as e:
            module_logger.warning("Failed to parse packet: {}".format(e))
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
            meta[meta_csv_fieldnames[0]],
            meta[meta_csv_fieldnames[1]],
            meta[meta_csv_fieldnames[4]],
            meta[meta_csv_fieldnames[5]],
            ptime,
            str(pbssid),
            str(pssid),
            pencryption,
            pcipher,
            pauth,
            pssi,
            pchannel,
            pbearing_magnetic,
            pbearing_true,
            meta[meta_csv_fieldnames[6]],
            meta[meta_csv_fieldnames[7]],
            meta[meta_csv_fieldnames[8]],
            meta[meta_csv_fieldnames[9]],
            meta[meta_csv_fieldnames[10]],
            meta[meta_csv_fieldnames[11]],
        ])

        _beacon_count += 1

    _results_df = pd.DataFrame(_rows, columns=_default_columns)
    # Add mw column
    _results_df.loc[:, 'mw'] = dbm_to_mw(_results_df['ssi'])
    module_logger.info("Completed processing {} beacons ({} failures)".format(_beacon_count, _beacon_failures))

    # If asked to guess, return list of bssids and a guess as to their bearing
    if guess:
        _columns = ['ssid', 'bssid', 'channel', 'security', 'strength', 'method', 'bearing']
        _rows = []

        with futures.ProcessPoolExecutor() as executor:

            _guess_processes = {}

            for names, group in _results_df.groupby(['ssid', 'bssid']):
                _channel = group.groupby('channel').count()['capture'].idxmax()
                _encryption = pd.unique(group['encryption'])[0]
                # _cipher = pd.unique(group['cipher'])[0]
                # _auth = pd.unique(group['auth'])[0]
                _strength = group['ssi'].max()
                if not names[0]:
                    names = ('<blank>', names[1])

                _row = [names[0], names[1], _channel, _encryption, _strength]
                _guess_processes[executor.submit(locate.interpolate, group, int(meta['degrees']))] = _row

            for future in futures.as_completed(_guess_processes):
                _row = _guess_processes[future]
                _guess, _method = future.result()
                _rows.append(_row + [_method, _guess])

            guess = pd.DataFrame(_rows, columns=_columns).sort_values('strength', ascending=False)

    # If a path is given, write the results to a file
    if write_to_disk:
        _results_path = os.path.join(path, time.strftime('%Y%m%d-%H-%M-%S') + "-results" + ".csv")
        _results_df.to_csv(_results_path, sep=',', index=False)
        module_logger.info("Wrote results to {}".format(_results_path))
        write_to_disk = _results_path

    return _beacon_count, _results_df, write_to_disk, guess


def _check_capture_dir(files):
    """
    Check whether the list of files has the required files in it to be considered a capture directory

    :param files: Files to check
    :type files: list
    :return: True if the files indicate a capture path, false otherwise
    :rtype: bool
    """

    for suffix in required_suffixes.values():
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

    if any(file.endswith(capture_suffixes["results"]) for file in files):
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
        if file.endswith(capture_suffixes["meta"]):
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

    # Walk through each subdirectory of working directory
    module_logger.info("Building list of directories to process")

    with futures.ProcessPoolExecutor() as executor:

        _processes = {}
        _results = 0

        for root, dirs, files in os.walk(os.getcwd()):
            if not _check_capture_dir(files):
                continue
            elif _check_capture_processed(files):
                continue
            else:
                # Add meta file to list
                _file = _get_capture_meta(files)
                assert _file is not None
                _path = os.path.join(root, _file)

                with open(_path, 'rt') as meta_csv:
                    _meta_reader = csv.DictReader(meta_csv, dialect='unix')
                    meta = next(_meta_reader)

                _processes[executor.submit(process_capture, meta, root, True, False, clockwise, macs)] = _path

        print("Found {} unprocessed data sets".format(len(_processes)))

        if _processes:
            with tqdm(total = len(_processes), desc = "Processing") as _pbar:
                for future in futures.as_completed(_processes):
                    _beacon_count, _, _, _ = future.result()
                    _results += _beacon_count
                    _pbar.update(1)

                print("Processed {} packets in {} directories".format(_results, len(_processes)))


def dbm_to_mw(dbm):
    return 10**(dbm/10)
