import numpy as np
import pandas as pd

def locate_naive(series):
    if len(series) > 360:
        series = series[np.arange(0,360)]
        
    return series.idxmax()
      

def locate_interpolate(series_concat, method, plot=False, test=None, bssid=None):
    series_inter = series_concat.interpolate(method=method)
    
    guess = series_inter.idxmax()
    
    if plot:
        ax = series_inter.plot()
        series_mid = series_concat[np.arange(0,360)]
        series_mid.plot(ax=ax, style='ro')
        import capmap
        bearing = capmap.get_bearing(test, bssid)      
        ax.axvline(x=guess, color='orange')
        ax.axvline(x=bearing, color='green')
        print(f"Guess: {guess}, True: {bearing}")
    
    return guess


def locate_method_helper(method, width, series_list):
    _results = []
    for params in series_list:
        series = params[-1]
        bearing = params[-2]
        guess_orig = params[3]
        center = 180
        offset = center - guess_orig
        
        # set index
        series.index = (series.index + offset) % 360
        series.sort_index(inplace=True)
        left = center + width[0]
        right = center + width[1]
        series_narrow = series[np.arange(left,right)]
        if len(series_narrow.dropna()) == 1:
            _guess = locate_naive(series_narrow) - offset
        elif len(series_narrow.dropna()>1):
            _guess = locate_interpolate(series_narrow, method) - offset
        else:
            # maximum error if there are no beacons captured - penalize too-narrow
            _guess = 180 + bearing
                 
        _error = (_guess - bearing)%360
        # Reflect modular distance - as error gets larger than 180, it's actually getting closer to truth
        if np.abs(_error) > 180:
            _error = -((360 - _error) % 360)
        _results.append(params[:-2] + [width, _error])
    
    return _results
