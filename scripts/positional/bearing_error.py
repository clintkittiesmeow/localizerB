import matplotlib.pyplot as plt
from tqdm import tqdm, tnrange, tqdm_notebook
from locate import error_methods, locate_method_helper, smoothing_methods
from concurrent import futures
import capmap
import pandas as pd
import numpy as np

def error(dataframe, methods, smooth_methods=None, mw=True, true_bearing=True):
    # Loop through each set and determine the bearing based on maximum mw
    # Return the error rate as the degrees from the correct bearing
    
    # Convert single method into list to simplify later code
    if isinstance(methods, str):
        methods = [methods]
    
    # Ensure all provided methods are legitimate
    for method in methods:
        if method not in error_methods:
            print(f"You did not specify a valid method '{method}'. Available methods: {methods}")
            return
        
    if not isinstance(smooth_methods, list):
        smooth_methods = [smooth_methods]
    
    _bearing_col = 'bearing_true' if true_bearing else 'bearing_magnetic'
    _power_col = 'mw' if mw else 'ssi'
    
    # Set up lists to hold data
    _columns = ['test', 'pass', 'bssid', 'lat', 'lon', 'samples', 'fallback', 'method', 'smooth', 'bearing', 'guess', 'error']
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
                _capmap = capmap.bearings[(capmap.bearings['test'] == _test) & (capmap.bearings['bssid'] == _bssid)]
                _bearing_real = _capmap['bearing'].values[0]
                _lat = _capmap['lat_test'].values[0]
                _lon = _capmap['lon_test'].values[0]
                
                pass_groups = group.groupby('pass')
                for i, sub_group in pass_groups:
                    _fallback = None
                    _samples = len(sub_group)
                    _params_prep = [_test, i, _bssid, _lat, _lon, _samples, _fallback, _bearing_real]
                    _prep_processes[executor.submit(prep_for_plot, sub_group, _bearing_col, _power_col)] = _params_prep

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
        _len = len(_prepped_series)*len(methods)*len(smooth_methods)
        with tqdm_notebook(total = _len, desc="Interpolating") as _pbar:
                
            for method in methods:
                for smooth in smooth_methods:
                    _exec_processes[executor.submit(locate_method_helper, method, smooth, _prepped_series)] = method

            # Get the results of interpolation
            for future in futures.as_completed(_exec_processes):
                _method = _exec_processes[future]
                _errors = future.result()
                _results += _errors
                _pbar.update(len(_errors))

    return pd.DataFrame(_results, columns=_columns)


def prep_for_plot(dataframe, x='bearing_true', y='mw', expand=True):
    """
    Prepare a dataframe for interpolation by stripping extraneous columns and converting it into a series
    """

    # Stip columns and convert to series
    df = dataframe.filter([x, y]).rename(columns={x: 'deg'}).sort_values('deg')
    df['deg'] = np.round(df['deg'])

    if df.duplicated('deg', keep=False).any():
        df = df.groupby('deg', group_keys=False).apply(lambda x: x.loc[x.mw.idxmax()])

    series_mid = df.set_index('deg').reindex(np.arange(0, 360)).iloc[:,0]

    if expand:
        # Extend to the left and right in order to ease interpolation
        series_concat = series_expand(series_mid)

        return series_concat
    else:
        return series_mid


def series_expand(series):
    series_left = series.copy()
    series_left.index = np.arange(-360, 0)
    series_right = series.copy()
    series_right.index = np.arange(360, 720)

    return pd.concat([series_left, series, series_right])
    
    
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
        