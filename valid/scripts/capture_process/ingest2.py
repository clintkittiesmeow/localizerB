# -*- coding: utf-8 -*-
"""
Created on Thu Dec  7 16:25:58 2017

@author: blaw
"""


import pandas as pd
import numpy as np
import gps
import capmap
import os
import matplotlib.pyplot as plt
from multiprocessing import Pool, cpu_count
from tqdm import tqdm, tnrange, tqdm_notebook
from locate import error_methods as error_methods

def setup(directory):
    global dataframe
    dataframe = import_captures(directory)   
    capmap.setup(directory, dataframe)
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
    _tests = pd.unique(dataframe["test"])
    results = {'test':[], 'lat':[], 'lon':[]}
    for test in _tests:
        coord, _ = gps.process_directory(os.path.join(directory, test))
        results['test'].append(test)
        results['lat'].append(coord[0])
        results['lon'].append(coord[1])
    return pd.DataFrame(results)

def compare_errors():
    
    global error_methods
    
    _results = [pd.DataFrame()]

    cores = max(cpu_count() - 1, 1)
    
    print(f"Processing with {cores} cores...")
    
    with Pool(processes=cores) as pool:
        for df in tqdm_notebook(pool.imap_unordered(error, error_methods.keys()), total=len(error_methods), desc="Methods"):
            _results.append(df)
     
    return pd.concat(_results, axis=0)


def get_set(test='capture-1', test_pass=1, bssid='00:12:17:9f:79:b6'):
    global dataframe
    
    if not capmap.validate_mac(bssid):
        bssid = capmap.get_bssids_from_names(ap_name)
    return dataframe[(dataframe['test'] == test) & (dataframe['pass'] == test_pass) & (dataframe['bssid'] == bssid)]


def error(method='naive', bearing_name='bearing_true'):
    # Loop through each test/pass and determine the bearing based on maximum mw
    # Return the error rate as the squared degrees from the correct bearing
    
    global dataframe, error_methods
    
    if method not in error_methods:
        print(f"You did not specify a valid method. Available methods: {_methods}")
    
    _columns = ['test', 'pass', 'bssid', 'error', 'fallbacks', 'samples']
    _rows = []
    
    _tests = pd.unique(capmap.bearings['test'])
    
    for test in _tests:
        _bssids = pd.unique(capmap.bearings['bssid'])
        for bssid in _bssids:
            _df = dataframe[(dataframe.test == test) & (dataframe.bssid == bssid)]
            _passes = pd.unique(_df['pass'])
            for i in _passes:
                _fallback = False
                _pass = prep_for_plot(_df[_df['pass'] == i], bearing_name)
                _samples = len(_pass)
                _true_bearing = capmap.bearings[(capmap.bearings['test'] == test) & (capmap.bearings['bssid'] == bssid)]['bearing'].values[0]
                
                try:
                    _location = error_methods[method](_pass)
                except ValueError as e:
                    # print(f"Error: couldn't use {method} method, falling back to naive; {e}")
                    _location = error_methods['naive'](_pass)
                    _fallback = True
                    
                _error = (_location-_true_bearing)%360
                # Reflect modular distance - as error gets larger than 180, it's actually getting closer to truth
                if np.abs(_error) > 180:
                    _error = -((360 - _error) % 360)
                _rows.append([test, i, bssid, _error, _fallback, _samples])
    _result = pd.DataFrame(_rows, columns=_columns)
    _result.loc[:,'method'] = method
    return _result


def prep_for_plot(dataframe, x='bearing_true', y='mw', degrees=360):
    """
    Prepare a dataframe for interpolation by stripping extraneous columns and converting it into a series
    """

    # Stip columns and convert to series
    df = dataframe.filter([x, y]).rename(columns={x: 'deg'}).sort_values('deg')
    df['deg'] = np.round(df['deg'])

    if df.duplicated('deg', keep=False).any():
        df = df.groupby('deg', group_keys=False).apply(lambda x: x.loc[x.mw.idxmax()])

    series_mid = df.set_index('deg').reindex(np.arange(0, 360)).iloc[:,0]

    if degrees == 360:
        # Extend to the left and right in order to ease interpolation
        series_left = series_mid.copy()
        series_left.index = np.arange(-360, 0)
        series_right = series_mid.copy()
        series_right.index = np.arange(360, 720)

        series_concat = pd.concat([series_left, series_mid, series_right])

        return series_concat
    else:
        return series_mid
    

def plot(test, bssid):
    global dataframe
    
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
    
    global dataframe
    
    test_dataframe = dataframe[dataframe['test'] == test]
    
    if not bssids:
        bssids = capmap.aps['BSSID']
        
    # Figure out subplot geometry
    nrows = np.ceil(np.sqrt(len(bssids)))
    ncols = np.ceil(len(bssids)/nrows)
    
    test_bearings = capmap.bearings[capmap.bearings['test'] == test]
        
    fig = plt.figure()
    fig.tight_layout()
    fig_name = f"{test} Histogram" if hist else f"{test} Bar Chart"
    fig.suptitle(fig_name)

    for i, bssid in enumerate(bssids):
        _name = capmap.aps[capmap.aps['BSSID'] == bssid]['SSID'].values[0]
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
    
    import simplekml
    kml = simplekml.Kml()
    folders = {}
    
    # Generate Capture Locations
    for _, test in capmap.tests.iterrows():
        name = test['test']       
        lat = test['lat']
        lon = test['lon']

        fol = kml.newfolder(name=name)
        fol.newpoint(name=name, coords = [(lon, lat)])
        
        folders[name] = fol
       
    # Generate liens
    for _, bearing in capmap.bearings.iterrows():
        test_name = bearing['test']
        lat1 = bearing['lat1']
        lon1 = bearing['lon1']
        lat2 = bearing['lat2']
        lon2 = bearing['lon2']
        folders[test_name].newlinestring(coords=[(lon1, lat1), (lon2, lat2)])

    # Generate AP locations
    for _, ap in capmap.aps.iterrows():
        name = ap['SSID']
        desc = ap['BSSID']
        lat = ap['Lat']
        lon = ap['Lon']
        kml.newpoint(name=name, description=desc, coords = [(lon, lat)])
        
    kml.save(file)
        

def dbm_to_mw(dbm):
    return 10**(dbm/10)

