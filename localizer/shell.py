import abc
import configparser
import datetime
import logging
import os
import pprint
import time
from cmd import Cmd
from distutils.util import strtobool

from tqdm import tqdm

import localizer
from localizer import wifi, capture, process, meta, antenna

module_logger = logging.getLogger(__name__)
_file_handler = logging.FileHandler('localizer.log')
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s: %(message)s'))
module_logger.addHandler(_file_handler)
module_logger.info("****STARTING LOCALIZER****")


# Helper class for exit functionality
class ExitCmd(Cmd):
    @staticmethod
    def can_exit():
        return True

    def onecmd(self, line):
        r = super().onecmd(line)
        if r and (self.can_exit() or input('exit anyway ? (yes/no):') == 'yes'):
            return True
        return False

    @staticmethod
    def do_exit(_):
        """Exit the interpreter."""
        return True

    @staticmethod
    def do_quit(_):
        """Exit the interpreter."""
        return True

    def emptyline(self):
        pass


# Helper class for shell command functionality
class ShellCmd(Cmd, object):
    @staticmethod
    def do_shell(args):
        """Execute shell commands in the format 'shell <command>'"""
        os.system(args)


# Helper class for debug toggling
class DebugCmd(Cmd, object):

    @staticmethod
    def do_debug(args):
        """
        Sets printing of debug information or shows current debug level if no param given

        :param args: (Optional) Set new debug value.
        :type args: str
        """

        args = args.split()
        if len(args) > 0:
            try:
                val = strtobool(args[0])
                localizer.set_debug(val)
            except ValueError:
                module_logger.error("Could not understand debug value '{}'".format(args[0]))

        print("Debug is {}".format("ENABLED" if localizer.debug else "DISABLED"))


# Helper class for cd and directory functions
class DirCmd(Cmd, object, metaclass=abc.ABCMeta):

    def do_cd(self, args):
        """
        cd into specified path

        :param args: path to cd into
        """

        args = args.split()
        if len(args) == 0:
            print(os.getcwd())
        else:
            try:
                localizer.set_working_dir(args[0])

            except ValueError as e:
                module_logger.error(e)
            finally:
                self._update_prompt()

    @abc.abstractmethod
    def _update_prompt(self):
        raise NotImplementedError("Subclasses of this class must implement _update_prompt")


