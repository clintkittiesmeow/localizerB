from cmd import Cmd
from localizer import wifi, capture, antenna
from distutils.util import strtobool
from threading import Event
import localizer
import logging
import os
import pprint
import queue


# Helper class for exit functionality
class ExitCmd(Cmd):
    @staticmethod
    def can_exit():
        return True

    def onecmd(self, line):
        r = super(ExitCmd, self).onecmd(line)
        if r and (self.can_exit() or input('exit anyway ? (yes/no):') == 'yes'):
            return True
        return False

    @staticmethod
    def do_exit(args):
        """Exit the interpreter."""
        return True

    @staticmethod
    def do_quit(args):
        """Exit the interpreter."""
        return True


# Helper class for shell command functionality
class ShellCmd(Cmd, object):
    @staticmethod
    def do_shell(s):
        """Execute shell commands in the format 'shell <command>'"""
        os.system(s)


# Base Localizer Shell Class
class LocalizerShell(ExitCmd, ShellCmd):

    def __init__(self):
        super(LocalizerShell, self).__init__()

        self._params = {"iface": None,
                        "duration": 0,
                        "degrees": 360.0,
                        "bearing": 0.0,
                        "path": localizer.working_directory,
                        "test": None}

        # Ensure we have root
        if os.getuid() != 0:
            print("Error: this application needs root to run correctly. Please run as root.")
            exit(1)

        # WiFi
        logging.getLogger('global').info("Initializing WiFi")
        # Get list of interfaces and those in monitor mode
        self._interfaces = wifi.get_interfaces().keys()
        # Stop monitoring for any interfaces already in monitor mode
        wifi.cleanup()

        # Start the command loop - these need to be the last lines in the initializer
        self._update_prompt()
        self.cmdloop('Welcome to Localizer Shell...')

    def do_debug(self, args):
        """
        Sets printing of debug information or shows current debug level if no param given

        :param debug_value: (Optional) Set new debug value.
        :type debug_value: str
        """

        args = args.split()
        if len(args) > 0:
            try:
                val = strtobool(args[0])
                localizer.set_debug(val)
            except ValueError:
                logging.getLogger('global').error("Could not understand debug value '{}'".format(args[0]))

        print("Debug is '{}'".format(localizer.debug))

    def do_test(self, args):
        """
        Test the antenna rotation

        :param args: Provide a duration and degrees (degrees defaults to 360 if not provided)
        :type args: str
        """

        dur = 0
        degrees = 360

        args = args.split()
        response = antenna.antenna_test(args)
        if response is None:
            logging.getLogger('global').error("You must provide an argument")


    def do_set(self, args):
        """
        Set a named parameter.

        :param args: Parameter name followed by new value
        :type args: str
        """

        split_args = args.split()
        if not len(split_args) >= 1:
            logging.getLogger('global')\
                .error("Invalid command '{}'; You must provide at least one argument".format(args))
            return

        # When only 1 interface is on system, no need to specify
        if len(split_args) == 1 and split_args[0] == "iface":
            ifaces = list(wifi.get_interfaces())
            if len(ifaces) > 1:
                logging.getLogger('global').error("Please specify an interface: {}".format(ifaces))
                return
            elif len(ifaces) == 1:
                split_args.append(ifaces[0])
            else:
                logging.getLogger('global').error("There are no wireless interfaces available.")
                return

        if split_args[0] in self._params:
            if self._params[split_args[0]] != split_args[1]:
                new_value = split_args[1]
                # Validate certain parameters
                if split_args[0] == "iface" and new_value not in wifi.get_interfaces().keys():
                    logging.getLogger('global').error("Invalid interface '{}'; valid interfaces: {}"
                                                      .format(new_value, wifi.get_interfaces().keys()))
                    return
                elif split_args[0] == "duration":
                    new_value = int(new_value)
                    if new_value <= 0:
                        logging.getLogger('global').error("Invalid duration '{}'; should be larger than 0"
                                                          .format(new_value))
                        return
                elif split_args[0] == "degrees":
                    try:
                        new_value = float(new_value)
                    except (ValueError, OverflowError):
                        logging.getLogger('global').error("Invalid degrees '{}'; should be a float".format(new_value))
                        return
                elif split_args[0] == "bearing":
                    try:
                        new_value = float(new_value)
                        if new_value < 0 or new_value > 360:
                            raise ValueError()
                    except (ValueError, OverflowError):
                        logging.getLogger('global').error("Invalid bearing '{}'; should be between 0 and 360"
                                                          .format(new_value))
                        return
                elif split_args[0] == "path":
                    if not localizer.set_working_directory(new_value):
                        logging.getLogger('global').error("Invalid path '{}'; should be writable".format(new_value))
                        return
                print("Updating parameter '{}' from '{}' to '{}'"
                      .format(split_args[0], self._params[split_args[0]], split_args[1]))
                self._params[split_args[0]] = new_value
            else:
                print("No change in parameter value")

        self._update_prompt()

    def do_get(self, args):
        """
        View the specified parameter or all parameters if none specified. May also view system interface data

        :param args: param name, ifaces for system interfaces, or blank for all parameters
        :type args: str
        """

        split_args = args.split()

        if len(split_args) >= 1:
            if split_args[0] in self._params:
                print(self._params[split_args[0]])
            elif split_args[0].lower() == "ifaces":
                pprint.pprint(wifi.get_interfaces())
            else:
                logging.getLogger('global').error("Unknown parameter '{}'".format(split_args[0]))
                return
        else:
            pprint.pprint(self._params)

    def do_capture(self, args):
        """
        Start the capture with the needed parameters set

        :param args: No parameter needed, but required parameters must be set using the `set` command
        :type args: str
        """

        if self._params["iface"] is None or self._params["duration"] <= 0:
            logging.getLogger('global').error("You must set 'iface' and 'duration' parameters first")
            return

        cap = capture.Capture(self._params["iface"],
                              self._params["duration"],
                              self._params["degrees"],
                              self._params["bearing"],
                              self._params["test"])
        cap.capture()

    def _update_prompt(self):
        """
        Update the command prompt based on the iface and duration parameters
        """

        # Console colors
        W = '\033[0m'  # white (normal)
        R = '\033[31m'  # red
        G = '\033[32m'  # green
        O = '\033[33m'  # orange
        B = '\033[34m'  # blue
        P = '\033[35m'  # purple
        C = '\033[36m'  # cyan
        GR = '\033[37m'  # gray

        params = []
        if self._params["test"] is not None:
            test = (self._params["test"][:7] + '..') if len(self._params["test"]) > 9 else self._params["test"]
            params.append(G + test)
        if self._params["iface"] is not None:
            params.append(C + self._params["iface"])
        if self._params["duration"] > 0:
            params.append(GR + str(self._params["duration"]))

        separator = W + ':'
        self.prompt = separator.join(params) + W + '> '

    def emptyline(self):
        pass
