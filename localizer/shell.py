import abc
import configparser
import csv
import datetime
import logging
import os
import pprint
import subprocess
import time
from cmd import Cmd
from distutils.util import strtobool

from tqdm import tqdm

import localizer
from localizer import capture, process, meta, antenna, interface
from localizer.capture import APs

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
        self._aps = APs()

        # Ensure we have root
        if os.getuid() != 0:
            print("Error: this application needs root to run correctly. Please run as root.")
            exit(1)

        # WiFi
        module_logger.info("Initializing WiFi")
        # Set interface to first
        iface = interface.get_first_interface()
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
        Process the results of all captures in the current working directory.
        This command will look in each subdirectory of the current path for unprocessed captures
        It looks for valid *-capture.csv, etc, and processes the files to build *.results.csv
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
                iface = interface.get_first_interface()

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
                elif param == "capture":
                    self._params.capture = value

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
                pprint.pprint(interface.get_interfaces())
            elif split_args[0] == "params":
                print(str(self._params))
            elif split_args[0] == "bearing":
                print("Current bearing: {} degrees".format(antenna.bearing_current))
            else:
                module_logger.error("Unknown parameter '{}'".format(split_args[0]))
        else:
            pprint.pprint(interface.get_interfaces())
            print(str(self._params))
            print("Debug is {}".format(localizer.debug))
            print("HTTP server is {}".format(localizer.serve))

    def do_list(self, _):
        """
        List any detected access points, their bearing, and whether they have been scanned
        """

        if self._aps:
            print(self._aps)
        else:
            print("No detected aps, or scan hasn't been performed")

    def do_capture(self, args):
        """
        Start the capture with the needed parameters set
        """

        split_args = args.split()

        if len(split_args) >= 1 and int(split_args[0]) < len(self._aps):
            # Build focused capture based on selected access point
            _ap = self._aps[int(split_args[0])]
            _prediction = _ap.bearing
            _bearing = _prediction - capture.OPTIMAL_CAPTURE_DEGREES_FOCUSED/2
            _duration = antenna.FOCUSED_RATE[capture.OPTIMAL_CAPTURE_DEGREES_FOCUSED] * capture.OPTIMAL_CAPTURE_DEGREES_FOCUSED / 360
            _channel = _ap.channel
            _bssid = _ap.bssid
            _try_params = localizer.meta.Params(self._params.iface, _duration, capture.OPTIMAL_CAPTURE_DEGREES_FOCUSED, _bearing, hop_int=0, channel= _channel, macs=[_bssid])
            module_logger.info("Setting capture to focused mode")
        else:
            _try_params = self._params

        if not _try_params.validate():
            module_logger.error("You must set 'iface' and 'duration' parameters first")
        else:
            # Shutdown http server if it's on
            localizer.shutdown_httpd()

            module_logger.info("Starting capture")
            try:
                _result = capture.capture(_try_params, reset=_try_params.bearing_magnetic)
                if _result:
                    _capture_path, _meta = _result

                    with open(os.path.join(_capture_path, _meta), 'rt') as meta_csv:
                        _meta_reader = csv.DictReader(meta_csv, dialect='unix')
                        meta = next(_meta_reader)

                    _, _, _, _aps = process.process_capture(meta, _capture_path, write_to_disk=False, guess=True, macs=_try_params.macs)
                    if len(self._aps):
                        self._aps.update(_aps)
                    else:
                        self._aps.aps = _aps
                    print(self._aps)
                else:
                    raise RuntimeError("Capture failed")

            except RuntimeError as e:
                module_logger.error(e)

            finally:
                # Restart http server if it is supposed to be on
                if localizer.serve:
                    localizer.start_httpd()

    def do_connect(self, args):
        """
        Connect to the specified access point number from the list command with the provided password.
        """
        split_args = args.split()

        if len(split_args) >= 2 and int(split_args[0]) < len(self._aps):
            # Build focused capture based on selected access point
            _ap = self._aps[int(split_args[0])]
            _prediction = int(_ap.bearing)
            # Set antenna to predicted bearing
            antenna.AntennaThread.reset_antenna(_prediction)

            # Connect to the access point
            try:
                WiFiConnectShell(self._params.iface, _ap.ssid, split_args[1])
            except ValueError as e:
                module_logger.error(e)
        else:
            print("You must provide an AP number and a password")

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
        if self._params.capture:
            capture = (self._params.capture[:7] + '..') if len(self._params.capture) > 9 else self._params.capture
            elements.append(localizer.G + capture)
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
        self.cmdloop("You are now in batch processing mode. Type 'exit' to return to the capture shell")

    def do_import(self, args):
        """
        Import all captures in the current directory, or the capture name provided. Captures are files that end in -capture.conf

        :param args: capture to import
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
                    if os.path.isfile(arg + meta.capture_suffixes['capture']):
                        _filenames.append(arg + meta.capture_suffixes['capture'])
        else:
            # Get list of valid capture batches in current directory
            _filenames = [file for file in next(os.walk('.'))[2] if file.endswith(meta.capture_suffixes['capture'])]

        print("Found {} batches".format(len(_filenames)))

        # Import captures from each batch
        _count = 0
        for batch in tqdm(_filenames):
            try:
                _name, _passes, _captures = BatchShell._parse_batch(batch)
                self._batches.append((_name, _passes, _captures))
                _count += 1
            except ValueError as e:
                module_logger.error(e)

        logging.info("Imported {} batches".format(_count))

    def complete_import(self, text, _, __, ___):
        return [file for file in next(os.walk('.'))[2] if file.startswith(text) and file.endswith(meta.capture_suffixes['capture'])]

    def do_capture(self, _):
        """
        Run all the imported captures
        """

        if not self._batches:
            print("No batches have been imported")
        else:
            _total = 0
            for _, _passes, _captures in self._batches:
                _total += len(_captures)*_passes

            _start_time = time.time()
            print("Starting batch of {} captures".format(_total))
            _curr = 0
            for _, _passes, _captures in self._batches:
                _len_pass = len(str(_passes))
                for cap in _captures:
                    for p in range(_passes):
                        print(localizer.R + "Capture {:>4}/{}\t\t{} elapsed".format(_curr, _total, datetime.timedelta(seconds=time.time()-_start_time)) + localizer.W)
                        capture.capture(cap, str(p).zfill(_len_pass), cap.bearing_magnetic)
                        _curr += 1

            print("Complete - total time elapsed: {}".format(datetime.timedelta(seconds=time.time()-_start_time)))

    def do_get(self, _):
        """
        Print the captures
        """

        for _name, _passes, _captures in self._batches:
            for cap in _captures:
                print(cap)

            print("Batch: {}; {} captures, {} passes each".format(_name, len(_captures), _passes))

        print("Estimated total runtime: {:0>8}".format(str(self._calculate_runtime())))

    def do_pause(self, args):
        """
        Pause between captures to allow for antenna calibration

        :param args: True to pause between captures, False to continue to the next capture immediately
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
        Calculate an estimated runtime for the imported captures
        :return: Estimated runtime
        :rtype: int
        """

        _time = 0
        for _, _passes, _captures in self._batches:
            for cap in _captures:
                _time_temp = ((cap.duration * _passes))

                if cap.focused:
                    _nmacs = len(cap.macs)
                    _deg, _dur = cap.focused
                    _time_fine = (_deg * _dur) / 360
                    _time_fine *= _nmacs
                    _time_temp += _time_fine

                _time += _time_temp

        return datetime.timedelta(seconds=_time)


    @staticmethod
    def _parse_batch(file):
        """
        Import captures from the supplied batch file

        :param file: Path to the file to import
        :type file: str
        :return: A tuple containing a passes value and a list containing captures
        :rtype: (str, int, list)
        """

        _name = file[:file.find(meta.capture_suffixes['capture'])]
        _captures = []

        config = configparser.ConfigParser()
        config.read(file, encoding='ascii')

        if not len(config.sections()):
            raise ValueError("Invalid capture config file: {}".format(file))

        _passes = int(config['meta']['passes'])

        for section in config.sections():
            if section == 'meta':
                continue

            cap = BatchShell._build_capture(config[section], config['meta'])
            if cap:
                _captures.append(cap)

        print("Imported {}/{} captures from {} batch ({} passes)".format(len(_captures), len(config.sections()) - 1, _name, _passes))
        return _name, _passes, _captures

    @staticmethod
    def _build_capture(capture_section, meta_section):
        """
        Use a dictionary from configparser to build a capture object

        :param capture_section: A dictionary of key and values with capture properties
        :type capture_section: dict
        :param meta_section: A dictionary of key and values with default properties
        :type meta_section: dict
        :return: A Params object
        :rtype: Params()
        """

        try:
            if 'iface' in capture_section and capture_section['iface']:
                _iface = capture_section['iface']
            elif 'iface' in meta_section and meta_section['iface']:
                _iface = meta_section['iface']
            else:
                _iface = interface.get_first_interface()
                if not _iface:
                    raise ValueError("No valid interface provided or available on system")

            if 'duration' in capture_section:
                _duration = capture_section['duration']
            elif 'duration' in meta_section:
                _duration = meta_section['duration']
            else:
                _duration = capture.OPTIMAL_CAPTURE_DURATION

            if 'degrees' in capture_section:
                _degrees = capture_section['degrees']
            elif 'degrees' in meta_section:
                _degrees = meta_section['degrees']
            else:
                raise ValueError("No valid degrees")

            if 'bearing' in capture_section:
                _bearing = capture_section['bearing']
            elif 'bearing' in meta_section:
                _bearing = meta_section['bearing']
            else:
                raise ValueError("No valid bearing")

            if 'hop_int' in capture_section:
                _hop_int = capture_section['hop_int']
            elif 'hop_int' in meta_section:
                _hop_int = meta_section['hop_int']
            else:
                _hop_int = interface.OPTIMAL_BEACON_INT

            if 'hop_dist' in capture_section:
                _hop_dist = capture_section['hop_dist']
            elif 'hop_dist' in meta_section:
                _hop_dist = meta_section['hop_dist']
            else:
                _hop_dist = interface.STD_CHANNEL_DISTANCE

            if 'capture' in capture_section:
                _capture = capture_section['capture']
            elif 'capture' in meta_section:
                _capture = meta_section['capture']
            else:
                raise ValueError("No valid capture name")

            if 'macs' in capture_section:
                _macs = capture_section['macs'].split(',')
            elif 'macs' in meta_section:
                _macs = meta_section['macs'].split(',')
            else:
                _macs = None

            if 'channel' in capture_section:
                _channel = capture_section['channel']
            elif 'channel' in meta_section:
                _channel = meta_section['channel']
            else:
                _channel = None

            if 'focused' in capture_section:
                _focused = tuple(capture_section['focused'].split(','))
            elif 'focused' in meta_section:
                _focused = tuple(meta_section['focused'].split(','))
            else:
                _focused = None

            cap = localizer.meta.Params(_iface, _duration, _degrees, _bearing, _hop_int, _hop_dist, _macs, _channel, _focused, _capture)
            # Validate iface
            module_logger.debug("Setting iface {}".format(_iface))
            cap.iface = _iface

            return cap

        except ValueError as e:
            module_logger.warning(e)
            return None

    def _update_prompt(self):
        self.prompt = localizer.GR + os.getcwd() + localizer.W + ":" + localizer.G + "batch" + localizer.W + "> "


class WiFiConnectShell(ExitCmd, ShellCmd, DirCmd, DebugCmd):
    connect_timeout = 5

    def __init__(self, iface, ap, password):
        super().__init__()

        self._iface = iface
        self._ap = ap
        self._pw = password

        # Kill any existing wpa_supplicant instance
        subprocess.run(['killall', 'wpa_supplicant'])

        self._mode = interface.get_interface_mode(self._iface)
        # Take interface out of monitor mode
        if self._mode != "managed":
            interface.set_interface_mode(self._iface, "managed")

        print("Connecting to {}...".format(self._ap))
        # Try to connect - timeout if otherwise
        self._proc = subprocess.Popen(['/bin/bash', '-c', 'wpa_supplicant -i {} -c <(wpa_passphrase {} {})'.format(self._iface, self._ap, self._pw)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Wait for process to output "File: ..." to stderr and then set flag for other threads
        curr_line = ""
        try:
            _time_waited = 0
            while "CTRL-EVENT-CONNECTED" not in curr_line:
                curr_line = self._proc.stdout.readline().decode()
                module_logger.debug("wpa_supplicant: {}".format(curr_line))
                time.sleep(.1)
                _time_waited += .1
                if _time_waited >= WiFiConnectShell.connect_timeout:
                    raise TimeoutError()
        except TimeoutError:
            self.do_disconnect(None)
            raise ValueError("Timed out connecting to {}".format(self._ap))

        print("Getting IP address, waiting 10 seconds...")
        try:
            subprocess.run(['dhclient', self._iface], timeout=10)
        except subprocess.TimeoutExpired:
            self.do_disconnect(None)
            raise ValueError("Timed out getting IP address")

        # Start the command loop - these need to be the last lines in the initializer
        self._update_prompt()
        self.cmdloop("You are now connected to {}. Type 'disconnect' to disconnect and return to the capture shell".format(self._ap))

    def do_ping(self, args):
        """
        Send a ping request to 8.8.8.8 or a provided IP to check internet connectivity
        """
        _ip = "8.8.8.8"

        arg_split = args.split()
        if len(arg_split) > 0:
            _ip = arg_split[0]

        _proc = subprocess.Popen("ping {} -c 5 -I {}".format(_ip, self._iface), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        while True:
            line = _proc.stdout.readline()
            if line != '':
                print(line.decode())
            else:
                break

    def do_disconnect(self, _):
        """
        Disconnect from the current AP
        """
        self._proc.kill()
        subprocess.run(['killall', 'wpa_supplicant'])
        interface.set_interface_mode(self._iface, self._mode)
        return self.do_exit(None)

    def _update_prompt(self):
        self.prompt = localizer.GR + os.getcwd() + localizer.W + ":" + localizer.G + "connect:" + self._ap + localizer.W + "> "