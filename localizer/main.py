from localizer.shell import LocalizerShell
import localizer
import argparse
import os


# STARTUP
def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug",
                        help="Make debug output print to the console. This flag may also be set in the shell",
                        action="store_true")
    parser.add_argument("-w", "--workingdir",
                        help="Set the parent directory for session experiments. If blank, current directory is used.",
                        default=os.getcwd())
    args = parser.parse_args()

    localizer.set_debug(args.debug)

    # Validate provided directory
    try:
        localizer.params.path = args.workingdir
    except ValueError as e:
        print(e)
        exit(1)

    # Start up shell
    LocalizerShell()


if __name__ == '__main__':
    main()
