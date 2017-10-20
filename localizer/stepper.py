#import RPi.GPIO as GPIO
import time
import threading
import queue
from localizer import utils

# Default pinout for motor controller:
# [0] = enable_pin
# [1] = coil A1 (black wire)
# [2] = coil A2 (green wire)
# [3] = coil B1 (red wire)
# [4] = coil B2 (blue wire)
pins = [18, 4, 17, 23, 24]

lock = threading.Lock()


def move(delay, steps, step_distance = 1, stepper_steps = 400):
    """
    Send a command to the supplied stepper motor queue

    :param delay: The number of milliseconds between steps
    :param steps: The total number of steps to take
    :param step_distance: The distance of each step as a multiple of default stepper motor steps. May not be less than 1
    """

    if step_distance < 1:
        step_distance = 1

    return (delay, steps, step_distance)

def move_degree(rpm, degrees, step_degrees =360 / 400, stepper_steps = 400):
    """
    Send a command to the supplied stepper motor queue

    :param rpm: The speed of rotation
    :param degrees: The total number of degrees to rotate
    :param step_degrees: The degree of each step
    :param stepper_steps: The number of stepper motor steps per 360 degrees
    """

    delay = 60 / (int(rpm) * stepper_steps)
    steps = round(degrees / step_degrees)
    step_distance = round(step_degrees*stepper_steps/360)

    return move(delay, steps, step_distance)


class StepperThread(threading.Thread):
    def __init__(self, inbound_queue, outbound_queue, pins = pins):

        # Set up thread
        super(StepperThread, self).__init__()

        with lock:
            utils.log_message("Starting Stepper Thread")

        self.daemon = True
        self._inbound_queue = inbound_queue
        self._outbound_queue = outbound_queue
        self._pins = pins

        # Set up GPIO
        # GPIO.setmode(GPIO.BCM)
        # GPIO.setup(pins[0], GPIO.OUT)
        # GPIO.setup(pins[1], GPIO.OUT)
        # GPIO.setup(pins[2], GPIO.OUT)
        # GPIO.setup(pins[3], GPIO.OUT)
        # GPIO.setup(pins[4], GPIO.OUT)
        # GPIO.output(pins[0], 1)

        self._seq = [[1, 1, 0, 0],
                     [0, 1, 1, 0],
                     [0, 0, 1, 1],
                     [1, 0, 0, 1]]

        self._seq_position = 0

    def run(self):
        # Wait for commands in the queue
        while(True):
            # Execute command (delay, steps) tuple
            command = self._inbound_queue.get()
            delay = command[0]
            steps = command[1]
            step_distance = command[2]

            # Step through each step
            for step in range(steps):
                self._move(delay, step_distance)
                # Tell caller a step is finished
                response = (delay, step_distance)
                self._outbound_queue.join()
                self._outbound_queue.put(response)

            self._inbound_queue.task_done()

    def _move(self, delay, steps):
        """
        Move the stepper motor a fixed number of steps at a fixed speed.

        :param delay: time between steps in seconds
        :param steps: number of steps to take - pos value is cw, neg is ccw
        :return:
        """

        if steps < 0:
            direction = -1
            steps = -steps
        else:
            direction = 1

        for step in range(0, steps):
            # print("Setting coils to {}".format(seq[seq_position]))
            # GPIO.output(self.pins[1], self.seq[self.seq_position][0])
            # GPIO.output(self.pins[2], self.seq[self.seq_position][1])
            # GPIO.output(self.pins[3], self.seq[self.seq_position][2])
            # GPIO.output(self.pins[4], self.seq[self.seq_position][3])

            self._seq_position = (self._seq_position + direction) % 4
            time.sleep(delay)