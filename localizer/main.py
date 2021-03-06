import argparse
from os import getcwd

import localizer


# STARTUP
def main():

    parser = argparse.ArgumentParser()
    me_group = parser.add_mutually_exclusive_group()
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
    parser.add_argument("-m", "--macs",
                        help="If processing, a file containing mac addresses to filter on")
    parser.add_argument("-ccw", "--counterclockwise",
                        help="Set this flag if the captures were performed in a counter-clockwise direction",
                        action="store_true")
    me_group.add_argument("-s", "--shell",
                          help="Start the localizer shell",
                          action="store_true")
    parser.add_argument("--serve",
                        help="Serve files from the working directory on port 80. This flag may also be set in the shell",
                        action="store_true")
    args = parser.parse_args()

    localizer.set_debug(args.debug)

    # Validate provided directory
    try:
        localizer.set_working_dir(args.workingdir)
    except ValueError as e:
        print(e)
        exit(1)

    if args.serve:
        localizer.set_serve(args.serve)

    if args.macs:
        args.macs = localizer.load_macs(args.macs)

    # Shell Mode
    if args.shell:
        from localizer.shell import LocalizerShell
        LocalizerShell(args.macs)

    elif args.process:
        from localizer import process
        process.process_directory(args.macs, not args.counterclockwise)

    elif args.serve:
        import socket
        input("Serving files from {} on {}:80, press any key to exit".format(getcwd(), socket.gethostname()))

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
