import datetime
import time

from geomag import WorldMagneticModel

import localizer
from localizer.wifi import OPTIMAL_BEACON_INT, STD_CHANNEL_DISTANCE


class Params:

    VALID_PARAMS = ["iface", "duration", "degrees", "bearing", "hop_int", "hop_dist", "test", "process"]

    def __init__(self,
                 iface=None,
                 duration=15,
                 degrees=360.0,
                 bearing=0.0,
                 hop_int=OPTIMAL_BEACON_INT,
                 hop_dist=STD_CHANNEL_DISTANCE,
                 test=time.strftime('%Y%m%d-%H-%M-%S')):

        # Default Values
        self._duration = self._degrees = self._bearing = self._hop_int = self._hop_dist = self._test = None
        self._iface = iface
        self.duration = duration
        self.degrees = degrees
        self.bearing_magnetic = bearing
        self.hop_int = hop_int
        self.hop_dist = hop_dist
        self.test = test

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
    def bearing_magnetic(self):
        return self._bearing

    @bearing_magnetic.setter
    def bearing_magnetic(self, value):
        try:
            if not isinstance(value, float):
                value = float(value)
            self._bearing = value % 360
        except ValueError:
            raise ValueError("Invalid bearing: {}; should be a float >= 0 and < 360".format(value))

    def bearing_true(self, lat, lon, alt=0, date=datetime.date.today()):
        wmm = WorldMagneticModel()
        declination = wmm.calc_mag_field(lat, lon, alt, date).declination
        return self._bearing + declination

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
    def hop_dist(self):
        return self._hop_dist

    @hop_dist.setter
    def hop_dist(self, value):
        try:
            if not isinstance(value, int):
                value = int(value)
            if value <= 0:
                raise ValueError()
            self._hop_dist = value
        except ValueError:
            raise ValueError("Invalid hop distance: {}; should be an integer > 0".format(value))

    @property
    def test(self):
        return self._test

    @test.setter
    def test(self, value):
        self._test = str(value)

    # Validation functions
    def validate_antenna(self):
        return self.duration is not None and \
               self.degrees is not None and \
               self.bearing_magnetic is not None

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
