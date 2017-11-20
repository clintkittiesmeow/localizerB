import argparse
from os import getcwd

import localizer


# STARTUP
def main():

    parser = argparse.ArgumentParser()
    me_group = parser.add_mutually_exclusive_group(required=True)
    # TODO Implement command line capture and batch
    # group_capture = me_group.add_argument_group('Capture')
    # group_capture.add_argument("-c", "--capture")
    parser.add_argument("-d", "--debug",
                        help="Make debug output print to the console. This flag may also be set in the shell",
                        action="store_true")
    parser.add_argument("-w", "--workingdir",
                        help="Set the parent directory for session experiments. If blank, current directory is used.",
                        default=getcwd())
    me_group.add_argument("-p", "--process",
                        help="Process the files in the current directory, or a provided working directory (-w)",
                        action="store_true")
    me_group.add_argument("-s", "--shell",
                        help="Start the localizer shell",
                        action="store_true")
    args = parser.parse_args()

    localizer.set_debug(args.debug)

    # Validate provided directory
    try:
        localizer.set_working_dir(args.workingdir)
    except ValueError as e:
        print(e)
        exit(1)

    if args.shell:
        from localizer.shell import LocalizerShell
        LocalizerShell()
    elif args.process:
        from localizer import process
        _processed = process.process_directory()
        print("Processed {} captures".format(_processed))


if __name__ == '__main__':
    main()
