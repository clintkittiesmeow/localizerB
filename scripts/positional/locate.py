import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter
import bearing_error

def locate_method_helper(method, smooth, series_list):
    _results = []
    for param in series_list:
        series = param[-1]
        bearing = param[-2]
        try:
            _guess = interpolate(series, method, smooth).idxmax()
        except ValueError:
            _fallback_method = 'Naive'
            param[-3] = method # Set fallback to failed method
            _guess = interpolate(series, _fallback_method, smooth).idxmax()
        finally:
            _error = (bearing - _guess)%360
            # Reflect modular distance - as error gets larger than 180, it's actually getting closer to truth
            if np.abs(_error) > 180:
                _error = -((360 - _error) % 360)
            _results.append(param[:-2] + [method, smooth, bearing, _guess, _error])
    
    return _results


# Smoothing Methods

def moving_average(series, n=21):
    # https://stackoverflow.com/a/14314054/1486966
    ret = np.cumsum(series.values)
    ret[n:] = ret[n:] - ret[:-n]
    return pd.Series(ret[n - 1:] / n)

def savinsky_golay(series, n=21, p=3):
    return savgol_filter

smoothing_methods = {
    'moving_average': moving_average,
    'savinsky_golay': lambda series: pd.Series(savgol_filter(series.values, 91, 1)),
}

# Interpolation Methods      

def interpolate(series_concat, method, smooth=None):
    method = error_methods[method]
    if method == 'random':
        series = pd.Series(np.random.randn(1,360).ravel())
    elif method == 'naive':
        series = series_concat.fillna(0)
    else:
        series = series_concat.interpolate(method=method)
    
    if smooth:
        series = smoothing_methods[smooth](localization_error.series_expand(series[np.arange(0,360)]))
    
    return series[np.arange(0,360)]

error_methods = {
    'Naive':'naive',
    'Quadratic':'quadratic',
    'Cubic':'cubic',
    'Linear':'linear',
    'SLinear':'slinear',
    'Barycentric':'barycentric',
    'Krogh':'krogh',
    'BPoly':'from_derivatives',
    'PCHIP':'pchip',
    'Akima':'akima',
    'Random':'random'
}
