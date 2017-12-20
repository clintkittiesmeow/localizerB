# -*- coding: utf-8 -*-
"""
Created on Thu Dec  7 16:25:58 2017

@author: blaw
"""


import pandas as pd
import numpy as np
import os
import gps
import aps
import matplotlib.pyplot as plt
from multiprocessing import Pool
from tqdm import tqdm, tnrange, tqdm_notebook

def setup(directory):
    global dataframe, tests, access_points, bearings
    dataframe = import_captures(directory)   
    tests = get_test_gps(dataframe, directory)
    access_points = aps.import_aps('../aps.csv')
    bearings = load_bearings()
    return dataframe


def import_captures(directory):
    dataframes = []    
    
    # Walk through each subdirectory of working directory
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith("-results.csv"):
                dataframes.append(pd.read_csv(os.path.join(root,file),sep=','))
                
    df = pd.concat(dataframes, axis=0)
    df.loc[:,'mw'] = dbm_to_mw(df['ssi'])
    return df
    
    
def get_test_gps(dataframe, directory):
    tests = pd.unique(dataframe["test"])
    results = {'test':[], 'lat':[], 'lon':[]}
    for test in tests:
        coord, _ = gps.process_directory(os.path.join(directory, test))
        results['test'].append(test)
        results['lat'].append(coord[0])
        results['lon'].append(coord[1])
    return pd.DataFrame(results)



def error(method='naive'):
    # Loop through each test/pass and determine the bearing based on maximum mw
    # Return the error rate as the squared degrees from the correct bearing
    
    global bearings, dataframe, error_methods
    
    if method not in error_methods:
        print(f"You did not specify a valid method. Available methods: {_methods}")
    
    _columns = ['test', 'pass', 'bssid', 'error', 'fallbacks']
    _rows = []
    
    _tests = pd.unique(bearings['test'])
    
    for test in tqdm_notebook(_tests, desc="Tests", leave=False):
        _bssids = pd.unique(bearings['bssid'])
        for bssid in _bssids:
            _df = dataframe[(dataframe.test == test) & (dataframe.bssid == bssid)]
            _passes = pd.unique(_df['pass'])
            for i in _passes:
                _fallbacks = 0
                _pass = _df[_df['pass'] == i].filter(['mw', 'bearing_true'])
                _pass = _pass.rename(columns={'bearing_true': 'deg'}).sort_values('deg')
                _pass['deg'] = np.round(_pass['deg'])
                _pass = _pass.set_index('deg').iloc[:,0]
                _true_bearing = bearings[(bearings['test'] == test) & (bearings['bssid'] == bssid)]['bearing'].values[0]
                
                try:
                    _location = error_methods[method](_pass)
                except ValueError as e:
                    # print(f"Error: couldn't use {method} method, falling back to naive; {e}")
                    _location = error_methods['naive'](_pass)
                    _fallbacks += 1
                    
                _error = np.abs(_location-_true_bearing)
                # Reflect modular distance - as error gets larger than 180, it's actually getting closer to truth
                if np.abs(_error) > 180:
                    _error = 360 - _error
                _rows.append([test, i, bssid, _error, _fallbacks])
        
    return pd.DataFrame(_rows, columns=_columns)


def compare_errors():
    
    global error_methods
    
    _results = {}
    
#    for method in tqdm_notebook(error_methods, desc="Methods", position=0):
#        _results[method] = np.median(error(method)['error'])
        
    with Pool(processes=4) as pool:
        _results = 0
        for result in pool.imap(error, error_methods.keys()):
            pass
            
    return pd.DataFrame(_results)



                
def locate_naive(series):
    return series.idxmax()
        

def locate_interpolate(series, method, plot=False):
    series = series.reindex(np.arange(0,360))
    
    series_left = series.copy()
    series_left.index = np.arange(-360,0)
    
    series_right = series.copy()
    series_right.index = np.arange(360,720)
    
    series_inter = pd.concat([series_left, series, series_right]).interpolate(method=method)[np.arange(0,360)]
    
    if plot:
        series_inter.plot()
    
    return series_inter.idxmax()
    

def plot(test, bssid):
    global dataframe, bearings, access_points
    
    test_dataframe = dataframe[dataframe['test'] == test]
        
    frame = test_dataframe[test_dataframe['bssid'] == bssid]
    frame.sort_values('bearing_true').reset_index()     

    fig = plt.figure()
    fig_name = f"{test} Plots"
    
    
    
    ax = plt.subplot(211)
    ax.set_title("Raw")
    ax.plot(frame['bearing_true'], frame['ssi'])
    
    
    ax = plt.subplot(212)
    ax.set_title("mW")
    ax.plot(frame['bearing_true'], frame['mw'])
    
    


