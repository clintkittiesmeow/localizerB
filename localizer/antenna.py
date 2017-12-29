import atexit
import logging
import math
import threading
import time

module_logger = logging.getLogger(__name__)

# Always start due north (magnetic) or change this variable
bearing_default = 0
bearing_current = bearing_default
bearing_max = 360
bearing_min = -360

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

    def __init__(self, response_queue, event_flag, duration, degrees, bearing, reset=None):

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
        global bearing_current

        module_logger.info("Executing Stepper Thread")

        # Point the antenna in the right direction
        AntennaStepperThread.reset_antenna(self._bearing)

        # Indicate readiness
        self._response_queue.put('r')

        # Wait for the synchronization flag
        module_logger.info("Waiting for synchronization flag")
        self._event_flag.wait()

        loop_start_time, loop_stop_time, wait, loop_average_time = self.rotate(self._degrees, self._duration)
        bearing_current += self._degrees

        module_logger.info("Rotated antenna {} degrees for {:.2f}s (expected {}s)"
                           .format(self._degrees, loop_stop_time - loop_start_time, self._duration))

        # Put results on queue
        self._response_queue.put((loop_start_time, loop_stop_time, wait, loop_average_time))

        # Pause for a moment to reduce drift
        time.sleep(.5)

        if self._reset is not None:
            AntennaStepperThread.reset_antenna(self._reset)


    @staticmethod
    def reset_antenna(bearing=bearing_default):
        global bearing_current

        _travel = AntennaStepperThread.determine_best_path(bearing)

        # Check to see if new bearing is within 0.1
        if not math.isclose(bearing_current, bearing, abs_tol=0.1) and _travel != 0:
            _travel_duration = abs(_travel) * RESET_RATE / 360
            module_logger.info(
                "Resetting antenna {} degrees (from {} to {})".format(_travel, bearing_current, bearing))
            AntennaStepperThread.rotate(_travel, _travel_duration)
            bearing_current += _travel
            return True

        return False


    @staticmethod
    def determine_best_path(new_bearing):
        global bearing_current

        _edge_case = bool(new_bearing == bearing_current % 360)
        if _edge_case and (bearing_current >= bearing_max or bearing_current <= bearing_min):
            _travel = new_bearing - bearing_current
        else:
            # Use algorithm tested and optimized in tests/antenna_motion.py
            _travel = 180 - (540 + (bearing_current - new_bearing)) % 360
            _proposed_new_bearing = bearing_current + _travel
            if _proposed_new_bearing > bearing_max:
                _travel = _travel - 360
            elif _proposed_new_bearing < bearing_min:
                _travel = 360 - _travel

        return _travel


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
