import RPi.GPIO as GPIO
import time
import threading
import logging
import atexit
import queue
import argparse

GPIO.setwarnings(False)

class AntennaStepperThread(threading.Thread):
    # Default number of steps per radian
    steps_per_revolution = 400
    degrees_per_step = 360 / steps_per_revolution
    microsteps_per_step = 1
    degrees_per_microstep = degrees_per_step / microsteps_per_step

    def __init__(self, command_queue, response_queue, event_flag):

        # Set up thread
        super().__init__()

        logging.getLogger('global').info("Starting Stepper Thread")

        self.daemon = True
        self._command_queue = command_queue
        self._response_queue = response_queue
        self._event_flag = event_flag
        self._seq_position = 0

        self.PUL_min = 21
        self.DIR_min = 20
        self.ENA_min = 16

        # Set up GPIO
        GPIO.setup(self.PUL_min, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.DIR_min, GPIO.OUT)
        GPIO.setup(self.ENA_min, GPIO.OUT)

    def run(self):
        # Wait for commands in the queue
        while True:
            # Execute command (duration, degrees, bearing) tuple
            duration, degrees, bearing = self._command_queue.get()

            pulses = round(degrees / AntennaStepperThread.degrees_per_microstep)
            wait = duration/pulses
            wait_half = wait/2

            bearing_table = {}

            if pulses < 0:
                GPIO.output(self.DIR_min, GPIO.LOW)
                pulses = -pulses
            else:
                GPIO.output(self.DIR_min, GPIO.HIGH)

            GPIO.output(self.ENA_min, GPIO.HIGH)

            # Wait for the synchronization flag
            self._event_flag.wait()

            # Step through each step
            for step in range(0, pulses):
                GPIO.output(self.PUL_min, GPIO.HIGH)
                time.sleep(wait_half)
                GPIO.output(self.PUL_min, GPIO.LOW)
                time.sleep(wait_half)

                bearing_table[time.time()] = bearing
                bearing += AntennaStepperThread.degrees_per_microstep

            GPIO.output(self.ENA_min, GPIO.LOW)

            self._command_queue.task_done()

            # Tell caller a step is finished
            self._response_queue.put(bearing_table)
            self._response_queue.join()


def antenna_test(args):
    """
    Test the antenna rotation

    :param args: A list of string arguments
    :type args: list[duration, degrees]
    :return: Returns a dict if the test was successful, None otherwise
    :rtype: bool
    """
    dur = 0
    degrees = 0

    try:
        if len(args) >= 2:
            dur = int(args[0])
            degrees = int(args[1])
        elif len(args) == 1:
            dur = int(args[0])
        else:
            return None
    except ValueError:
        return None

    _command_queue = queue.Queue()
    _response_queue = queue.Queue()
    _flag = threading.Event()
    _thread = AntennaStepperThread(_command_queue, _response_queue, _flag)
    _thread.start()

    print("Starting antenna test for {}s, please wait...".format(dur))

    _command_queue.put((dur, degrees, 0))
    _flag.set()
    _command_queue.join()

    response = _response_queue.get()
    _response_queue.task_done()
    return response


@atexit.register
def cleanup():
    """
    Cleanup - ensure GPIO is cleaned up properly
    """

    GPIO.cleanup()


# Script can be run standalone to test the antenna
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the antenna by rotating it a number of degrees in a number of seconds")
    parser.add_argument("duration",
                        help="Number of seconds to rotate the antenna",
                        type=int)
    parser.add_argument("degrees",
                        help="Number of degrees to rotate the antenna",
                        type=int,
                        nargs='?',
                        default=360)
    arguments = parser.parse_args()

    response = antenna_test([str(arguments.duration), str(arguments.degrees)])
    if response is None:
        logging.getLogger('global').error("Antenna test failed")
    else:
        print("Antenna test complete")
