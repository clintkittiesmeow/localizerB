import atexit
import logging
import threading
import time

import RPi.GPIO as GPIO

import localizer

# Set up GPIO
PUL_min = 21
DIR_min = 20
ENA_min = 16
GPIO.setmode(GPIO.BCM)
GPIO.setup(PUL_min, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(DIR_min, GPIO.OUT)
GPIO.setup(ENA_min, GPIO.OUT)
GPIO.output(ENA_min, GPIO.HIGH)
GPIO.setwarnings(False)


module_logger = logging.getLogger('localizer.antenna')


# Optimization https://wiki.python.org/moin/PythonSpeed/PerformanceTips
now = time.time
sleep = time.sleep
output = GPIO.output


class AntennaStepperThread(threading.Thread):
    # Default number of steps per radian
    steps_per_revolution = 400
    degrees_per_step = 360 / steps_per_revolution
    microsteps_per_step = 32
    degrees_per_microstep = degrees_per_step / microsteps_per_step

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
            _reset_rate = 3
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
        degrees_per_microstep = AntennaStepperThread.degrees_per_microstep
        pulses = round(degrees / degrees_per_microstep)
        if pulses < 0:
            GPIO.output(DIR_min, GPIO.LOW)
            pulses = -pulses
        else:
            GPIO.output(DIR_min, GPIO.HIGH)
        wait = duration/pulses
        wait_half = wait/2

        loop_start_time = time.time()

        # Step through each step
        for step in range(0, pulses):
            # Calculate remaining time for current loop
            curr_loop = step*wait + loop_start_time

            output(21, 1)

            # Wait for half the remaining available time in the loop
            remaining = (curr_loop-now())-wait_half
            if remaining > 0:
                sleep(remaining)

            output(21, 0)

            # Wait remaining loop time, if any
            remaining = curr_loop - now()
            if remaining > 0:
                sleep(remaining)

        loop_stop_time = time.time()

        loop_average_time = (time.time() - loop_start_time) / pulses

        localizer.params.bearing += degrees

        return loop_start_time, loop_stop_time, wait, loop_average_time


@atexit.register
def cleanup():
    """
    Cleanup - ensure GPIO is cleaned up properly
    """

    module_logger.info("Cleaning up GPIO")
    GPIO.cleanup()
