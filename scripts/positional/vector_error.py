import matplotlib.pyplot as plt
from tqdm import tqdm, tnrange, tqdm_notebook
from locate import error_methods, locate_method_helper
import capmap
import vectors
import pandas as pd
import numpy as np
from itertools import combinations
from threading import Thread
import csv
from multiprocessing import Pool

# Lookup table for test locations
TEST_LOCS = {}
BSSID_LOCS = {}

def error(combos, dataframe, errors, filename):
    # Loop through each combination pass permutation and predict the position and record the error
    # Return the error rate as the tuple meters from the true location
    
    # Populate BSSID & TEST_LOCS
    global TEST_LOCS, BSSID_LOCS
    TEST_LOCS = {test: vectors.get_point(test) for test in pd.unique(dataframe.test)}
    BSSID_LOCS = {bssid: capmap.get_bssid_coord(bssid) for bssid in pd.unique(dataframe.bssid)}
    
    # Organization for result data
    _columns = ['test0', 'test1', 'test2', 'pass0', 'pass1', 'pass2', 'bssid', 'sample0', 'sample1', 'sample2', 'samples', 'ray0_p_lat', 'ray0_p_lon', 'ray0_d_lat', 'ray0_d_lon', 'ray1_p_lat', 'ray1_p_lon', 'ray1_d_lat', 'ray1_d_lon', 'ray2_p_lat', 'ray2_p_lon', 'ray2_d_lat', 'ray2_d_lon', 'guess_lat', 'guess_lon', 'error_lat', 'error_lon', 'error_distance']
    _failures = 0
    
    # Write results to CSV so we don't have to keep them in memory
    with open(filename, 'w', newline='') as results_csv:
        _csv_writer = csv.writer(results_csv, dialect="unix")
        _csv_writer.writerow(_columns)
        
        # Use multiprocessing to speed things up
        with Pool(processes=None) as pool:

            # Calculate the number of tests
            _num_combinations = 0
            for combo in combos:
                for bssid in pd.unique(dataframe.bssid):
                    _num_combinations += len(list(combinations(pd.unique(dataframe['pass']),len(combo))))

            with tqdm_notebook(total = _num_combinations, desc="Preparing") as _pbar:

                for result, count in pool.imap_unordered(batch_prep, combinator(errors, combos)):
                    _csv_writer.writerows(result)
                    _pbar.update(count)

    return filename         


def combinator(errors, combos, n=1000):
    _buffer = []
    
    for combo in combos:
        for bssid in pd.unique(errors.bssid):
            truth = BSSID_LOCS[bssid]
            _num_tests = len(combo)
            
            for passes in combinations(pd.unique(errors['pass']),_num_tests):
                # Generate our parameters
                
                _buffer.append((combo, bssid, passes))
                if len(_buffer) >= n:
                    yield (_buffer, errors, capmap.distance, TEST_LOCS)
                    _buffer = []
                    
    yield (_buffer, errors, capmap.distance, TEST_LOCS)

                
                
def batch_prep(t):
    _ray_filler = [(np.full((1,2), np.nan), np.full((1,2), np.nan))]
    _list_filler = (np.nan,)
    
    params, errors, distance, TEST_LOCS = t
    
    _prepped = []
    _count = 0
    
    for param in params:
        combo, bssid, passes = param
        _samples = ()
        rays = []
        
        try: 
            for test, pass_num in zip(combo, passes):
                bearing_guess = errors[(errors.test==test) & (errors.bssid==bssid) & (errors['pass']==pass_num)]
                _samples += (bearing_guess.samples.values[0],)
                P = TEST_LOCS[test]
                D_bearing = bearing_guess.guess.values[0]
                D = vectors.bearing_to_vector(D_bearing)
                rays.append((P,D))

        except IndexError:
            # Skip combinations that have a missing component
            continue

        else:

            guess = vectors.locate(rays).x
            truth = BSSID_LOCS[bssid]
            error = guess - truth
            error_distance = distance(guess, truth)
            
            if len(combo) < 3:
                combo += _list_filler
            if len(passes) < 3:
                passes += _list_filler
            if len(_samples) < 3:
                _samples += _list_filler
            if len(rays) < 3:
                rays += _ray_filler
                
            _result = list(combo) + list(passes) + [bssid] + list(_samples) + [sum(_samples)]
            for P,D in rays:
                _result += [P[0][0]] + [P[0][1]] + [D[0][0]] + [D[0][1]]
            _result += guess.tolist() + error.ravel().tolist() + [error_distance]
            
            _prepped.append(_result)
        
        finally: 
            _count += 1
    
    return _prepped, _count
