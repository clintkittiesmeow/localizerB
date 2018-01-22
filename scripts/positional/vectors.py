import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.optimize import least_squares
import math

import capmap
import pandas as pd


def locate(rays):
    """
    Determine the closest point to an arbitrary number of rays, and optionally plot the results
    
    :param rays:    list of ray tuples (S, D) where S is the starting point & D is a unit vector
    :return:        scipy.optimize.OptimizeResult object from scipy.optimize.least_squares call
    """
    
    # Generate a starting position, the dimension-wise mean of each ray's starting position
    ray_start_positions = []
    for ray in rays:
        ray_start_positions.append(ray[0])
    starting_P = np.stack(ray_start_positions).mean(axis=0).ravel()
    
    # Start the least squares algorithm, passing the list of rays to our error function
    ans = least_squares(distance_dimensionwise, starting_P, kwargs={'rays': rays})
    
    return ans
    
    
def distance(P, rays):
    """
    Calculate the distance between a point and each ray
    
    :param P:       1xd array representing coordinates of a point
    :param rays:    list of ray tuples (S, D) where S is the starting point & D is a unit vector
    :return:        nx1 array of closest distance from point P to each ray in rays
    """
    
    # Generate array to hold calculated error distances
    errors = np.full([len(rays),1], np.inf)
    
    # For each ray, calculate the error and put in the errors array
    for i, _ in enumerate(rays):
        S, D = rays[i]
        t_P = D.dot((P - S).T)/(D.dot(D.T))
        if t_P > 0:
            errors[i] = np.linalg.norm(P - (S + t_P * D))
        else:
            errors[i] = np.linalg.norm(P - S)
    
    # Convert the error array to a vector (vs a nx1 matrix)
    return errors.ravel()
    
    
def distance_dimensionwise(P, rays):
    """
    Calculate the distance between a point and each ray
    
    :param P:       1xd array representing coordinates of a point
    :param rays:    list of ray tuples (S, D) where S is the starting point & D is a unit vector
    :return:        d*nx1 array of closest distance from each dimension of point P to each ray in rays
    """
    
    dims = len(rays[0][0][0])
    
    # Generate array to hold calculated error distances
    errors = np.full([len(rays)*dims,1], np.inf)
    
    # For each ray, calculate the error and put in the errors array
    for i, _ in enumerate(rays):
        S, D = rays[i]
        t_P = D.dot((P - S).T)/(D.dot(D.T))
        if t_P > 0:
            errors[i*dims:(i+1)*dims] = (P - (S + t_P * D)).T
        else:
            errors[i*dims:(i+1)*dims] = (P - S).T
    
    # Convert the error array to a vector (vs a nx1 matrix)
    return errors.ravel()
    

def plot_results(rays, ans, obj=None):
    """
    Plot the rays and the optimization results
    
    :param rays:    list of ray tuples (S, D) where S is the starting point & D is a unit vector
    :param ans:     scipy.optimize.OptimizeResult object from scipy.optimize.least_squares call    
    """
    
    dims = len(rays[0][0][0])
    if 2 <= dims <= 3:
        
        # Build up a matplotlib-friendly list of coordinate arrays
        n_rays = len(rays)
        POINTS = np.empty((n_rays, dims))
        VECTORS = np.empty((n_rays, dims))
        
        # Get coordinates from each ray
        for i, ray in enumerate(rays):
            for dim in range(dims):
                POINTS[i, dim] = ray[0][0][dim]
                VECTORS[i, dim] = ray[1][0][dim]
        
        fig = plt.figure()
        gca_kwargs = {}
        
        quiver_args = []
        quiver_kwargs = {}
        
        vector_plot_args = [POINTS[:,0], POINTS[:,1]]
        vector_plot_kwargs = {'linestyle':'None', 'marker':'o', 'markeredgecolor':'r'}
        
        ans_x = ans.x.tolist()
        loc_plot_args = [ans_x[0], ans_x[1]]
        loc_plot_kwargs = {'marker':'o', 'c':'g'}
            
        if isinstance(obj, np.ndarray):
            object_plot_args = [obj[0][0], obj[0][1]]
            object_plot_kwargs = {'marker':'x'}
        
        if dims == 3:
            gca_kwargs = {'projection':'3d'}
            quiver_args = [POINTS[:,0], POINTS[:,1], POINTS[:,2], VECTORS[:,0], VECTORS[:,1], VECTORS[:,2]]
            vector_plot_kwargs['zs'] = POINTS[:,2]
            loc_plot_kwargs['zs'] = [ans_x[2]]
            if isinstance(obj, np.ndarray):
                object_plot_kwargs['zs'] = [obj[0][2]]
        else:
            quiver_args = [POINTS[:,0], POINTS[:,1], VECTORS[:,0], VECTORS[:,1]]
            quiver_kwargs['scale'] = .5
            
        ax = fig.gca(**gca_kwargs)
        # Plot vectors
        ax.quiver(*quiver_args, **quiver_kwargs)
        # Plot vector origins
        ax.plot(*vector_plot_args, **vector_plot_kwargs)
        # Plot calculated nearest point
        ax.scatter(*loc_plot_args, **loc_plot_kwargs)
        
        if isinstance(obj, np.ndarray):
            # Plot object
            ax.scatter(*object_plot_args, **object_plot_kwargs)        
        
        ax.axis('scaled')
        
        plt.show()

            
def locate_random_rays(n=3, dims=3):
    """
    Helper function that generates random vectors to demonstrate location technique
    
    :param n:       The number of rays to generate
    :param dims:    The number of dimensions for each ray
    :return:        scipy.optimize.OptimizeResult object from scipy.optimize.least_squares call
    """
    
    from scipy.spatial.distance import cdist
    
    # Distance to object the rays will be point to
    dist_to_object = 50
    # Area to space the rays starting points in
    origin_area_width = 30
    # Origin point of reference
    origin = np.zeros((1,dims))
    
    # Generate Object Position
    obj = origin
    while cdist(obj, origin) < dist_to_object:
        obj = np.random.randint(dist_to_object, 1.5*dist_to_object, (1,dims))
    
    S = []
    D = []
    
    # Generate S
    for i in range(n):
        s = np.full((1,dims), np.inf)
        while cdist(s, origin) > origin_area_width:
            s = np.random.randint(-origin_area_width/2,origin_area_width/2,(1,dims))
        S.append(s)
    
    # Generate D - Simply use the object location and add an element of random error
    for i in range(n):
        d = np.multiply(obj,np.random.uniform(.75,1.25, (1,dims)))
        d = d - origin
        D.append(d)
        
    rays = list(zip(S, D))

    ans = locate(rays)
    
    plot_results(rays, ans, obj)
    return ans


def locate_real_rays(rays, obj=None):
    ans = locate(rays)
    plot_results(rays, ans, obj)
    return ans
                 
    
def bearing_to_vector(bearing):
    """
    Create a unit vector from a given bearing
    
    :params bearing: A float bearing
    """
    
    bearing = math.radians(bearing % 360)
    
    u = math.sin(bearing)
    v = math.cos(bearing)
    return np.array([[u,v]])

def get_point(test):
    """
    Get a test's location
    """
    # Get an object location
    _lat = pd.unique(capmap.bearings[capmap.bearings.test==test].lat_test)[0]
    _lon = pd.unique(capmap.bearings[capmap.bearings.test==test].lon_test)[0]
    return np.array([[_lat, _lon]])


    