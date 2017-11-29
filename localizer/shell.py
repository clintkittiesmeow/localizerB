import abc
import configparser
import datetime
import logging
import os
import pprint
from cmd import Cmd
from distutils.util import strtobool

from tqdm import tqdm

import localizer
from localizer import wifi, capture, params, antenna

module_logger = logging.getLogger('localizer')
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

    def __init__(self):
        super().__init__()

        self._modules = ["antenna", "gps", "capture", "wifi"]
        self._params = params.Params()

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
    def do_process(args):
        """
        Process the results of all tests in the current working directory.
        This command will look in each subdirectory of the current path for unprocessed tests
        It looks for valid *-test.csv, etc, and processes the files to build *.results.csv

        :param args: Process provided number of dirs. If blank, all valid subdirectories will be searched.
        :type args: str
        """

        _processed = 0

        args = args.split()
        if len(args) > 0:
            try:
                num_dirs = int(args[0])

                if num_dirs <= 0:
                    raise ValueError()

                _processed = capture.process_directory(num_dirs)

            except ValueError:
                module_logger.error("This command accepts an optional limit parameter. {} is not an int > 0".format(args[0]))

        else:
            _processed = capture.process_directory()

        print("Processed {} captures".format(_processed))

    def do_set(self, args):
        """
        Set a named parameter.

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
            else:
                module_logger.error("Parameters require a value".format(split_args[0]))
        elif split_args[0] in params.Params.VALID_PARAMS:
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
                    self._params.bearing = value
                elif param == "hop_int":
                    self._params.hop_int = value
                elif param == "test":
                    self._params.test = value
                elif param == "process":
                    self._params.process = value

                print("Parameter '{}' set to '{}'".format(param, value))

            except ValueError as e:
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
            else:
                module_logger.error("Unknown parameter '{}'".format(split_args[0]))
        else:
            pprint.pprint(wifi.get_interfaces())
            print(str(self._params))
            print("Debug is {}".format(localizer.debug))
            print("HTTP server is {}".format(localizer.serve))

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
                _capture_path, _meta = capture.capture(self._params)
            except RuntimeError as e:
                module_logger.error(e)
                return

            if self._params.process:
                capture.process_capture(_capture_path, _meta)

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
            _filenames.append(args[0] + capture.TEST_SUFFIX)
            if not os.path.isfile(_filenames[0]):
                print("Invalid file specified: {}".format(args[0]))
                return
        else:
            # Get list of valid test batches in current directory
            _files = next(os.walk('.'))[2]
            for file in _files:
                if file.endswith(capture.TEST_SUFFIX):
                    _filenames.append(file)

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

            print("Starting batch of {} tests".format(_total))
            _curr = 0
            for _, _passes, _tests in self._batches:
                _len_pass = len(str(_passes))
                for test in _tests:
                    for p in range(_passes):
                        print(localizer.R + "Test {:>4}/{}".format(_curr, _total) + localizer.W)
                        capture.capture(test, str(p).zfill(_len_pass))
                        _curr += 1

    def do_show(self, _):
        """
        Print the tests
        """

        for _name, _passes, _tests in self._batches:
            for test in _tests:
                print(test)

            print("Batch: {}; {} tests, {} passes each".format(_name, len(_tests), _passes))

        print("Estimated total runtime: {:0>8}".format(datetime.timedelta(seconds=self._calculate_runtime())))

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
                _time += ((test.duration * _passes) + _test_overhead)
        return _time

    @staticmethod
    def _parse_batch(file):
        """
        Import tests from the supplied batch file

        :param file: Path to the file to import
        :type file: str
        :return: A tuple containing a passes value and a list containing tests
        :rtype: (str, int, list)
        """

        _name = file[:file.find(capture.TEST_SUFFIX)]
        _tests = []

        config = configparser.ConfigParser()
        config.read(file, encoding='ascii')

        if not len(config):
            raise ValueError("Invalid test config file: {}".format(file))

        _passes = int(config['meta']['passes'])

        for section in config.sections():
            if section == 'meta':
                continue

            test = BatchShell._build_test(config[section], config['meta'])
            if test:
                _tests.append(test)

        module_logger.info("Imported {}/{} tests from {} batch ({} passes".format(len(_tests), len(config.sections()) - 1, _name, _passes))
        return _name, _passes, _tests

    @staticmethod
    def _build_test(section, meta):
        """
        Use a dictionary from configparser to build a test object

        :param section: A dictionary of key and values with test properties
        :type section: dict
        :return: A Params object
        :rtype: Params()
        """

        try:
            if 'iface' in section:
                _iface = section['iface']
            elif 'iface' in meta:
                _iface = meta['iface']
            else:
                _iface = wifi.get_first_interface()
                if not _iface:
                    raise ValueError("No valid interface provided or available on system")

            if 'duration' in section:
                _duration = section['duration']
            elif 'duration' in meta:
                _duration = meta['duration']
            else:
                raise ValueError("No valid duration")

            if 'degrees' in section:
                _degrees = section['degrees']
            elif 'degrees' in meta:
                _degrees = meta['degrees']
            else:
                raise ValueError("No valid degrees")

            if 'bearing' in section:
                _bearing = section['bearing']
            elif 'bearing' in meta:
                _bearing = meta['bearing']
            else:
                raise ValueError("No valid bearing")

            if 'hop_int' in section:
                _hop_int = section['hop_int']
            elif 'hop_int' in meta:
                _hop_int = meta['hop_int']
            else:
                raise ValueError("No valid hop_int")

            if 'test' in section:
                _test = section['test']
            elif 'test' in meta:
                _test = meta['test']
            else:
                raise ValueError("No valid test")

            if 'process' in section:
                _process = section['process']
            elif 'process' in meta:
                _process = meta['process']
            else:
                raise ValueError("No valid process")

            test = localizer.params.Params(_iface, _duration, _degrees, _bearing, _hop_int, _test, _process)
            # Validate iface
            test.iface = _iface

            return test

        except ValueError as e:
            logging.warning(e)
            return None

    def _update_prompt(self):
        self.prompt = localizer.GR + os.getcwd() + localizer.W + ":" + localizer.G + "batch" + localizer.W + "> "
