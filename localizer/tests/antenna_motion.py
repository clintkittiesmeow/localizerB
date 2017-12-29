import numpy as np
import pandas as pd

current_bearing = 0
max_distance_pos = 360
max_distance_neg = -360

RESET_RATE = 3/360


def distance(a,b,m=360):
    #return (m/2-(3*m/2 + (a-b))%m)
    return (180 - (540 + (a - b)) % m)


def antenna_motion(n=100000):
    global current_bearing
    cols = ['bearing', 'travel']
    distances = []

    for _ in range(0,n):
        _new_bearing = np.random.random()*360
        _travel = (_new_bearing - current_bearing) % 360
        _proposed_new_bearing = current_bearing + _travel
        if _proposed_new_bearing > max_distance_pos:
            _travel = _new_bearing - 360
        elif _proposed_new_bearing < max_distance_neg:
            _travel = 360 - _new_bearing
        current_bearing += _travel

        assert current_bearing < max_distance_pos
        assert current_bearing > max_distance_neg
        distances.append((current_bearing, _travel))

    return pd.DataFrame(distances, columns=cols)


def antenna_motion2(n=100000):
    global current_bearing
    cols = ['bearing', 'travel']
    distances = []

    for _ in range(0,n):
        _new_bearing = np.random.random()*360

        _edge_case = bool(_new_bearing == current_bearing % 360)
        if _edge_case and (current_bearing >= max_distance_pos or current_bearing <= max_distance_neg):
            _travel = _new_bearing - current_bearing
        else:
            _travel = distance(current_bearing,_new_bearing)
            _proposed_new_bearing = current_bearing + _travel
            if _proposed_new_bearing > max_distance_pos:
                _travel = _travel - 360
            elif _proposed_new_bearing < max_distance_neg:
                _travel = 360 - _travel
            current_bearing += _travel

        assert current_bearing <= max_distance_pos
        assert current_bearing >= max_distance_neg
        distances.append((current_bearing, _travel))

    return pd.DataFrame(distances, columns=cols)

df1 = antenna_motion()
df1.plot(kind='hist')
df2 = antenna_motion2()
df2.plot(kind='hist')
dist1 = abs(df1['travel']).mean()
dist2 = abs(df2['travel']).mean()
print("Average travel distance for naive approach: {} ({}s)".format(dist1, dist1/RESET_RATE))
print("Average travel distance for optimal approach: {} ({}s)".format(dist2, dist2/RESET_RATE))