# -*- coding: utf-8 -*-
"""
Created on Thu Dec  7 16:26:17 2017

@author: blaw
"""

import os
import csv
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt

def process_directory(directory=os.getcwd(), plot=False):
    """
    Average the GPS location for every *-test.csv file found below the
    designated directory.
    
    :param directory: The directory to recursively search for *-test.csv
    :type directory: str
    :return: A tuple, the average gps coordinate, # of samples
    :rtype: tuple
    """
    
    tests = set()
    lats = []
    lons = []
    alts = []
    lats_e = []
    lons_e = []
    alts_e = []

    # Walk through each subdirectory of working directory
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith("-test.csv"):
                tests.add(os.path.join(root,file))

    for test in tests:
        with open(test, 'rt') as meta_csv:
            _meta_reader = csv.DictReader(meta_csv, dialect='unix')
            meta = next(_meta_reader)
            lats.append(float(meta['pos_lat']))
            lons.append(float(meta['pos_lon']))
            alts.append(float(meta['pos_alt']))
            lats_e.append(float(meta['pos_lat_err']))
            lons_e.append(float(meta['pos_lon_err']))
            alts_e.append(float(meta['pos_alt_err']))

    coords = np.array(list(zip(lats,lons)), dtype=[('lat',float),('lon',float)])
    coords = reject_outliers(coords)
    outliers = len(lats) - len(coords)
    if outliers > 0:
        print(f"Dropped {outliers} outlier coordinate{'s' if outliers>1 else ''}")

    lat = np.median(coords['lat'])
    lon = np.median(coords['lon'])
    
    if plot:
        plt.plot(coords['lon'], coords['lat'], color='g', marker='o', ls='')
        plt.plot(lon, lat, color='b', marker='x', markersize=20, markeredgewidth=5)
    
    return ((lat,lon), len(coords))

def reject_outliers(coords, m = 10.):
    d = np.abs(coords['lat'] - np.median(coords['lat']))
    mdev = np.median(d)
    s = d/mdev if mdev else 0.
    lats = coords[s<m]
    d = np.abs(lats['lon'] - np.median(lats['lon']))
    mdev = np.median(d)
    s = d/mdev if mdev else 0.
    return lats[s<m]
