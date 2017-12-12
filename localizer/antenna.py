import atexit
import logging
import threading
import time

module_logger = logging.getLogger(__name__)


# Constants
RESET_RATE = 3
# Default number of steps per radian
steps_per_revolution = 400
degrees_per_step = 360 / steps_per_revolution
microsteps_per_step = 32
degrees_per_microstep = degrees_per_step / microsteps_per_step
# Set up GPIO
PUL_min = 17
DIR_min = 27
ENA_min = 22


# Try to perform GPIO setup, but if not available print error and continue
try:
    from RPi import GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PUL_min, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(DIR_min, GPIO.OUT)
    GPIO.setup(ENA_min, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.setwarnings(False)

    cleanup = GPIO.cleanup
    output = GPIO.output
except RuntimeError as e:
    module_logger.warning(e)
    module_logger.info("Setting up dummy functions 'cleanup' and 'output'")

    def cleanup():
        pass

    def output(*_):
        pass


class AntennaStepperThread(threading.Thread):

    def __init__(self, response_queue, event_flag, duration, degrees, bearing, reset=True):

        # Set up thread
        super().__init__()

        module_logger.info("Starting Stepper Thread")

        self.daemon = True
        self._response_queue = response_queue
        self._event_flag = event_flag
        self._duration = duration
        self._degrees = degrees
        self._bearing = bearing
        self._reset = reset

    def run(self):
        # Wait for commands in the queue
        module_logger.info("Executing Stepper Thread")

        # Wait for the synchronization flag
        module_logger.info("Waiting for synchronization flag")
        self._event_flag.wait()

        loop_start_time, loop_stop_time, wait, loop_average_time = self.rotate(self._degrees, self._duration)

        module_logger.info("Rotated antenna {} degrees for {:.2f}s (expected {}s)"
                           .format(self._degrees, loop_stop_time-loop_start_time, self._duration))

        # Put results on queue
        self._response_queue.put((loop_start_time, loop_stop_time, wait, loop_average_time))

        if self._reset:
            module_logger.info("Resetting antenna position")
            _reset_rate = RESET_RATE
            _duration = _reset_rate * (self._degrees / 360)
            self.rotate(self._degrees*-1, _duration)

    @staticmethod
    def rotate(degrees, duration):
        """
        Rotate by degrees and duration

        :param degrees: Number of degrees to rotate
        :type degrees: int
        :param duration: Time to take for rotation
        :type duration: float
        :return: loop start time, loop end time, expected iteration time, measured iteration time
        :rtype: tuple
        """

        global degrees_per_microstep, output

        degrees_per_microstep = degrees_per_microstep
        pulses = round(degrees / degrees_per_microstep)
        wait = duration/abs(pulses)
        wait_half = wait/2

        if pulses < 0:
            output(DIR_min, 1)
            pulses = -pulses
        else:
            output(DIR_min, 0)

        # Optimization https://wiki.python.org/moin/PythonSpeed/PerformanceTips
        now = time.time
        sleep = time.sleep
        output = output

        loop_start_time = time.time()

        # Step through each step
        for step in range(0, pulses):
            # Calculate remaining time for current loop
            curr_loop = step*wait + loop_start_time

            output(PUL_min, 1)

            # Wait for half the remaining available time in the loop
            remaining = (curr_loop-now())-wait_half
            if remaining > 0:
                sleep(remaining)

            output(PUL_min, 0)

            # Wait remaining loop time, if any
            remaining = curr_loop - now()
            if remaining > 0:
                sleep(remaining)

        loop_stop_time = time.time()

        loop_average_time = (time.time() - loop_start_time) / pulses

        return loop_start_time, loop_stop_time, wait, loop_average_time

    @staticmethod
    def antenna_set_en(val):
        """
        Set the antenna enable pin
        :param val: Enable value to send
        :type val: bool
        """

        output(ENA_min, val)


@atexit.register
def cleanup_gpio():
    """
    Cleanup - ensure GPIO is cleaned up properly
    """

    module_logger.info("Cleaning up GPIO")
    cleanup()