# Base Localizer Shell Class
class LocalizerShell(ExitCmd, ShellCmd, DirCmd, DebugCmd):

    def __init__(self, macs=None):
        super().__init__()

        self._modules = ["antenna", "gps", "capture", "wifi"]
        self._params = meta.Params()
        if macs:
            self._params.macs = macs
        self._aps = {}

        # Ensure we have root
        if os.getuid() != 0:
            print("Error: this application needs root to run correctly. Please run as root.")
            exit(1)

        # WiFi
        module_logger.info("Initializing WiFi")
        # Set interface to first
        iface = wifi.get_first_interface()
        if iface is not None:
            self._params.iface = iface
        else:
            module_logger.error("No valid wireless interface available")
            exit(1)

        # Start the command loop - these need to be the last lines in the initializer
        self._update_prompt()
        self.cmdloop('Welcome to Localizer Shell...')

    @staticmethod
    def do_serve(args):
        """
        Sets serving of the working directory over http:80, or shows current setting if no param given

        :param args: (Optional) Set new serve value.
        :type args: str
        """

        args = args.split()
        if len(args) > 0:
            try:
                val = strtobool(args[0])
                localizer.set_serve(val)
            except ValueError:
                module_logger.error("Could not understand serve value '{}'".format(args[0]))

        print("Serve is {}".format("ENABLED" if localizer.serve else "DISABLED"))
        if localizer.serve:
            print("HTTP serving working dir {} on port :{}".format(os.getcwd(), localizer.PORT))

    @staticmethod
    def do_process(_):
        """
        Process the results of all tests in the current working directory.
        This command will look in each subdirectory of the current path for unprocessed tests
        It looks for valid *-test.csv, etc, and processes the files to build *.results.csv
        """

        _processed = process.process_directory()

        print("Processed {} captures".format(_processed))

    def do_set(self, args):
        """
        Set a named parameter. All parameters require a value except for iface and macs
        - iface without a parameter will set the iface to the first system wireless iface found
        - macs without a parameter will delete the mac address whitelist

        :param args: Parameter name followed by new value
        :type args: str
        """

        split_args = args.split()
        if len(split_args) < 1:
            module_logger.error("You must provide at least one argument".format(args))
        elif len(split_args) == 1:
            if split_args[0] == "iface":
                iface = wifi.get_first_interface()

                if iface is not None:
                    self._params.iface = iface
                else:
                    module_logger.error("There are no wireless interfaces available.")
            elif split_args[0] == 'macs':
                self._params.macs = []
            else:
                module_logger.error("Parameters require a value".format(split_args[0]))
        elif split_args[0] in meta.Params.VALID_PARAMS:
            try:
                param = split_args[0]
                value = split_args[1]
                # Validate certain parameters
                if split_args[0] == "iface":
                    self._params.iface = value
                elif param == "duration":
                    self._params.duration = value
                elif param == "degrees":
                    self._params.degrees = value
                elif param == "bearing":
                    self._params.bearing_magnetic = value
                elif param == "hop_int":
                    self._params.hop_int = value
                elif param == "hop_dist":
                    self._params.hop_dist = value
                elif param == "mac":
                    self._params.add_mac(value)
                elif param == "macs":
                    # Load macs from provided file
                    self._params.add_mac(localizer.load_macs(value))
                elif param == "channel":
                    self._params.channel = value
                elif param == "test":
                    self._params.test = value

                print("Parameter '{}' set to '{}'".format(param, value))

            except (ValueError, FileNotFoundError) as e:
                module_logger.error(e)
        else:
            module_logger.error("Invalid parameter '{}'".format(split_args[0]))

        self._update_prompt()

    def do_get(self, args):
        """
        View the specified parameter or all parameters if none specified. May also view system interface data

        :param args: param name, ifaces for system interfaces, or blank for all parameters
        :type args: str
        """

        split_args = args.split()

        if len(split_args) >= 1:
            if split_args[0] == "ifaces":
                pprint.pprint(wifi.get_interfaces())
            elif split_args[0] == "params":
                print(str(self._params))
            elif split_args[0] == "bearing":
                print("Current bearing: {} degrees".format(antenna.bearing_current))
            else:
                module_logger.error("Unknown parameter '{}'".format(split_args[0]))
        else:
            pprint.pprint(wifi.get_interfaces())
            print(str(self._params))
            print("Debug is {}".format(localizer.debug))
            print("HTTP server is {}".format(localizer.serve))

    def do_list(self, _):
        """
        List any detected access points, their bearing, and whether they have been scanned
        """

        if self._aps:
            pprint.pprint(self._aps)
        else:
            print("No detected aps, or scan hasn't been performed")

    def do_capture(self, _):
        """
        Start the capture with the needed parameters set
        """

        if not self._params.validate():
            module_logger.error("You must set 'iface' and 'duration' parameters first")
        else:
            # Shutdown http server if it's on
            localizer.shutdown_httpd()

            module_logger.info("Starting capture")
            try:
                _result = capture.capture(self._params, reset=self._params.bearing_magnetic)
                if _result:
                    _capture_path, _meta = _result
                    _, _, _, _aps = process.process_capture(os.path.join(_capture_path, _meta), write_to_disk=False, guess=True, macs=self._params.macs)
                    print(_aps)
                else:
                    raise RuntimeError("Cappture failed")

            except RuntimeError as e:
                module_logger.error(e)

            finally:
                # Restart http server if it is supposed to be on
                if localizer.serve:
                    localizer.start_httpd()

    @staticmethod
    def do_batch(_):
        """
        Start batch mode
        """

        BatchShell()

    def _update_prompt(self):
        """
        Update the command prompt based on the iface and duration parameters
        """

        elements = [localizer.GR + os.getcwd()]
        if self._params.test:
            test = (self._params.test[:7] + '..') if len(self._params.test) > 9 else self._params.test
            elements.append(localizer.G + test)
        if self._params.iface is not None:
            elements.append(localizer.C + self._params.iface)
        if self._params.duration > 0:
            elements.append(localizer.GR + str(self._params.duration) + 's')

        separator = localizer.W + ':'
        self.prompt = separator.join(elements) + localizer.W + '> '


