import argparse
import csv
import os
import time
from concurrent import futures

from tqdm import tqdm

from localizer import load_macs
from localizer.meta import meta_csv_fieldnames, capture_suffixes
from localizer.process import _check_capture_dir, _get_capture_meta, process_capture


def fix_meta(path, file, macs=None):
    """
    Check for presence of 'focused' column value, and fill it in
    """

    # Open meta information
    with open(os.path.join(path, file), 'rt') as meta_csv:
        _meta_reader = csv.DictReader(meta_csv, dialect='unix')
        meta = next(_meta_reader)

    _change_flag = False
    _write_flag = False
    _guess = None

    # Check guess column
    if meta_csv_fieldnames[20] not in meta or arguments.force:
        _path = meta[meta_csv_fieldnames[2]]
        _path_split = os.path.split(_path)

        # Check whether path is 2 layers (ie, we are looking at a 'parent' capture (not focused)
        if not os.path.split(_path_split[0])[0]:

            # Generate guesses
            _, _, _, _guess = process_capture(os.path.join(path, file), False, True, True, macs)
            _change_flag = True

    # Write changes to file
    if arguments.force or (not arguments.dry and _change_flag):
        if _guess is not None:
            # guess.csv filename
            _capture_prefix = time.strftime('%Y%m%d-%H-%M-%S')
            _output_csv_guess = _capture_prefix + capture_suffixes["guess"]
            _output = os.path.join(path, _output_csv_guess)
            _guess.to_csv(_output, sep=',')

            # Add column to meta
            meta[meta_csv_fieldnames[20]] = _output_csv_guess
            _write_flag = True

            with open(os.path.join(path, file), 'w', newline='') as test_csv:
                _test_csv_writer = csv.DictWriter(test_csv, dialect="unix", fieldnames=meta_csv_fieldnames)
                _test_csv_writer.writeheader()
                _test_csv_writer.writerow(meta)



    return _change_flag, _write_flag


def process_directory(macs=None):

    with futures.ProcessPoolExecutor() as executor:

        _processes = {}
        _changed = 0
        _written = 0

        # Walk through each subdirectory of working directory
        for root, dirs, files in os.walk(os.getcwd()):
            if not _check_capture_dir(files):
                continue
            else:
                # Add meta file to list
                _file = _get_capture_meta(files)
                assert _file is not None
                _processes[executor.submit(fix_meta, root, _file, macs)] = _file

        print("Found {} completed data sets".format(len(_processes)))

        if _processes:
            with tqdm(total=len(_processes), desc="Processing") as _pbar:
                for future in futures.as_completed(_processes):
                    _c, _w = future.result()
                    if _c:
                        _changed += 1
                    if _w:
                        _written += 1
                    _pbar.update(1)

        _caveat = ''
        if _changed != _written:
            _caveat = " ({} written to disk)".format(_written)

        print("Processed {} captures in {} directories{}".format(_changed, len(_processes), _caveat))
        return _changed


parser = argparse.ArgumentParser(description="Convert discovery test data (meta) to include more details")
parser.add_argument("--force",
                    help="Force overwriting existing duration/hop_rate",
                    action="store_true")
parser.add_argument("--dry",
                    help="Perform a dry run",
                    action="store_true")
parser.add_argument("-m", "--macs",
                    help="If processing, a file containing mac addresses to filter on")
arguments = parser.parse_args()

if arguments.macs:
    arguments.macs = load_macs(arguments.macs)

process_directory(arguments.macs)
