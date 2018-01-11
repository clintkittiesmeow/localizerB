import matplotlib.pyplot as plt
from multiprocessing import Pool, cpu_count
from tqdm import tqdm, tnrange, tqdm_notebook
from locate import locate_method_helper
from concurrent import futures
import capmap
import numpy as np
import pandas as pd


def error(widths, dataframe, mw=True, true_bearing=True):
    # Loop through each set and determine the bearing based on maximum mw
    # Return the error rate as the degrees from the correct bearing
    
    dataframe = dataframe.dropna(subset=['guess_bearing'])
    
    # Convert single width into list to simplify later code
    if isinstance(widths, tuple):
        widths = [widths]
    
    _bearing_col = 'bearing_true' if true_bearing else 'bearing_magnetic'
    _power_col = 'mw' if mw else 'ssi'
    
    # Set up lists to hold data
    _columns = ['test', 'pass', 'bssid', 'guess_orig', 'guess_orig_method', 'samples', 'width', 'error']
    _prepped_series = []
    _results = []
    
    # Use multiprocessing to speed things up
    with futures.ProcessPoolExecutor() as executor:
        
        # Make a pretty progress bar
        _len = len(dataframe.groupby(['test', 'bssid', 'pass']))
        with tqdm_notebook(total = _len, desc="Preparing data") as _pbar:
        
            _prep_processes = {}
            _exec_processes = {}

            # Prepare the data to be interpolated
            for name, group in dataframe.groupby(['test','bssid']):
                _test = name[0]
                _bssid = name[1]
                _bearing_real = capmap.bearings[(capmap.bearings['test'] == _test) & (capmap.bearings['bssid'] == _bssid)]['bearing'].values[0]

                pass_groups = group.groupby('pass')
                for i, sub_group in pass_groups:
                    _samples = len(sub_group)
                    
                    _guess_orig = pd.unique(sub_group.guess_bearing)
                    assert len(_guess_orig) == 1
                    _guess_orig = _guess_orig[0]
                    
                    _guess_orig_m = pd.unique(sub_group.guess_method)
                    assert len(_guess_orig_m) == 1
                    _guess_orig_m = _guess_orig_m[0]
                    
                    _params_prep = [_test, i, _bssid, _guess_orig, _guess_orig_m, _samples, _bearing_real]
                    _prep_processes[executor.submit(prep_for_plot, sub_group, _bearing_col, _power_col, False)] = _params_prep

                _pbar.update(len(pass_groups))
            
            # Get the results of the data preparation and create exec_processes to interpolate
            for future in futures.as_completed(_prep_processes):
                _params_prep_done = _prep_processes[future]
                try:
                    _pass_prepared = future.result()
                except Exception as e:
                    print(f"{_params_prep_done}: {e}")
                    continue
                _prepped_series.append((_params_prep_done + [_pass_prepared]))

        # Make another pretty progress bar
        _len = len(_prepped_series)*len(widths)
        with tqdm_notebook(total = _len, desc="Interpolating") as _pbar:
                
            for width in widths:
                _exec_processes[executor.submit(locate_method_helper, 'pchip', width, _prepped_series)] = width

            # Get the results of interpolation
            for future in futures.as_completed(_exec_processes):
                _width = _exec_processes[future]
                _errors = future.result()
                _results += _errors
                _pbar.update(len(_prepped_series))

    return pd.DataFrame(_results, columns=_columns)


def prep_for_plot(dataframe, x='bearing_true', y='mw', degrees_360 = False):
    """
    Prepare a dataframe for interpolation by stripping extraneous columns and converting it into a series
    """

    # Stip columns and convert to series
    df = dataframe.filter([x, y]).rename(columns={x: 'deg'}).sort_values('deg')
    df['deg'] = np.round(df['deg'])

    if df.duplicated('deg', keep=False).any():
        df = df.groupby('deg', group_keys=False).apply(lambda x: x.loc[x.mw.idxmax()])

    series_mid = df.set_index('deg').reindex(np.arange(0, 360)).iloc[:,0]

    if degrees_360:
        # Extend to the left and right in order to ease interpolation
        series_left = series_mid.copy()
        series_left.index = np.arange(-360, 0)
        series_right = series_mid.copy()
        series_right.index = np.arange(360, 720)

        series_concat = pd.concat([series_left, series_mid, series_right])

        return series_concat
    else:
        return series_mid