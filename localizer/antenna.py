import atexit
import logging
import math
import threading
import time
from subprocess import run

import pigpio

module_logger = logging.getLogger(__name__)

# Always start due north (magnetic) or change this variable
bearing_default = 0
bearing_current = bearing_default
bearing_max = 720
bearing_min = -360

# Constants
# Reset Rate Curve
# From utils/model.py
#   x = [0,90,180,360]
#   y = [20,10,8,6]
get_reset_rate = lambda x: 3.235294 + (20 - 3.235294) / (1 + (x / 34.68111) ** 1.29956)
RESET_RATE = [get_reset_rate(x) for x in range(1080)]
get_focused_rate = lambda x: -4 + (20 + 4) / (1 + (x / 180) ** 0.48542683)
FOCUSED_RATE = [get_focused_rate(x) for x in range(360)]

# Default number of steps per radian
steps_per_revolution = 200
degrees_per_step = 360 / steps_per_revolution
microsteps_per_step = 32
microsteps_per_revolution = steps_per_revolution*microsteps_per_step*2
degrees_per_microstep = degrees_per_step / microsteps_per_step
# Set up GPIO
PUL_min = 18
DIR_min = 23
ENA_min = 24


# PIGPIOD bootstrap
# Try to start pigpiod locally
try:
    run(['pigpiod'], timeout=3)
    pi = pigpio.pi()
except FileNotFoundError:
    # pigpiod is not installed on this system, try connecting to remote instance
    pi = pigpio.pi('192.168.137.61', 8888)

if not pi.connected:
    raise Exception("Need to have pigpiod running")

pi.set_mode(PUL_min, pigpio.OUTPUT)
pi.write(PUL_min, pigpio.LOW)
pi.set_mode(DIR_min, pigpio.OUTPUT)
pi.set_mode(ENA_min, pigpio.OUTPUT)
pi.write(ENA_min, pigpio.HIGH)


