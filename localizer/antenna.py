import RPi.GPIO as GPIO
import time
import threading
import logging
import atexit
import queue
import localizer

GPIO.setwarnings(False)

module_logger = logging.getLogger('localizer.antenna')

class AntennaStepperThread(threading.Thread):
    # Default number of steps per radian
    steps_per_revolution = 400
    degrees_per_step = 360 / steps_per_revolution
    microsteps_per_step = 32
    degrees_per_microstep = degrees_per_step / microsteps_per_step

    def __init__(self, command_queue, response_queue, event_flag):

        # Set up thread
        super().__init__()

        module_logger.info("Starting Stepper Thread")

        self.daemon = True
        self._command_queue = command_queue
        self._response_queue = response_queue
        self._event_flag = event_flag
        self._seq_position = 0

        self.PUL_min = 21
        self.DIR_min = 20
        self.ENA_min = 16

        # Set up GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.PUL_min, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.DIR_min, GPIO.OUT)
        GPIO.setup(self.ENA_min, GPIO.OUT)

    def run(self):
        # Wait for commands in the queue
        module_logger.info("Executing Stepper Thread")
        while True:
            module_logger.info("Waiting for commands")
            # Execute command (duration, degrees, bearing) tuple
            duration, degrees, bearing = self._command_queue.get()
            degrees_per_microstep = AntennaStepperThread.degrees_per_microstep
            pulses = round(degrees / degrees_per_microstep)
            wait = duration/pulses
            wait_half = wait/2

            if pulses < 0:
                GPIO.output(self.DIR_min, GPIO.LOW)
                pulses = -pulses
            else:
                GPIO.output(self.DIR_min, GPIO.HIGH)

            GPIO.output(self.ENA_min, GPIO.HIGH)

            # Optimization https://wiki.python.org/moin/PythonSpeed/PerformanceTips
            now = time.time
            sleep = time.sleep
            output = GPIO.output

            # Wait for the synchronization flag
            self._event_flag.wait()

            curr_loop = 0
            remaining = 0
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

            module_logger.info("Rotated antenna {} degrees for {}s".format(degrees, duration))

            loop_stop_time = time.time()
            loop_average_time = (time.time() - loop_start_time) / pulses

            GPIO.output(self.ENA_min, GPIO.LOW)

            self._command_queue.task_done()

            # Tell caller a step is finished
            self._response_queue.put((loop_start_time, loop_stop_time, wait, loop_average_time))
            self._response_queue.join()

@atexit.register
def cleanup():
    """
    Cleanup - ensure GPIO is cleaned up properly
    """

    module_logger.info("Cleaning up GPIO")
    GPIO.cleanup()
