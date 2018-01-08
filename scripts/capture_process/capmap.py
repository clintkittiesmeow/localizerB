# -*- coding: utf-8 -*-
"""
Created on Fri Dec  8 13:45:35 2017

@author: blaw
"""

import numpy as np
import pandas as pd
import gps
import re
import os

aps_file = '../aps.csv'
_ap_prefix = "RESEARCH_MULLINS_"


def import_aps(ap_file = aps_file):
    types = {'Router Number': np.int8, 'CHANNEL': np.int8, 'Lat': np.float32, 'Lon': np.float32, 'Alt': np.float32}
    return pd.read_csv(ap_file,sep=',', dtype = types)


def get_names_from_bssid(bssids, concat=False):
    """
    Create a list of AP names based on provided bssids
    """
    
    if isinstance(bssids, str):
        return aps[aps['BSSID']==bssids].SSID.values[0]
    else:
        _return = []
        for bssid in bssids:
            _val = aps[aps['BSSID']==bssid].SSID.values[0]
            if concat:
                _val = f"{_val} - {bssid}"
            _return.append(_val)
            
        return _return
    

def get_bssids_from_names(names, concat=False):
    """
    Create a list of BSSIDs based on provided AP names
    """
        
    if isinstance(names, int):
        names = _default_prefix + str(names)
    if isinstance(names, str):
        return aps[aps['SSID']==names].BSSID.values[0]
    else:
        _return = []
        for name in names:
            _val = aps[aps['SSID']==name].BSSID.values[0]
            if _val:
                if concat:
                    _val = f"{_val} - {name}"
                _return.append(_val)
                
        return _return
        
        
def get_bearing(test, bssid):
    """
    Look up bearing from given ap
    """
    
    if not validate_mac(bssid):
        bssid = get_bssids_from_names(bssid)
    if bssid:
        return bearings[(bearings['test']==test) & (bearings['bssid']==bssid)].bearing.values[0]
        


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


def load_bearings(tests, access_points):
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


def get_test_gps(directory, dataframe):
    tests = pd.unique(dataframe["test"])
    results = {'test':[], 'lat':[], 'lon':[]}
    for test in tests:
        coord, _ = gps.process_directory(os.path.join(directory, test))
        results['test'].append(test)
        results['lat'].append(coord[0])
        results['lon'].append(coord[1])
    return pd.DataFrame(results)


def validate_mac(mac):
        return re.match("[0-9a-f]{2}([-:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", mac.lower())


def setup(directory, dataframe):
    global bearings, aps, tests
    
    aps = import_aps()
    tests = get_test_gps(directory, dataframe)
    bearings = load_bearings(tests, aps)
    