def bar(test, bssids=None, hist=False):
    # https://stackoverflow.com/a/22568292/1486966
    
    global dataframe, bearings, access_points
    
    test_dataframe = dataframe[dataframe['test'] == test]
    
    if not bssids:
        bssids = access_points['BSSID']
        
    # Figure out subplot geometry
    nrows = np.ceil(np.sqrt(len(bssids)))
    ncols = np.ceil(len(bssids)/nrows)
    
    test_bearings = bearings[bearings['test'] == test]
        
    fig = plt.figure()
    fig.tight_layout()
    fig_name = f"{test} Histogram" if hist else f"{test} Bar Chart"
    fig.suptitle(fig_name)

    for i, bssid in enumerate(bssids):
        _name = access_points[access_points['BSSID'] == bssid]['SSID'].values[0]
        _title = f"{_name}\n{bssid}"
        
        # Set up frame
        frame = test_dataframe[test_dataframe['bssid'] == bssid]
        radii = np.deg2rad(frame['bearing_true'])
        
        N = 36
        bottom = np.max(frame['mw'])  
        width = (2*np.pi) / N
        
        ax = plt.subplot(nrows, ncols, i+1, polar=True)
        ax.set_title(_title, position=(.5, -.6))
        ax.set_theta_zero_location('N')
        ax.set_theta_direction(-1)
        ax.set_ylabel('mw')
                
        if hist:
            # Histogram
            bars = plt.hist(radii, N, weights=frame['mw'])      
        else:
            # Bar
            bars = plt.bar(radii, frame['mw'], width=width)
        
        bearing = test_bearings[test_bearings['bssid'] == bssid]['bearing'].values[0]
        ax.axvline(np.deg2rad(bearing), color='g', linestyle='dashed', linewidth=2)
    
    top=0.92
    bottom=0.1
    left=0.05
    right=0.95
    hspace=1.0
    wspace=0.0
    plt.subplots_adjust(left=left, bottom=bottom, right=right, top=top, wspace=wspace, hspace=hspace)
    plt.show()

        
def kml(file='test.kml'):
    """
    Generate kml file for Google Earth visualization
    """
    global access_points, tests, bearings
    
    import simplekml
    kml = simplekml.Kml()
    folders = {}
    
    # Generate Capture Locations
    for _, test in tests.iterrows():
        name = test['test']       
        lat = test['lat']
        lon = test['lon']

        fol = kml.newfolder(name=name)
        fol.newpoint(name=name, coords = [(lon, lat)])
        
        folders[name] = fol
       
    # Generate liens
    for _, bearing in bearings.iterrows():
        test_name = bearing['test']
        lat1 = bearing['lat1']
        lon1 = bearing['lon1']
        lat2 = bearing['lat2']
        lon2 = bearing['lon2']
        folders[test_name].newlinestring(coords=[(lon1, lat1), (lon2, lat2)])

    # Generate AP locations
    for _, ap in access_points.iterrows():
        name = ap['SSID']
        desc = ap['BSSID']
        lat = ap['Lat']
        lon = ap['Lon']
        kml.newpoint(name=name, description=desc, coords = [(lon, lat)])
        
    kml.save(file)
        

def load_bearings():
    global tests, access_points
    results = {'test':[], 'bssid':[], 'bearing':[], 'lat1':[], 'lon1':[], 'lat2':[], 'lon2':[]}
    
    for _, test in tests.iterrows():
        for _, ap in access_points.iterrows():
            results['test'].append(test['test'])
            results['bssid'].append(ap["BSSID"])
            results['bearing'].append(haversine_bearing(test['lat'], test['lon'], ap['Lat'], ap['Lon']))
            results['lat1'].append(test['lat'])
            results['lon1'].append(test['lon'])
            results['lat2'].append(ap['Lat'])
            results['lon2'].append(ap['Lon'])
    
    return pd.DataFrame(results)


def dbm_to_mw(dbm):
    return 10**(dbm/10)


def coords_from_dist_bearing(lat, lon, meters, bearing):
    """
    Calculate coordinates from a given point and bearing
    From: http://www.movable-type.co.uk/scripts/latlong.html
    """
    
    rad = np.deg2rad(bearing)
    sigma = meters/1000/6371
    
    lat, lon = map(np.radians, [lat, lon])

    dest_lat = np.arcsin(np.sin(lat)*np.cos(sigma)+np.cos(lat)*np.sin(sigma)*np.cos(rad))
    dest_lon = lon + np.arctan2(np.sin(rad)*np.sin(sigma)*np.cos(lat), np.cos(sigma)-np.sin(lat)*np.sin(dest_lat))
    
    return (np.rad2deg(dest_lat), np.rad2deg(dest_lon))


def distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)

    All args must be of equal length.    
    Credit: https://stackoverflow.com/a/29546836/1486966
    """
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2

    c = 2 * np.arcsin(np.sqrt(a))
    km = 6371 * c
    return km


def haversine_bearing(lat1, lon1, lat2, lon2):
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    
    dlon = lon2 - lon1
    
    y = np.sin(dlon)*np.cos(lat2)
    x = np.cos(lat1)*np.sin(lat2)-np.sin(lat1)*np.cos(lat2)*np.cos(dlon)
    
    return np.degrees(np.arctan2(y,x)) % 360

error_methods = {'naive': locate_naive, 
            'quadratic': lambda series: locate_interpolate(series, 'quadratic'), 
            'cubic': lambda series: locate_interpolate(series, 'cubic'),
            'linear': lambda series: locate_interpolate(series, 'linear'),
            'slinear': lambda series: locate_interpolate(series, 'slinear'),
            'barycentric': lambda series: locate_interpolate(series, 'barycentric'),
            'krogh': lambda series: locate_interpolate(series, 'krogh'),
            'piecewise_polynomial': lambda series: locate_interpolate(series, 'piecewise_polynomial'),
            'from_derivatives': lambda series: locate_interpolate(series, 'from_derivatives'),
            'pchip': lambda series: locate_interpolate(series, 'pchip'),
            'akima': lambda series: locate_interpolate(series, 'akima'),}


setup('../../capture')