import argparse
import tempfile

import localizer
from localizer.shell import LocalizerShell


# STARTUP
def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug",
                        help="Make debug output print to the console. This flag may also be set in the shell",
                        action="store_true")
    parser.add_argument("-s", "--server",
                        help="Start a http server in the working directory to host test output",
                        action="store_true")
    parser.add_argument("-w", "--workingdir",
                        help="Set the parent directory for session experiments. If blank, current directory is used.",
                        default=tempfile.gettempdir())
    args = parser.parse_args()

    localizer.set_debug(args.debug)

    # Validate provided directory
    try:
        localizer.set_working_dir(args.workingdir)
    except ValueError as e:
        print(e)
        exit(1)

    # Start up shell
    LocalizerShell()


if __name__ == '__main__':
    main()