class BatchShell(ExitCmd, ShellCmd, DirCmd, DebugCmd):

    def __init__(self):
        super().__init__()

        self._pause = True
        self._batches = []

        # Start the command loop - these need to be the last lines in the initializer
        self._update_prompt()
        self.cmdloop("You are now in batch processing mode. Type 'exit' to return to the regular shell")

    def do_import(self, args):
        """
        Import all tests in the current directory, or the test name provided. Tests are files that end in -test.conf

        :param args: test to import
        :type args: str
        """

        _filenames = []

        args = args.split()
        # Check for provided filename
        if len(args):
            for arg in args:
                if os.path.isfile(arg):
                    _filenames.append(arg)
                else:
                    if os.path.isfile(arg + meta.capture_suffixes['test']):
                        _filenames.append(arg + meta.capture_suffixes['test'])
        else:
            # Get list of valid test batches in current directory
            _filenames = [file for file in next(os.walk('.'))[2] if file.endswith(meta.capture_suffixes['test'])]

        print("Found {} batches".format(len(_filenames)))

        # Import tests from each batch
        _count = 0
        for batch in tqdm(_filenames):
            try:
                _name, _passes, _tests = BatchShell._parse_batch(batch)
                self._batches.append((_name, _passes, _tests))
                _count += 1
            except ValueError as e:
                module_logger.error(e)

        logging.info("Imported {} batches".format(_count))

    def complete_import(self, text, _, __, ___):
        return [file for file in next(os.walk('.'))[2] if file.startswith(text) and file.endswith(meta.capture_suffixes['test'])]

    def do_capture(self, _):
        """
        Run all the imported tests
        """

        if not self._batches:
            print("No batches have been imported")
        else:
            _total = 0
            for _, _passes, _tests in self._batches:
                _total += len(_tests)*_passes

            _start_time = time.time()
            print("Starting batch of {} tests".format(_total))
            _curr = 0
            for _, _passes, _tests in self._batches:
                _len_pass = len(str(_passes))
                for test in _tests:
                    for p in range(_passes):
                        print(localizer.R + "Test {:>4}/{}\t\t{} elapsed".format(_curr, _total, datetime.timedelta(seconds=time.time()-_start_time)) + localizer.W)
                        capture.capture(test, str(p).zfill(_len_pass), test.bearing_magnetic)
                        _curr += 1

            print("Complete - total time elapsed: {}".format(datetime.timedelta(seconds=time.time()-_start_time)))

    def do_get(self, _):
        """
        Print the tests
        """

        for _name, _passes, _tests in self._batches:
            for test in _tests:
                print(test)

            print("Batch: {}; {} tests, {} passes each".format(_name, len(_tests), _passes))

        print("Estimated total runtime: {:0>8}".format(str(self._calculate_runtime())))

    def do_pause(self, args):
        """
        Pause between tests to allow for antenna calibration

        :param args: True to pause between tests, False to continue to the next test immediately
        :type args: str
        """

        args = args.split()
        if len(args) > 0:
            try:
                self._pause = strtobool(args[0])
            except ValueError:
                module_logger.error("Could not understand pause value '{}'".format(args[0]))

        print("Pause is {}".format("ENABLED" if self._pause else "DISABLED"))

    def do_clear(self, _):
        """
        Clear all batches
        """

        self._batches = []

    def _calculate_runtime(self):
        """
        Calculate an estimated runtime for the imported tests
        :return: Estimated runtime
        :rtype: int
        """

        _time = 0
        for _, _passes, _tests in self._batches:
            for test in _tests:
                _test_overhead = antenna.RESET_RATE + 2
                _time_temp = ((test.duration * _passes) + _test_overhead)

                if test.focused:
                    _nmacs = len(test.macs)
                    _deg, _dur = test.focused
                    _time_fine = (_deg * _dur) / 360 + _test_overhead
                    _time_fine *= _nmacs
                    _time_temp += _time_fine

                _time += _time_temp

        return datetime.timedelta(seconds=_time)

    @staticmethod
    def _parse_batch(file):
        """
        Import tests from the supplied batch file

        :param file: Path to the file to import
        :type file: str
        :return: A tuple containing a passes value and a list containing tests
        :rtype: (str, int, list)
        """

        _name = file[:file.find(meta.capture_suffixes['test'])]
        _tests = []

        config = configparser.ConfigParser()
        config.read(file, encoding='ascii')

        if not len(config.sections()):
            raise ValueError("Invalid test config file: {}".format(file))

        _passes = int(config['meta']['passes'])

        for section in config.sections():
            if section == 'meta':
                continue

            test = BatchShell._build_test(config[section], config['meta'])
            if test:
                _tests.append(test)

        print("Imported {}/{} tests from {} batch ({} passes)".format(len(_tests), len(config.sections()) - 1, _name, _passes))
        return _name, _passes, _tests

    @staticmethod
    def _build_test(test_section, meta_section):
        """
        Use a dictionary from configparser to build a test object

        :param test_section: A dictionary of key and values with test properties
        :type test_section: dict
        :param meta_section: A dictionary of key and values with default properties
        :type meta_section: dict
        :return: A Params object
        :rtype: Params()
        """

        try:
            if 'iface' in test_section and test_section['iface']:
                _iface = test_section['iface']
            elif 'iface' in meta_section and meta_section['iface']:
                _iface = meta_section['iface']
            else:
                _iface = wifi.get_first_interface()
                if not _iface:
                    raise ValueError("No valid interface provided or available on system")

            if 'duration' in test_section:
                _duration = test_section['duration']
            elif 'duration' in meta_section:
                _duration = meta_section['duration']
            else:
                _duration = capture.OPTIMAL_CAPTURE_DURATION

            if 'degrees' in test_section:
                _degrees = test_section['degrees']
            elif 'degrees' in meta_section:
                _degrees = meta_section['degrees']
            else:
                raise ValueError("No valid degrees")

            if 'bearing' in test_section:
                _bearing = test_section['bearing']
            elif 'bearing' in meta_section:
                _bearing = meta_section['bearing']
            else:
                raise ValueError("No valid bearing")

            if 'hop_int' in test_section:
                _hop_int = test_section['hop_int']
            elif 'hop_int' in meta_section:
                _hop_int = meta_section['hop_int']
            else:
                _hop_int = wifi.OPTIMAL_BEACON_INT

            if 'hop_dist' in test_section:
                _hop_dist = test_section['hop_dist']
            elif 'hop_dist' in meta_section:
                _hop_dist = meta_section['hop_dist']
            else:
                _hop_dist = wifi.STD_CHANNEL_DISTANCE

            if 'test' in test_section:
                _test = test_section['test']
            elif 'test' in meta_section:
                _test = meta_section['test']
            else:
                raise ValueError("No valid test")

            if 'macs' in test_section:
                _macs = test_section['macs'].split(',')
            elif 'macs' in meta_section:
                _macs = meta_section['macs'].split(',')
            else:
                _macs = None

            if 'channel' in test_section:
                _channel = test_section['channel']
            elif 'channel' in meta_section:
                _channel = meta_section['channel']
            else:
                _channel = None

            if 'focused' in test_section:
                _focused = tuple(test_section['focused'].split(','))
            elif 'focused' in meta_section:
                _focused = tuple(meta_section['focused'].split(','))
            else:
                _focused = None

            test = localizer.meta.Params(_iface, _duration, _degrees, _bearing, _hop_int, _hop_dist, _macs, _channel, _focused, _test)
            # Validate iface
            module_logger.debug("Setting iface {}".format(_iface))
            test.iface = _iface

            return test

        except ValueError as e:
            module_logger.warning(e)
            return None

    def _update_prompt(self):
        self.prompt = localizer.GR + os.getcwd() + localizer.W + ":" + localizer.G + "batch" + localizer.W + "> "
