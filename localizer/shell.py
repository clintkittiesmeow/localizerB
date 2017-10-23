from cmd import Cmd
from localizer.stepper import StepperThread
from localizer import stepper
from localizer import wifi
import localizer

from localizer import utils

import os
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

        # Ensure we have root
        if os.getuid() != 0:
            print("Error: this application needs root to run correctly. Please run as root.")
            exit(1)

        # Initialize the hardware
        ## Stepper Motor
        self._stepper_commands = queue.Queue()
        self._stepper_response = queue.Queue()
        self._stepper = StepperThread(self._stepper_commands, self._stepper_response)
        self._stepper.start()
        ## WiFi
        ### Get list of interfaces and those in monitor mode
        self._interfaces, self._monitors = wifi.get_interfaces()
        ### Stop monitoring for any interfaces already in monitor mode
        wifi.cleanup()

        # Logging Destination

        # Start the command loop - these need to be the last lines in the initializer
        self.prompt = '> '
        self.cmdloop('Welcome to Localizer Shell...')


    def do_debug(self, args):
        """Sets printing of debug information.

        Arguments:
        0: No debug information is printed
        1: Errors and state changes are printed
        2: Low priority logs are printed
        3: Repeating messages are printed
        """

        try:
            number = int(args)

            # Check for valid number
            if number < 0 or number > len(utils.Level)-1:
                raise ValueError("Out of Bounds Error")
            else:
                localizer.debug = number
        except ValueError as e:
            print("{}\nYou did not provide a valid number (0-{}): '{}'".format(e, len(utils.Level)-1, args))

        print("Debug is set to {} ({})".format(localizer.debug, utils.Level(localizer.debug).name))

    def do_move(self, args):
        """
        Manually rotate the antenna; useful for debugging

        :param type (string): possible input is degree (default) or step
        :param rpm (float): speed of rotation (only for type degree)
        :param degrees (int): number of degrees (total) to rotate (only for type degree)
        :param step_degrees (float): number of degrees each step takes (only for type degree)
        :param delay (float): time to wait between steps (only for type step)
        :param steps (int): number of steps (total) to rotate (only for type step)
        :param step_distance (int): number of stepper steps in each step (only for type step)
        """

        command = None

        try:
            args = args.lower().strip().split()

            if len(args) == 3:
                command = stepper.move_degree(float(args[0]), int(args[1]), float(args[2]))

            elif len(args) == 4:

                if args[0].startswith("deg"):
                    command = stepper.move_degree(float(args[1]), int(args[2]), float(args[3]))

                elif args[0].startswith("step"):
                    command = stepper.move(float(args[1]), int(args[2]), int(args[3]))

                else:
                    raise ValueError("Wrong command syntax")

            else:
                raise ValueError("Wrong command syntax")

        except ValueError as e:
            print("{0}\nYou did not provide a valid command".format(e))
            return

        # Pass command to Stepper Thread and log responses
        self._stepper_commands.put(command)
        while not self._stepper_commands.empty():
            try:
                response = self._stepper_response.get(True, 1/1000)
                self._stepper_response.task_done()
                utils.log_message("Got a response: {}".format(response), utils.Level.MEDIUM)
            except queue.Empty:
                continue

    def do_init(self, args):
        """
        Initialize the specified adapter in monitor mode
        """
        try:
            args = args.split()
            self._interfaces, self._monitors = wifi.get_interfaces()

            if len(args) <= 0:
                raise ValueError("You must specify an interface. Interfaces: {}".format(self._interfaces))

            if args[0] not in self._interfaces:
                raise ValueError("Specified interface ({}) is not valid.".format(args[0]))
            else:
                if args[0] in self._monitors:
                    raise ValueError("Specified interface ({}) is already in monitor mode.".format(args[0]))
                else:
                    wifi.enable_monitor_mode(args[0])
                    self._interfaces, self._monitors = wifi.get_interfaces()
                    print("Monitor interfaces: {}".format(self._monitors))
        except ValueError as e:
            print(e)


    def complete_init(self, text, line, begidx, endidx):
        return [i for i in self._interfaces if i.startswith(text)]

    def emptyline(self):
        pass
