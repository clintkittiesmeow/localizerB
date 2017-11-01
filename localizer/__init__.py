import os
import logging

# Shared Variables
debug = 0
working_directory = None
console_logger = None


def set_debug(value):
    global debug
    debug = value
    if console_logger is not None:
        if debug:
            console_logger.setLevel(logging.DEBUG)
        else:
            console_logger.setLevel(logging.ERROR)

        logging.getLogger('global').info("Debug set to {}".format(value))


def set_working_directory(path):
    global working_directory
    try:
        tmpfile = os.path.join(path, 'tmpfile')
        fp = open(tmpfile, 'w')
        fp.write(" ")
        fp.close()
        os.remove(tmpfile)
    except PermissionError:
        logging.getLogger('global').error("Cannot write to working directory '{}'".format(working_directory))
        return False
    else:
        logging.getLogger('global').info("Working directory '{}' successfully validated".format(working_directory))
        working_directory = path
        return True


# /dev/null, send output from programs so they don't print to screen.
DN = open(os.devnull, 'w')
ERRLOG = open(os.devnull, 'w')
OUTLOG = open(os.devnull, 'w')
