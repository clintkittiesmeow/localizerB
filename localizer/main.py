from localizer.shell import LocalizerShell
import localizer
import argparse
import logging
import os


# STARTUP
def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug",
                        help="Make debug output print to the console. This flag may also be set in the shell",
                        action="store_true")
    parser.add_argument("-w", "--workingdir",
                        help="Set the parent directory for session experiments. If blank, current directory is used.")
    args = parser.parse_args()

    localizer.set_debug(args.debug)
    if args.workingdir is None:
        args.workingdir = os.getcwd()

    # Validate provided directory
    if not localizer.set_working_directory(args.workingdir):
        logging.getLogger('global').error("Provided directory '{}' is not valid".format(args.workingdir))
        exit(1)

    # Set up logging
    logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', filename='localizer.log', level=logging.DEBUG)
    localizer.console_logger = logging.StreamHandler()
    localizer.console_logger.setLevel(logging.DEBUG)
    localizer.console_logger.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    logging.getLogger('global').addHandler(localizer.console_logger)
    localizer.set_debug(localizer.debug)
    logging.getLogger('global').info("****STARTING LOCALIZER****")

    # Start up shell
    LocalizerShell()


if __name__ == '__main__':
    main()
