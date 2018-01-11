import argparse
import csv
import os
from multiprocessing import Pool

from tqdm import tqdm

from localizer.meta import meta_csv_fieldnames
from localizer.process import _check_capture_dir, _get_capture_meta


def fix_meta(file):
    """
    Check for presence of 'focused' column value, and fill it in
    """

    # Open meta information
    with open(file, 'rt') as meta_csv:
        _meta_reader = csv.DictReader(meta_csv, dialect='unix')
        meta = next(_meta_reader)

    _change_flag = False
    # Check for presence of 'focused'
    if meta_csv_fieldnames[19] not in meta or arguments.force:
        _path = meta[meta_csv_fieldnames[2]]
        _path_split = os.path.split(_path)
        # Check whether path is 3 layers
        if os.path.split(_path_split[0])[0]:
            # Get the ssid from the path
            _ssid = _path_split[1]
            underscores = [i for i, letter in enumerate(_ssid) if letter == '_']
            if underscores:
                _ssid = _ssid[underscores[-1]+1:]
            if len(_ssid) != 12:
                raise ValueError("Bad ssid format")
            _ssid_chunks = [_ssid[i:i+2] for i in  range(0, len(_ssid), 2)]
            _ssid_reconstituted = ':'.join(_ssid_chunks)
            meta[meta_csv_fieldnames[19]] = _ssid_reconstituted
            _change_flag = True
        else:
            meta[meta_csv_fieldnames[19]] = None
            _change_flag = True

    # Write changes to file
    if not arguments.dry and _change_flag:
        with open(file, 'w', newline='') as test_csv:
            _test_csv_writer = csv.DictWriter(test_csv, dialect="unix", fieldnames=meta_csv_fieldnames)
            _test_csv_writer.writeheader()
            _test_csv_writer.writerow(meta)

    return _change_flag


def process_directory():
    """
    Process entire directory - will search subdirectories for required files and process them if not already processed

    :param limit: limit on the number of directories to process
    :type limit: int
    :return: The number of directories processed
    :rtype: int
    """

    _tasks = []

    # Walk through each subdirectory of working directory
    for root, dirs, files in os.walk(os.getcwd()):
        if not _check_capture_dir(files):
            continue
        else:
            # Add meta file to list
            _file = _get_capture_meta(files)
            assert _file is not None
            _tasks.append(os.path.join(root, _file))

    print("Found {} completed data sets".format(len(_tasks)))

    _results = 0
    if _tasks:
        with Pool(processes=4) as pool:
            for result in tqdm(pool.imap_unordered(fix_meta, _tasks), total=len(_tasks)):
                if result:
                    _results += 1

    return _results


parser = argparse.ArgumentParser(description="Convert discovery test data (meta) to include more details")
parser.add_argument("--force",
                    help="Force overwriting existing duration/hop_rate",
                    action="store_true")
parser.add_argument("--dry",
                    help="Perform a dry run",
                    action="store_true")
arguments = parser.parse_args()

print("{} tests fixed".format(process_directory()))
