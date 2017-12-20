# -*- coding: utf-8 -*-
"""
Created on Fri Dec  8 13:45:35 2017

@author: blaw
"""

import numpy as np
import pandas as pd

def import_aps(ap_file):
    types = {'Router Number': np.int8, 'CHANNEL': np.int8, 'Lat': np.float32, 'Lon': np.float32, 'Alt': np.float32}
    return pd.read_csv(ap_file,sep=',', dtype = types)


def get_coords(aps):
     coords = [(ap["Lat"],ap["Lon"]) for ap in aps]
     return np.array(coords, dtype=[('lat', 'float'),('lon','float')])
 
def get_bssids(aps):
    return [ap["BSSID"] for ap in aps]
