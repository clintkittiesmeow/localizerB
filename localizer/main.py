from localizer.shell import LocalizerShell
import localizer

# STARTUP
def main():
    # Initialize any global variables
    # settings.init()

    # Debug on if argument present

    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'debug':
        localizer.debug = 1
        print("Debug mode is {}".format(localizer.debug))
    else:
        localizer.debug = 0

    # Start up shell
    LocalizerShell()


if __name__ == '__main__':
    main()
