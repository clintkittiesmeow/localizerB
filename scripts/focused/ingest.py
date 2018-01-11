# -*- coding: utf-8 -*-
"""
Created on Thu Dec  7 16:25:58 2017

@author: blaw
"""


import pandas as pd
import gps
import capmap
import os


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
                _df = pd.read_csv(os.path.join(root,file),sep=',')
                
                _parent = os.path.dirname(root)
                _guess = get_guess(_parent)
                if _guess is not None:     
                    _bssid = pd.unique(_df.bssid)
                    assert len(_bssid) == 1
                    _bssid = _bssid[0]

                    _bearing = _guess[_guess.bssid == _bssid].bearing.values[0]
                    _method = _guess[_guess.bssid == _bssid].method.values[0]

                    _df['guess_bearing'] = _bearing
                    _df['guess_method'] = _method
                    _df['focused'] = _bssid
                    
                dataframes.append(_df)
                
    df = pd.concat(dataframes, axis=0)
    df.loc[:,'mw'] = dbm_to_mw(df['ssi'])
    return df
    

def get_guess(directory):
    files = os.listdir(directory)
    
    for file in files:
        if file.endswith('-guess.csv'):
            return pd.read_csv(os.path.join(directory, file))
    
    
def get_test_gps(dataframe, directory):
    _tests = pd.unique(dataframe["test"])
    results = {'test':[], 'lat':[], 'lon':[]}
    for test in _tests:
        coord, _ = gps.process_directory(os.path.join(directory, test))
        results['test'].append(test)
        results['lat'].append(coord[0])
        results['lon'].append(coord[1])
    return pd.DataFrame(results)


def get_set(test='capture-1', test_pass=1, bssid='00:12:17:9f:79:b6'):
    global dataframe
    
    if not capmap.validate_mac(bssid):
        bssid = capmap.get_bssids_from_names(ap_name)
    return dataframe[(dataframe['test'] == test) & (dataframe['pass'] == test_pass) & (dataframe['bssid'] == bssid)]


def dbm_to_mw(dbm):
    return 10**(dbm/10)
