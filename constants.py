import numpy as np

PI = np.pi

# how many seconds to use to calculate angle for angle-based calculations
# (acts as a smoothing coefficient)
ANGLE_LAG_SECONDS=5

# interval between counting parts 
RASTER_COOLDOWN_INTERVAL=60

# probably only need these for debugging/QA purposes
RASTER_LAT_OFFSET=0
RASTER_LONG_OFFSET=0

RASTER_SIZE_M=40

RASTER_SIZE_LAT=RASTER_SIZE_M/111000


# product of decay by distance;
# minimum factor = RASTER_DECAY_FACTOR ^ RASTER_MANHATTAN_DISTANCE_MAX
RASTER_DECAY_FACTOR=4
RASTER_MANHATTAN_DISTANCE_MAX=4

RASTER_METHOD='custom'

CUSTOM_RASTER_PROFILE = [1, 0.95, 0.9, 0.85, 0.1]

# this changes decay profile of rasters
# x = RASTER_DECAY_FACTOR
# y = RASTER_MANHATTAN_DISTANCE
# value should be 1 when y is 0
RASTER_FUNCTIONS = {
    'exponential': lambda x, y: x ** y,
    'power': lambda x, y: (1+y) ** (-x),
    'linear': lambda x, y: 1 - y / x,
    'normal': lambda x, y: np.exp(-y ** 2 / (2 * x)),
    'cosine': lambda x, y: np.cos(y * PI / x),
    'near_intersect': lambda x, y: 1 - (y > 0) * (1-x),
    'custom': lambda x, y: CUSTOM_RASTER_PROFILE[y],
}

RASTER_FUNCTION = RASTER_FUNCTIONS[RASTER_METHOD]
# determine increase in bbox size from above constants
BBOX_INCREASE_LAT=(RASTER_MANHATTAN_DISTANCE_MAX + 1) * RASTER_SIZE_LAT

