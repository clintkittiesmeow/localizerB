# Modified from wifite.py:
from localizer import utils

from subprocess import Popen, call, PIPE
import os
import atexit

# /dev/null, send output from programs so they don't print to screen.
DN = open(os.devnull, 'w')
ERRLOG = open(os.devnull, 'w')
OUTLOG = open(os.devnull, 'w')


def enable_monitor_mode(iface):
    """
        Uses airmon-ng to put a device into Monitor Mode.
        Then uses the get_iface() method to return the new interface's name.
    """
    utils.log_message("Enabling monitor mode on {}...".format(iface))
    call(['airmon-ng', 'start', iface], stdout=DN, stderr=DN)
    utils.log_message("...done")


def disable_monitor_mode(iface):
    """
        The program may have enabled monitor mode on a wireless interface.
        We want to disable this before we exit, so we will do that.
    """
    utils.log_message("Disabling monitor mode on {}...".format(iface))
    call(['airmon-ng', 'stop', iface], stdout=DN, stderr=DN)
    utils.log_message("...done")


# def rtl8187_fix(iface):
#     """
#         Attempts to solve "Unknown error 132" common with RTL8187 devices.
#         Puts down interface, unloads/reloads driver module, then puts iface back up.
#         Returns True if fix was attempted, False otherwise.
#     """
#     # Check if current interface is using the RTL8187 chipset
#     proc_airmon = Popen(['airmon-ng'], stdout=PIPE, stderr=DN)
#     proc_airmon.wait()
#     using_rtl8187 = False
#     for line in proc_airmon.communicate()[0].split():
#         line = line.upper()
#         if line.strip() == '' or line.startswith('INTERFACE'): continue
#         if line.find(iface.upper()) and line.find('RTL8187') != -1: using_rtl8187 = True
#
#     utils.log_message("Attempting RTL8187 'Unknown Error 132' fix...")
#     original_iface = iface
#     # Take device out of monitor mode
#     airmon = Popen(['airmon-ng', 'stop', iface], stdout=PIPE, stderr=DN)
#     airmon.wait()
#     for line in airmon.communicate()[0].split('\n'):
#         if line.strip() == '' or \
#                 line.startswith("Interface") or \
#                         line.find('(removed)') != -1:
#             continue
#         original_iface = line.split()[0]  # line[:line.find('\t')]
#
#     # Remove drive modules, block/unblock ifaces, probe new modules.
#     call(['ifconfig', original_iface, 'down'], stdout=DN, stderr=DN)
#     time.sleep(0.1)
#     call(['rmmod', 'rtl8187'], stdout=DN, stderr=DN)
#     time.sleep(0.1)
#     call(['rfkill', 'block', 'all'], stdout = DN, stderr = DN)
#     time.sleep(0.1)
#     call(['rfkill', 'unblock', 'all'], stdout = DN, stderr = DN)
#     time.sleep(0.1)
#     call(['modprobe', 'rtl8187'], stdout = DN, stderr = DN)
#     time.sleep(0.1)
#     call(['ifconfig', original_iface, 'up'], stdout = DN, stderr = DN)
#     time.sleep(0.1)
#     call(['airmon-ng', 'start', original_iface], stdout = DN, stderr = DN)
#     time.sleep(0.1)
#
#     return True

def get_interfaces():
    """
    Returns a list of interfaces and a list of monitors
    """
    proc = Popen(['iwconfig'], stdout=PIPE, stderr=DN)
    iface = ''
    monitors = []
    adapters = []
    for line in proc.communicate()[0].split(b'\n'):
        if len(line) == 0: continue
        if line[0] != 32:  # Doesn't start with space
            iface = line[:line.find(b' ')].decode()  # is the interface
            if line.find(b'Mode:Monitor') != -1:
                monitors.append(iface)
            else:
                adapters.append(iface)

    return adapters,monitors


@atexit.register
def cleanup():
    """
    Cleanup - ensure all devices are no longer in monitor mode
    """
    for mon in get_interfaces()[1]:
        disable_monitor_mode(mon)