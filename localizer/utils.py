from xtermcolor import colorize
from enum import Enum
import localizer

class Level(Enum):
    LOW = 3         # Used for repeating messages (eg heartbeat)
    MEDIUM = 2      # Use this level for low priority logs (messaging, etc)
    HIGH = 1        # Use this level for typical debug logging such as errors, spawning threads, and state change
    FORCE = 0       # Use this level to force printing - useful for errors affecting ledger state


def log_message(message, level=Level.HIGH):
    """
    Log a message - use this function to do any printing to the console. From lowest priority:

    LOW: Use for repeating messages (eg heartbeat)
    MEDIUM: Use for low priority (eg messaging)
    HIGH (default): Use for typical debug logging such as errors, state change, thread spawning, etc
    FORCE: Force printing. Use to print to console regardless of debug state or for errors affecting ledger state
    """

    if localizer.debug >= level.value:
        # Uses termcolor: https://pypi.python.org/pypi/termcolor
        color = 0x0000FF
        background = 0xCCCCCC

        if localizer.debug == Level.MEDIUM:
            color = 0x00FF00
        elif localizer.debug == Level.HIGH:
            color = 0xFFFF00
        elif localizer.debug == Level.FORCE:
            color = 0x0000FF

        print(colorize(message, rgb=color, bg=background))
