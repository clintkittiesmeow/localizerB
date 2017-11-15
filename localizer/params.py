import time
from distutils.util import strtobool

import localizer
from localizer.wifi import STD_BEACON_INT


class Params:

    VALID_PARAMS = ["iface", "duration", "degrees", "bearing", "hop_int", "test", "process"]

    def __init__(self,
                 iface=None,
                 duration=15,
                 degrees=360.0,
                 bearing=0.0,
                 hop_int=STD_BEACON_INT,
                 test=time.strftime('%Y%m%d-%H-%M-%S'),
                 process=False):

        # Default Values
        self._iface = iface
        self.duration = duration
        self.degrees = degrees
        self.bearing = bearing
        self.hop_int = hop_int
        self.test = test
        self.process = process

    @property
    def iface(self):
        return self._iface

    @iface.setter
    def iface(self, value):
        from localizer import wifi
        if value in list(wifi.get_interfaces()):
            self._iface = value
        else:
            raise ValueError("Invalid interface: {}".format(value))

    @property
    def duration(self):
        return self._duration

    @duration.setter
    def duration(self, value):
        try:
            if not isinstance(value, int):
                value = int(value)
            if value <= 0:
                raise ValueError()
            self._duration = value
        except ValueError:
            raise ValueError("Invalid duration: {}; should be an integer > 0".format(value))

    @property
    def degrees(self):
        return self._degrees

    @degrees.setter
    def degrees(self, value):
        try:
            if not isinstance(value, float):
                value = float(value)
            self._degrees = value
        except ValueError:
            raise ValueError("Invalid degrees: {}; should be a float".format(value))

    @property
    def bearing(self):
        return self._bearing

    @bearing.setter
    def bearing(self, value):
        try:
            if not isinstance(value, float):
                value = float(value)
            self._bearing = value % 360
        except ValueError:
            raise ValueError("Invalid bearing: {}; should be a float >= 0 and < 360".format(value))

    @property
    def hop_int(self):
        return self._hop_int

    @hop_int.setter
    def hop_int(self, value):
        try:
            if not isinstance(value, float):
                value = round(float(value), 5)
            if value <= 0:
                raise ValueError()
            self._hop_int = value
        except ValueError:
            raise ValueError("Invalid hop interval: {}; should be a float > 0".format(value))

    @property
    def test(self):
        return self._test

    @test.setter
    def test(self, value):
        self._test = str(value)

    @property
    def process(self):
        return self._process

    @process.setter
    def process(self, value):
        if isinstance(value, bool):
            self._process = value
        elif isinstance(value, str):
            self._process = strtobool(value)
        else:
            raise ValueError("Cannot parse '{}' as a bool".format(str(value)))

    # Validation functions
    def validate_antenna(self):
        return self.duration is not None and \
               self.degrees is not None and \
               self.bearing is not None

    def validate_gps(self):
        return self.duration is not None

    def validate_capture(self):
        return self.iface is not None and \
               self.duration is not None
    def validate_wifi(self):
        return self.iface is not None and \
               self.duration is not None and \
               self.hop_int is not None

    def validate(self):
        return self.validate_antenna() and self.validate_gps() and self.validate_wifi()

    def __str__(self):
        retstr = "\n{} \tParameters: {}\n".format(localizer.G, localizer.W)
        for param, val in sorted(self.__dict__.items()):

            # Highlight 'None' values as red, except for 'test' which is optional
            signifier = ''
            if param is not '_test' and val is None:
                signifier = localizer.R
            retstr += "\t    {:<15}{}{:<15}{}\n".format(str(param[1:]) + ': ', signifier, str(val), localizer.W)

        return retstr
