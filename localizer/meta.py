import datetime
import re
import time

#CB from geomag import WorldMagneticModel
import geomag

import localizer

# WIFI Constants
IEEE80211bg = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
IEEE80211bg_intl = IEEE80211bg + [12, 13, 14]
IEEE80211a = [36, 40, 44, 48, 52, 56, 60, 64, 149, 153, 157, 161]
IEEE80211bga = IEEE80211bg + IEEE80211a
IEEE80211bga_intl = IEEE80211bg_intl + IEEE80211a
TU = 1024/1000000  # 1 TU = 1024 usec https://en.wikipedia.org/wiki/TU_(Time_Unit)
STD_BEACON_INT = 100*TU
OPTIMAL_BEACON_INT = 179*TU
STD_CHANNEL_DISTANCE = 2


meta_csv_fieldnames = ['name',
                       'pass',
                       'path',
                       'iface',
                       'duration',
                       'hop_int',
                       'pos_lat',
                       'pos_lon',
                       'pos_alt',
                       'pos_lat_err',
                       'pos_lon_err',
                       'pos_alt_err',
                       'start',
                       'end',
                       'degrees',
                       'bearing',
                       'pcap',
                       'nmea',
                       'coords',
                       'focused',
                       'guess',
                       'elapsed',
                       'num_guesses',
                       'guess_time',
                       ]


required_suffixes = {"nmea": ".nmea",
                    "pcap": ".pcapng",
                    "meta": "-capture.csv",
                    "coords": "-gps.csv",
                     }


capture_suffixes = {
                    "guess": "-guess.csv",
                    "results": "-results.csv",
                    "capture": "-capture.conf",
                    }

capture_suffixes.update(required_suffixes)


class Params:

    VALID_PARAMS = ["iface",
                    "duration",
                    "degrees",
                    "bearing",
                    "hop_int",
                    "hop_dist",
                    "mac",
                    "macs",
                    "channel",
                    "focused",
                    "capture"]

    def __init__(self,
                 iface=None,
                 duration=15.0,
                 degrees=360,
                 bearing=0,
                 hop_int=OPTIMAL_BEACON_INT,
                 hop_dist=STD_CHANNEL_DISTANCE,
                 macs=None,
                 channel=None,
                 focused=None,
                 capture=time.strftime('%Y%m%d-%H-%M-%S')):

        # Default Values
        self._duration = self._degrees = self._bearing = self._hop_int = self._hop_dist = self._macs = self._channel = self._focused = self._capture = None
        self._iface = iface
        self.duration = duration
        self.degrees = degrees
        self.bearing_magnetic = bearing
        self.hop_int = hop_int
        self.hop_dist = hop_dist
        self.macs = macs
        self.channel = channel
        self.focused = focused
        self.capture = capture

    @property
    def iface(self):
        return self._iface

    @iface.setter
    def iface(self, value):
        from localizer import interface
        if value in list(interface.get_interfaces()):
            self._iface = value
        else:
            raise ValueError("Invalid interface: {}".format(value))

    @property
    def duration(self):
        return self._duration

    @duration.setter
    def duration(self, value):
        try:
            if not isinstance(value, float):
                value = float(value)
            if value < 0:
                raise ValueError()
            self._duration = value
        except ValueError:
            raise ValueError("Invalid duration: {}; should be a float >= 0".format(value))

    @property
    def degrees(self):
        return self._degrees

    @degrees.setter
    def degrees(self, value):
        try:
            if not isinstance(value, int):
                value = int(float(value))
            self._degrees = value
        except ValueError as e:
            raise ValueError("Invalid degrees: {}; should be an int".format(value))

    @property
    def bearing_magnetic(self):
        return self._bearing

    @bearing_magnetic.setter
    def bearing_magnetic(self, value):
        try:
            if not isinstance(value, int):
                value = int(float(value))
            self._bearing = value % 360
        except ValueError:
            raise ValueError("Invalid bearing: {}; should be an int".format(value))

    def bearing_true(self, lat, lon, alt=0, date=datetime.date.today()):
        #CB wmm = WorldMagneticModel()
        #CB declination = wmm.calc_mag_field(lat, lon, alt, date).declination
        declination = geomag.declination(lat, lon) #CB
        return self._bearing + declination

    @property
    def hop_int(self):
        return self._hop_int

    @hop_int.setter
    def hop_int(self, value):
        try:
            if not isinstance(value, float):
                value = round(float(value), 5)
            if value < 0:
                raise ValueError()
            self._hop_int = value
        except ValueError:
            raise ValueError("Invalid hop interval: {}; should be a float >= 0".format(value))

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
    def macs(self):
        return self._macs

    @macs.setter
    def macs(self, value):
        self._macs = []
        if value:
            self.add_mac(value)

    def add_mac(self, value):
        try:
            # Check for string
            if isinstance(value, str):
                if self.validate_mac(value):
                    self._macs.append(value)
                else:
                    raise ValueError
            else:
                # Try to treat value as an iterable
                for mac in value:
                    if self.validate_mac(mac):
                        self._macs.append(mac)
                    else:
                        raise ValueError

        except (ValueError, TypeError):
            raise ValueError("Invalid mac address or list supplied; should be a mac string or list of mac strings")

    @property
    def channel(self):
        return self._channel

    @channel.setter
    def channel(self, value):
        try:
            if value is None:
                self._channel = value
            else:
                if not isinstance(value, int):
                    value = int(value)
                if value <= 0:
                    raise ValueError()
                self._channel = value
        except ValueError:
            raise ValueError("Invalid channel: {}; should be an integer > 0".format(value))

    @property
    def focused(self):
        return self._focused

    @focused.setter
    def focused(self, value):
        try:
            if value is None:
                self._focused = value
            else:
                if not isinstance(value, tuple) or len(value) != 2:
                    raise ValueError()
                else:
                    _degrees = float(value[0])
                    if _degrees <= 0 or _degrees > 360:
                        raise ValueError()
                    _duration = float(value[1])
                    if _duration <= 0:
                        raise ValueError()

                    self._focused = (_degrees, _duration)
        except ValueError:
            raise ValueError("Invalid fine: {}; should be a tuple of length 2 (degrees[width], duration > 0)".format(value))

    @property
    def capture(self):
        return self._capture

    @capture.setter
    def capture(self, value):
        self._capture = str(value)

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

    @staticmethod
    def validate_mac(mac):
        return re.match("[0-9a-f]{2}([-:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", mac.lower())

    def validate(self):
        return self.validate_antenna() and self.validate_gps() and self.validate_wifi()

    def __str__(self):
        retstr = "\n{} \tParameters: {}\n".format(localizer.G, localizer.W)
        for param, val in sorted(self.__dict__.items()):

            # If no macs are specified, don't print
            if param is '_macs':
                if len(val) > 0:
                    retstr += "\t    Macs:\n"
                    for i, mac in enumerate(val):
                        retstr += "\t\t    {:<15}{:<15}\n".format(i, mac)
            else:
                # Highlight 'None' values as red, except for 'test' which is optional
                signifier = ''
                if param is not '_capture' and val is None:
                    signifier = localizer.R
                retstr += "\t    {:<15}{}{:<15}{}\n".format(str(param[1:]) + ': ', signifier, str(val), localizer.W)

        return retstr

    def copy(self):
        from copy import deepcopy

        return Params(
            self.iface,
            self.duration,
            self.degrees,
            self.bearing_magnetic,
            self.hop_int,
            self.hop_dist,
            deepcopy(self.macs),
            self.channel,
            deepcopy(self.focused),
            self.capture
        )
