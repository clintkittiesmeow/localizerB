import unittest
from unittest import TestCase

from localizer.params import Params


class TestParams(TestCase):

    def test_exceptions(self):
        params = Params()
        with self.assertRaises(ValueError):
            params.iface = "no-adapter"
        with self.assertRaises(ValueError):
            params.duration = "goat"
        with self.assertRaises(ValueError):
            params.degrees = "cheese"
        with self.assertRaises(ValueError):
            params.bearing = "curds"
        with self.assertRaises(ValueError):
            params.hop_int = "hot"
        with self.assertRaises(ValueError):
            params.path = "%$#)$"
        with self.assertRaises(ValueError):
            params.path = None
        with self.assertRaises(ValueError):
            params.path = 123456
        with self.assertRaises(ValueError):
            params.process = "Nuttin"

        params.bearing = -1000
        self.assertGreaterEqual(params.bearing, 0)
        self.assertLess(params.bearing, 360)

        params.bearing = 495
        self.assertGreaterEqual(params.bearing, 0)
        self.assertLess(params.bearing, 360)


if __name__ == '__main__':
    unittest.main()
