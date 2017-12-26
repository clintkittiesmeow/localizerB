import numpy as np
import pandas as pd

def locate_random(series):
    return np.random.randint(-180,180)
    
    
def locate_naive(series):
    return series.idxmax()
        

def locate_interpolate(series, method, plot=False, test=None, bssid=None):
    series = series.reindex(np.arange(0,360))
    
    series_left = series.copy()
    series_left.index = np.arange(-360,0)
    
    series_right = series.copy()
    series_right.index = np.arange(360,720)
    
    series_inter = pd.concat([series_left, series, series_right]).interpolate(method=method)[np.arange(0,360)]
    
    guess = series_inter.idxmax()
    
    if plot:
        ax = series_inter.plot()
        series.plot(ax=ax, style='ro')
        import capmap
        bearing = capmap.get_bearing(test, bssid)
        ax.axvline(x=bearing, color='green')        
        ax.axvline(x=guess, color='orange')
    
    return guess

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