class AntennaThread(threading.Thread):

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
        AntennaThread.reset_antenna(self._bearing, self._degrees)

        # Indicate readiness
        self._response_queue.put('r')

        # Wait for the synchronization flag
        module_logger.info("Waiting for synchronization flag")
        self._event_flag.wait()

        _start_time, _stop_time = self.rotate(self._degrees, self._duration)
        bearing_current += self._degrees

        module_logger.info("Rotated antenna {} degrees for {:.2f}s"
                           .format(self._degrees, _stop_time - _start_time))

        # Put results on queue
        self._response_queue.put((_start_time, _stop_time))

        # Pause for a moment to reduce drift
        time.sleep(.5)

        if self._reset is not None:
            # Reset antenna for next test, assuming next test has same width as current
            AntennaThread.reset_antenna(self._reset, self._degrees)

    @staticmethod
    def reset_antenna(bearing=bearing_default, degrees=0):
        global bearing_current

        _travel = AntennaThread.determine_best_path(bearing, degrees)

        # Check to see if new bearing is within 0.1
        if not math.isclose(bearing_current, bearing, abs_tol=0.1) and _travel != 0:
            _travel_duration = RESET_RATE[abs(_travel)]
            module_logger.info(
                "Resetting antenna {} degrees (from {} to {})".format(_travel, bearing_current, bearing_current + _travel))
            AntennaThread.rotate(_travel, _travel_duration)
            bearing_current += _travel
            return True

        return False

    @staticmethod
    def determine_best_path(new_bearing, degrees):
        """
        Return an optimized path to arrive at the provided bearing based on how far the travel is and the current state
        of the antenna.

        :param new_bearing: New bearing to set the antenna to
        :param degrees: How far will the antenna be traveling from this bearing
        :return: An optimized (equivalent) bearing to set the antenna
        """

        global bearing_current


        _edge_case = bool(new_bearing == bearing_current % 360)
        if _edge_case and (bearing_current >= bearing_max or bearing_current <= bearing_min):
            _travel = new_bearing - bearing_current
        else:
            # Use algorithm tested and optimized in tests/antenna_motion.py
            _travel = 180 - (540 + (bearing_current - new_bearing)) % 360
            _proposed_new_bearing = bearing_current + _travel
            if _proposed_new_bearing + degrees >= bearing_max:
                _travel = _travel - 360
            elif _proposed_new_bearing <= bearing_min:
                _travel = 360 - _travel

        return _travel

    @staticmethod
    def rotate(degrees, duration):
        """
        Rotate by degrees and duration

        :param degrees: Number of degrees to rotate
        :type degrees: int
        :param duration: Time to take for rotation for 360 degrees
        :type duration: float
        :return: start, end
        :rtype: tuple
        """

        pi.wave_clear()

        if degrees < 0:
            pi.write(DIR_min, 1)
            degrees = - degrees
        else:
            pi.write(DIR_min, 0)

        _frequency = microsteps_per_revolution/duration

        if degrees > 6:
            _ramp1 = 1  # degrees
            _ramp1_frequency = _frequency / 4
            _ramp1_pulses = round(_ramp1 / degrees_per_microstep)

            _ramp2 = 1  # degrees
            _ramp2_frequency = _frequency / 2
            _ramp2_pulses = round(_ramp2 / degrees_per_microstep)

            _ramp3 = 1  # degrees
            _ramp3_frequency = 3 * _frequency / 4
            _ramp3_pulses = round(_ramp3 / degrees_per_microstep)

            _pulses = round((degrees - 2*(_ramp1 + _ramp2 + _ramp3)) / degrees_per_microstep)

            _ramp = [[_ramp1_frequency, _ramp1_pulses],
                     [_ramp2_frequency, _ramp2_pulses],
                     [_ramp3_frequency, _ramp3_pulses],
                     [_frequency, _pulses],
                     [_ramp3_frequency, _ramp3_pulses],
                     [_ramp2_frequency, _ramp2_pulses],
                     [_ramp1_frequency, _ramp1_pulses]]

        else:
            _pulses = round(degrees/degrees)
            _ramp = [[_frequency/3, _pulses]]

        _duration = 0
        for r in _ramp:
            assert r[0] > 0, "degrees: {}, duration: {}, ramp freq: {}".format(degrees, duration, r[0])
            assert r[1] > 0, "degrees: {}, duration: {}, ramp pulses: {}".format(degrees, duration, r[0])
            _duration += int(1000000 / r[0]) * r[1]

        _duration *= 2
        _duration /= 1000000

        _chain, _wid = AntennaThread.generate_ramp(_ramp)

        _time_start = time.time()
        pi.wave_chain(_chain)
        _time_end = _time_start + _duration

        while time.time() < _time_end:
            time.sleep(.1)

        try:
            for wid in _wid:
                if wid:
                    pi.wave_delete(wid)
        except pigpio.error as e:
            module_logger.error(e)

        return _time_start, _time_end

    @staticmethod
    def antenna_set_en(val):
        """
        Set the antenna enable pin
        :param val: Enable value to send
        :type val: bool
        """

        pi.write(ENA_min, val)

    @staticmethod
    def generate_ramp(ramp):
        """Generate ramp wave forms.
        ramp:  List of [Frequency, Steps]
        """
        pi.wave_clear()  # clear existing waves
        length = len(ramp)  # number of ramp levels
        wid = [-1] * length

        # Generate a wave per ramp level
        for i in range(length):
            frequency = ramp[i][0]
            micros = int(1000000 / frequency)
            wf1 = pigpio.pulse(1 << PUL_min, 0, micros)  # pulse on
            wf2 = pigpio.pulse(0, 1 << PUL_min, micros)  # pulse off
            wf = [wf1, wf2]
            pi.wave_add_generic(wf)
            wid[i] = pi.wave_create()

        # Generate a chain of waves
        chain = []
        for i in range(length):
            steps = ramp[i][1]
            x = steps & 255
            y = steps >> 8
            chain += [255, 0, wid[i], 255, 1, x, y]

        return chain, wid  # Return chain.


@atexit.register
def cleanup_gpio():
    """
    Cleanup - ensure GPIO is cleaned up properly
    """

    module_logger.info("Cleaning up GPIO")
    pi.wave_clear()
