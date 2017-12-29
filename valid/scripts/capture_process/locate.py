import numpy as np
import pandas as pd

def locate_random(series):
    return np.random.randint(-180,180)
    
    
def locate_naive(series):
    if len(series) > 360:
        series = series[np.arange(0,360)]
        
    return series.idxmax()
        

def locate_interpolate(series_concat, method, plot=False, test=None, bssid=None):
    series_inter = series_concat.interpolate(method=method)[np.arange(0,360)]
    
    guess = series_inter.idxmax()
    
    if plot:
        ax = series_inter.plot()
        series_mid = series_concat[np.arange(0,360)]
        series_mid.plot(ax=ax, style='ro')
        import capmap
        bearing = capmap.get_bearing(test, bssid)      
        ax.axvline(x=guess, color='orange')
        ax.axvline(x=bearing, color='green')
        naive = locate_naive(series_mid)
        ax.axvline(x=naive, color='purple')
        print(f"Guess: {guess}, Naive: {naive}, True: {bearing}")
    
    return guess


def locate_method_helper(method, series_list):
    _results = []
    for param in series_list:
        series = param[-1]
        bearing = param[-2]
        try:
            _guess = error_methods[method](series)
        except ValueError:
            _fallback_method = 'naive'
            param[-3] = method
            _guess = error_methods[_fallback_method](series)
        finally:
            _error = (_guess - bearing)%360
            # Reflect modular distance - as error gets larger than 180, it's actually getting closer to truth
            if np.abs(_error) > 180:
                _error = -((360 - _error) % 360)
            _results.append(param[:-2] + [method, _error])
    
    return _results


error_methods = {
    'naive': locate_naive, 
    'quadratic': lambda series: locate_interpolate(series, 'quadratic'), 
    'cubic': lambda series: locate_interpolate(series, 'cubic'),
    'linear': lambda series: locate_interpolate(series, 'linear'),
    'slinear': lambda series: locate_interpolate(series, 'slinear'),
    'barycentric': lambda series: locate_interpolate(series, 'barycentric'),
    'krogh': lambda series: locate_interpolate(series, 'krogh'),
    'piecewise_polynomial': lambda series: locate_interpolate(series, 'piecewise_polynomial'),
    'from_derivatives': lambda series: locate_interpolate(series, 'from_derivatives'),
    'pchip': lambda series: locate_interpolate(series, 'pchip'),
    'akima': lambda series: locate_interpolate(series, 'akima'),
    'random': lambda series: locate_random(series)
}

