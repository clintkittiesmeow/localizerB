# import RPi.GPIO as GPIO
import time
import threading
import logging


# def move(delay, steps, step_distance = 1, stepper_steps = 400):
#     """
#     Send a command to the supplied stepper motor queue
#
#     :param delay: The number of milliseconds between steps
#     :param steps: The total number of steps to take
#     :param step_distance: The distance of each step as a multiple of default stepper motor steps.
#     """
#
#     if step_distance < 1:
#         step_distance = 1
#
#     return delay, steps, step_distance
#
#
# def move_degree(rpm, degrees, step_degrees=360 / 400, stepper_steps=400):
#     """
#     Send a command to the supplied stepper motor queue
#
#     :param rpm: The speed of rotation
#     :param degrees: The total number of degrees to rotate
#     :param step_degrees: The degree of each step
#     :param stepper_steps: The number of stepper motor steps per 360 degrees
#     """
#
#     delay = 60 / (int(rpm) * stepper_steps)
#     steps = round(degrees / step_degrees)
#     step_distance = round(step_degrees*stepper_steps/360)
#
#     return move(delay, steps, step_distance)


class AntennaStepperThread(threading.Thread):

    # Default pinout for motor controller:
    # [0] = enable_pin
    # [1] = coil A1 (black wire)
    # [2] = coil A2 (green wire)
    # [3] = coil B1 (red wire)
    # [4] = coil B2 (blue wire)
    pins = [18, 4, 17, 23, 24]

    seq = [[1, 1, 0, 0],
           [0, 1, 1, 0],
           [0, 0, 1, 1],
           [1, 0, 0, 1]]

    # Default number of steps per radian
    radian_steps = 400
    degrees_per_step = 360/radian_steps

    # Set up GPIO
    # GPIO.setmode(GPIO.BCM)
    # GPIO.setup(pins[0], GPIO.OUT)
    # GPIO.setup(pins[1], GPIO.OUT)
    # GPIO.setup(pins[2], GPIO.OUT)
    # GPIO.setup(pins[3], GPIO.OUT)
    # GPIO.setup(pins[4], GPIO.OUT)
    # GPIO.output(pins[0], 1)

    def __init__(self, command_queue, response_queue, event_flag):

        # Set up thread
        super().__init__()

        logging.getLogger('global').info("Starting Stepper Thread")

        self.daemon = True
        self._command_queue = command_queue
        self._response_queue = response_queue
        self._event_flag = event_flag
        self._seq_position = 0

    def run(self):
        # Wait for commands in the queue
        while True:
            # Execute command (duration, degrees, bearing) tuple
            duration, degrees, bearing = self._command_queue.get()

            steps = round(degrees / AntennaStepperThread.degrees_per_step)
            wait = duration/steps

            bearing_table = {}

            if steps < 0:
                direction = -1
                steps = -steps
            else:
                direction = 1

            # Wait for the synchronization flag
            self._event_flag.wait()

            # Step through each step
            for step in range(0, steps):
                # GPIO.output(self.pins[1], self.seq[self._seq_position][0])
                # GPIO.output(self.pins[2], self.seq[self._seq_position][1])
                # GPIO.output(self.pins[3], self.seq[self._seq_position][2])
                # GPIO.output(self.pins[4], self.seq[self._seq_position][3])

                self._seq_position = (self._seq_position + direction) % 4
                bearing_table[time.time()] = bearing
                bearing += AntennaStepperThread.degrees_per_step
                time.sleep(wait)

            self._command_queue.task_done()

            # Tell caller a step is finished
            self._response_queue.put(bearing_table)
            self._response_queue.join()
