import argparse
import csv
import os
from multiprocessing import Pool

from tqdm import tqdm

from ..capture import meta_csv_fieldnames
from ..process import _check_capture_dir, _get_capture_meta


def fix_meta(file):

    # Open meta information
    with open(file, 'rt') as meta_csv:
        _meta_reader = csv.DictReader(meta_csv, dialect='unix')
        meta = next(_meta_reader)

    _change_flag = False
    # Check for presence of duration and hop_int values
    if meta_csv_fieldnames[4] not in meta or arguments.force:
        meta[meta_csv_fieldnames[4]] = arguments.duration
        _change_flag = True
    if meta_csv_fieldnames[5] not in meta or arguments.force:
        meta[meta_csv_fieldnames[5]] = arguments.hop
        _change_flag = True
    if meta_csv_fieldnames[1] not in meta or arguments.force:
        # Get the pass number from the path if possible
        _head = os.path.split(file)[0]
        if _head:
            try:
                _pass = int(os.path.split(_head)[1])
                meta[meta_csv_fieldnames[1]] = _pass
                _change_flag = True
            except (ValueError, TypeError):
                pass

    # Fix paths
    _path = os.path.split(meta[meta_csv_fieldnames[16]])
    if _path[0]:
        meta[meta_csv_fieldnames[16]] = _path[1]
        _change_flag = True
    _path = os.path.split(meta[meta_csv_fieldnames[17]])
    if _path[0]:
        meta[meta_csv_fieldnames[17]] = _path[1]
        _change_flag = True
    _path = os.path.split(meta[meta_csv_fieldnames[18]])
    if _path[0]:
        meta[meta_csv_fieldnames[18]] = _path[1]
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
parser.add_argument("-p", "--hop",
                    help="Hop interval",
                    type=float,
                    required=True)
parser.add_argument("-d", "--duration",
                    help="Test duration",
                    type=int,
                    required=True)
parser.add_argument("--force",
                    help="Force overwriting existing duration/hop_rate",
                    action="store_true")
parser.add_argument("--dry",
                    help="Perform a dry run",
                    action="store_true")
arguments = parser.parse_args()

print("{} tests fixed".format(process_directory()))
